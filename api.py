"""SkyDex FastAPI backend — serves aircraft data, Dex entries, weather, and facts.

Also provides a WebSocket endpoint for live aircraft push updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import subprocess
import threading
import time
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from config import SkyDexConfig
from acars import match_to_contacts as acars_match
from database import Database
from enrichment import AdsbdbClient, LocalDbClient, WeatherClient, TideClient, StormglassClient, AerodataboxClient, AirportResolver, PlanespottersClient, WikipediaImageClient, JetApiClient, CommonsImageClient
from classifier import Classifier, SchedulePredictor, contrail_likely, flight_phase, rarity_for
from aircraft_specs import get_specs, spec_summary
from countries import country_for_hex, country_name
from vessels import ship_category, category_icon, vessel_rarity, nav_status_text, is_anchored, is_notable_for_photo
from facts import get_fact, get_facts_for_empty_state, get_type_fact, get_sea_facts_for_empty_state, get_vessel_type_fact, get_atmo_facts_for_empty_state, get_atmo_fact, get_land_facts_for_empty_state, get_ether_facts_for_empty_state
from atmo import sky_report, sun_times, ApodClient, TlePassPredictor, LaunchClient, NearMissClient, AsteroidClient
from satellites import catalog_list, get_satellite
from settings import settings
from achievements import compute_achievements
from quiz import get_quiz
from landdex import TVC_TARGETS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state (set by main.py on startup)
# ---------------------------------------------------------------------------

_db: Optional[Database] = None
_receiver: Optional[Any] = None
_ais: Optional[Any] = None
_config: SkyDexConfig = SkyDexConfig()
_adsbdb = AdsbdbClient()
_localdb = LocalDbClient(_config.faa_db_path, _config.opensky_db_path)
_airports = AirportResolver(_config.airports_db_path)
_weather: Optional[WeatherClient] = None
_stormglass: Optional[StormglassClient] = None
_apod: Optional[ApodClient] = None
_sat: Optional[TlePassPredictor] = None
_launch: Optional[LaunchClient] = None
_nearmiss: Optional[NearMissClient] = None
_asteroid: Optional[AsteroidClient] = None
_land: Optional[Any] = None
_ether: Optional[Any] = None
_journeys: Optional[Any] = None
_acars: Optional[Any] = None
_acars_reg_cache: Dict[str, str] = {}
_aerodatabox = AerodataboxClient()
_planespotters = PlanespottersClient()
_jetapi = JetApiClient()
_tide = TideClient(station_id="8467150")  # Bridgeport, CT (cached; reused across requests)


def _resolve_aircraft_photo(hex_code: str, reg: str):
    """(photo_url, photographer) for an airframe, best source first:
    Planespotters (official, fast) -> JetPhotos/jetapi (huge library, by reg)
    -> AeroDataBox (paid). Returns (None, None) if nothing found."""
    info = _planespotters.lookup_photo_info(hex_code, reg)
    if info and info.get("url"):
        return info["url"], info.get("photographer")
    if reg:
        j = _jetapi.lookup_photo_info(reg)
        if j and j.get("url"):
            return j["url"], j.get("photographer")
    url = _aerodatabox.lookup_aircraft_photo(hex_code, reg)
    return url, None
_wikipedia = WikipediaImageClient()
_commons = CommonsImageClient()
_classifier = Classifier()
_schedule = SchedulePredictor()

# Proxied photo bytes: hex -> (content_type, bytes) or None (known miss).
_photo_cache: Dict[str, Any] = {}
# Representative model photos: type_code -> (content_type, bytes) or None.
_model_photo_cache: Dict[str, Any] = {}
# Proxied vessel photo bytes: mmsi -> (content_type, bytes) or None (known miss).
_vessel_photo_cache: Dict[str, Any] = {}


def _resolve_vessel_photo(vessel: Dict[str, Any]):
    """(photo_url, credit) for a vessel. Wikimedia Commons by IMO first (most
    reliable for commercial ships), then Wikipedia by name (for notable/named
    vessels like superyachts). Returns (None, None) if nothing matches."""
    # 1. Commons by IMO — covers most cargo/tanker/passenger ships.
    imo = vessel.get("imo")
    if imo:
        info = _commons.search_image(f"IMO {imo}")
        if info and info.get("url"):
            return info["url"], info.get("photographer")

    # 2. Wikipedia by name — covers named/notable vessels (AIS names are caps).
    name = (vessel.get("name") or "").strip()
    if name and _wikipedia is not None:
        title = name.title()
        cat = vessel.get("category")
        if cat == "Superyacht":
            variants = [f"{title} (yacht)", f"{title} (ship)"]
        elif cat in ("Passenger", "HSC"):
            variants = [f"{title} (ship)", f"{title} (ferry)"]
        else:
            variants = [f"{title} (ship)"]
        for t in variants:
            try:
                url = _wikipedia.image_for(t)
            except Exception:
                url = None
            if url:
                return url, None
    return None, None


def _fetch_image(url: str):
    """Download an image; returns (content_type, bytes) or raises."""
    req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return (resp.headers.get("Content-Type") or "image/jpeg", resp.read())


# --- Persistent on-disk image cache (so photos are downloaded only once) -----
_photo_dir: Optional[Path] = None


def _safe_key(key) -> str:
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in str(key))


def _sniff_ct(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _disk_get(kind: str, key) -> Optional[tuple]:
    if _photo_dir is None:
        return None
    try:
        p = _photo_dir / kind / _safe_key(key)
        if p.is_file():
            data = p.read_bytes()
            if data:
                return (_sniff_ct(data), data)
    except Exception:
        pass
    return None


def _disk_put(kind: str, key, data: bytes) -> None:
    if _photo_dir is None or not data:
        return
    try:
        d = _photo_dir / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / _safe_key(key)).write_bytes(data)
    except Exception as e:
        logger.debug("disk cache write failed (%s/%s): %s", kind, key, e)


def _cached_image(kind: str, key, url: Optional[str]) -> Optional[tuple]:
    """(content_type, bytes) from local disk, else download + store, else None."""
    hit = _disk_get(kind, key)
    if hit:
        return hit
    if not url:
        return None
    try:
        ct, data = _fetch_image(url)
    except Exception as e:
        logger.debug("image fetch failed %s: %s", url, e)
        return None
    if not data:
        return None
    _disk_put(kind, key, data)
    return (ct, data)


def set_globals(db: Database, receiver: Any, config: SkyDexConfig, ais: Any = None,
                land: Any = None, ether: Any = None, journeys: Any = None,
                acars: Any = None) -> None:
    global _db, _receiver, _ais, _config, _weather, _stormglass, _localdb, _airports, _photo_dir, _apod, _sat, _launch, _nearmiss, _asteroid, _land, _ether, _journeys, _acars
    _db = db
    _receiver = receiver
    _ais = ais
    _land = land
    _ether = ether
    _journeys = journeys
    _acars = acars
    _config = config
    _localdb = LocalDbClient(config.faa_db_path, config.opensky_db_path)
    _airports = AirportResolver(config.airports_db_path)
    _weather = WeatherClient(config.location.lat, config.location.lon)
    _stormglass = StormglassClient(config.location.lat, config.location.lon)
    if config.atmo.enabled:
        _apod = ApodClient(config.atmo.nasa_apod_key, config.atmo.apod_cache_seconds)
        _launch = LaunchClient(config.atmo.passes_cache_seconds)
        _nearmiss = NearMissClient(config.atmo.rapidapi_key)
        _asteroid = AsteroidClient(config.atmo.nasa_apod_key)
        if config.atmo.iss_passes_enabled:
            _sat = TlePassPredictor(config.location.lat, config.location.lon,
                                    alt_m=30.0, min_elevation=config.atmo.iss_min_elevation)
    _photo_dir = Path(config.photo_cache_dir).expanduser()
    try:
        _photo_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("could not create photo cache dir %s: %s", _photo_dir, e)


def _airport_label(code: Optional[str]) -> str:
    """'City (CODE)' for an airport code, or just the code/'???' as fallback."""
    if not code:
        return "???"
    info = _airports.resolve(code) if _airports else None
    city = (info or {}).get("city")
    return f"{city} ({code})" if city else code


def _enrich_airport(obj: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Add name/city/country to a {code, count} airport object, in place."""
    if not obj or not obj.get("code"):
        return obj
    info = _airports.resolve(obj["code"])
    if info:
        obj["name"] = info.get("name")
        obj["city"] = info.get("city")
        obj["country"] = info.get("country")
        obj["country_iso"] = info.get("country_iso")
    return obj


def _agg_cities(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate {code, count} airport rows into cities (JFK+LGA -> New York)."""
    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        info = _airports.resolve(r.get("code"))
        city = (info or {}).get("city") or r.get("code") or "Unknown"
        entry = agg.setdefault(city, {"city": city, "count": 0,
                                      "country_iso": (info or {}).get("country_iso")})
        entry["count"] += r.get("count", 0)
    return list(agg.values())


def _haversine_mi(lat1, lon1, lat2, lon2) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def _route_distance_mi(o_code: str, d_code: str):
    o = _airports.resolve(o_code)
    d = _airports.resolve(d_code)
    if o and d and o.get("lat") is not None and d.get("lat") is not None:
        return _haversine_mi(o["lat"], o["lon"], d["lat"], d["lon"])
    return None


def _compute_badges(airframe: Dict[str, Any], sightings: List[Dict[str, Any]],
                    types: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Collectible badges for an airframe (shown on the Dex card)."""
    badges: List[Dict[str, str]] = []

    def add(label, color, title):
        badges.append({"label": label, "color": color, "title": title})

    count = airframe.get("detection_count") or 0
    if count >= 100:
        add("Centurion", "#e64980", f"Seen {count} times — a true regular")
    elif count >= 10:
        add("Frequent Flyer", "#FFD700", f"Seen {count} times")
    elif count >= 3:
        add("Regular", "#30A7D7", f"Seen {count} times")
    elif count <= 1:
        add("First Sighting", "#4ade80", "New to your Dex")

    if airframe.get("emergency_seen"):
        add("Emergency", "#ff4d4d", "Seen squawking an emergency code (7500/7600/7700)")

    try:
        yr = int(str(airframe.get("year_built") or "")[:4])
        age = datetime.now().year - yr
        if age >= 20:
            add("Veteran", "#b08d57", f"Built {yr} · {age} yrs old")
        elif 0 <= age <= 5:
            add("Brand New", "#7ee0ff", f"Built {yr}")
    except (TypeError, ValueError):
        pass

    typeset = {t.get("type") for t in (types or [])}
    if "Sentinel" in typeset:
        add("Military", "#C03028", "Military aircraft")
    if "Heavy" in typeset:
        add("Heavy", "#7038F8", "Widebody heavy")
    if "Rotor" in typeset:
        add("Rotor", "#F08030", "Helicopter")

    home = (_config.location.home_airport_icao or "").upper()
    max_dist = 0.0
    is_local = False
    countries = set()
    night = dawn = False
    for s in sightings:
        o = (s.get("origin_airport") or "").upper()
        d = (s.get("dest_airport") or "").upper()
        if home and (o == home or d == home):
            is_local = True
        for code in (o, d):
            if code:
                info = _airports.resolve(code)
                if info and info.get("country_iso"):
                    countries.add(info["country_iso"])
        if o and d:
            dm = _route_distance_mi(o, d)
            if dm and dm > max_dist:
                max_dist = dm
        ts = s.get("started_at")
        if ts:
            try:
                h = datetime.fromtimestamp(float(ts)).hour
                if h >= 21 or h < 5:
                    night = True
                elif 5 <= h < 8:
                    dawn = True
            except (ValueError, OSError, TypeError):
                pass

    if is_local:
        add(f"{home} Local", "#FFCB05", f"Flies to/from {home}")
    if max_dist >= 3000:
        add("Long Hauler", "#9c27b0", f"Longest leg ~{int(max_dist):,} mi")
    if len(countries) >= 3:
        add("Globetrotter", "#20c997", f"Seen on routes across {len(countries)} countries")
    if night:
        add("Night Owl", "#5c6bc0", "Spotted after dark")
    if dawn:
        add("Dawn Patrol", "#ffa94d", "Spotted at dawn")

    return badges


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent

app = FastAPI(title="SkyDex", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Cache-buster appended to static asset URLs. Changes every server start, so a
# restart always serves fresh CSS/JS to the kiosk (Chromium caches aggressively).
STATIC_VERSION = datetime.now().strftime("%Y%m%d%H%M%S")


# -- TemplateResponse compatibility ------------------------------------------
# Starlette changed the TemplateResponse API between versions.
#   New API (Starlette >= 0.28):  TemplateResponse(request, name, context=None)
#   Old API (Starlette < 0.28):   TemplateResponse(name, context) with context["request"] set
#
# Since newer Starlette uses *args, **kwargs, signature inspection doesn't
# work.  We detect at import time by trying the new API against a dummy.

def _detect_template_api():
    """Returns 'new' or 'old' for the TemplateResponse API flavour."""
    try:
        from starlette.requests import Request as _R
        from unittest.mock import MagicMock
        dummy_req = MagicMock(spec=_R)
        # Try new API (request first); if it raises TypeError about
        # positional args, we have the old API.
        templates.TemplateResponse(dummy_req, "_nonexistent.html")
    except TypeError as e:
        # If the error complains about 'request' or positional args,
        # it's the old API that expects (name, context).
        msg = str(e).lower()
        if "takes" in msg or "positional" in msg or "request" in msg:
            return "old"
    except Exception:
        # Any other error means the API call was accepted and it failed
        # later (file not found, etc.) — that's the new API.
        pass
    return "new"

_TEMPLATE_API = _detect_template_api()
logger.info("Starlette TemplateResponse API detected: %s", _TEMPLATE_API)


def _template_response(request: Request, name: str, context: Dict[str, Any] | None = None, **kwargs):
    """Version-agnostic TemplateResponse wrapper. HTML pages are sent no-cache so
    the kiosk never renders a stale layout (static assets are versioned instead)."""
    ctx = context or {}
    if _TEMPLATE_API == "new":
        resp = templates.TemplateResponse(request, name, ctx, **kwargs)
    else:
        ctx["request"] = request
        resp = templates.TemplateResponse(name, ctx, **kwargs)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


# -- HTML pages -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main kiosk screen."""
    return _template_response(request, "index.html", {
        "v": STATIC_VERSION,
        "home_lat": _config.location.lat,
        "home_lon": _config.location.lon,
        "home_name": _config.location.name,
        "radius": _config.range.radius_miles,
    })


@app.get("/dex/{hex_code}", response_class=HTMLResponse)
async def dex_page(request: Request, hex_code: str):
    """Individual airframe Dex detail page."""
    return _template_response(request, "dex.html", {"hex": hex_code, "v": STATIC_VERSION})


# -- helpers ----------------------------------------------------------------

def _visible_contacts(radius: float | None = None) -> List[Dict[str, Any]]:
    """Contacts you could plausibly see (altitude-aware range)."""
    if _receiver is None:
        return []
    base = radius if radius is not None else _config.range.radius_miles
    return _receiver.get_visible_contacts(
        base,
        _config.range.visibility_miles_per_1000ft,
        _config.range.max_visible_radius_miles,
    )


# -- API endpoints ----------------------------------------------------------

@app.get("/api/contacts")
async def get_contacts(in_range_only: bool = True, radius_miles: float | None = None) -> List[Dict[str, Any]]:
    """Live aircraft contacts.

    By default returns only aircraft within the configured "nearby" radius
    (``range.radius_miles``) — the Live view should show what you can actually
    see overhead, not every aircraft in the wider scan box. Pass
    ``in_range_only=false`` to get everything, or ``radius_miles=N`` to override.
    """
    if _receiver is None:
        return []

    if in_range_only:
        contacts = _visible_contacts(radius_miles)
    else:
        contacts = list(_receiver.get_all_contacts().values())
        contacts.sort(key=lambda c: c.get("distance_miles", 999))

    enriched = []

    for ac in contacts:
        hex_code = ac["hex"]

        # Enrich from database (cached info)
        db_ac = _db.get_airframe(hex_code) if _db else None

        # Enrich from local DBs / adsbdb (only when we don't already have it)
        extra: Dict[str, Any] = {}
        if db_ac and db_ac.get("model"):
            extra = {
                "model": db_ac.get("model"),
                "operator": db_ac.get("operator"),
                "registration": db_ac.get("registration"),
                "type_code": db_ac.get("type_code"),
                "manufacturer": db_ac.get("manufacturer"),
                "photo_url": db_ac.get("photo_url"),
            }
            extra = {k: v for k, v in extra.items() if v}
        else:
            extra = _localdb.lookup_hex(hex_code) or _adsbdb.lookup_hex(hex_code)
            if _db and extra:
                _db.update_airframe(hex_code, **extra)

        # Route lookup (per-flight)
        if ac.get("callsign"):
            route = _adsbdb.lookup_callsign(ac["callsign"])
            if route:
                extra.update(route)

        # Classify + derive flight state + rarity + country of registration
        merged = {**ac, **extra}
        types = _classifier.classify(merged)
        ac["contrail_likely"] = contrail_likely(ac.get("altitude"))
        ac["phase"] = flight_phase(ac.get("altitude"), ac.get("vertical_rate"), ac.get("ground_speed"))
        ac["country"] = country_for_hex(hex_code)
        rarity = (db_ac.get("rarity") if db_ac and db_ac.get("rarity") not in (None, "Common") else None) or rarity_for(merged)

        dex_num = db_ac.get("dex_number") if db_ac else None
        det_count = db_ac.get("detection_count") if db_ac else 0

        enriched.append({
            **ac,
            **extra,
            "types": types,
            "rarity": rarity,
            "dex_number": dex_num,
            "detection_count": det_count,
            "shiny": False,  # TODO: gamify layer
        })

    return enriched


@app.get("/api/vessels")
async def get_vessels(in_range_only: bool = True, radius_miles: float | None = None) -> List[Dict[str, Any]]:
    """Live marine traffic (SeaDex) — AIS vessels near home, nearest first."""
    if _ais is None:
        return []
    radius = radius_miles if radius_miles is not None else _config.marine.radius_miles
    if in_range_only:
        vessels = _ais.get_vessels_in_range(radius)
    else:
        vessels = list(_ais.get_all_vessels().values())
        vessels.sort(key=lambda v: v.get("distance_miles", 9999))

    out = []
    for v in vessels:
        # Ship type/length arrive in infrequent AIS static messages; if the live
        # feed doesn't have them yet, fall back to what we've already stored so
        # the list doesn't show a known Tug/Superyacht as "Other".
        st = v.get("ship_type")
        length = v.get("length")
        if st is None and _db is not None:
            stored = _db.get_vessel(v.get("mmsi"))
            if stored:
                st = stored.get("ship_type")
                length = length or stored.get("length")
        cat = ship_category(st, length)
        out.append({
            **v,
            "category": cat,
            "icon": category_icon(cat),
            "rarity": vessel_rarity(st, length),
            "nav_status_text": nav_status_text(v.get("nav_status")),
            "anchored": is_anchored(v.get("nav_status"), v.get("speed")),
        })
    return out


@app.get("/api/vessel-dex")
async def get_vessel_dex(sort: str = "detection_count", limit: int = 1000) -> List[Dict[str, Any]]:
    """The Fleetdex — all collected vessels."""
    if _db is None:
        return []
    order_map = {
        "detection_count": "detection_count DESC",
        "first_seen": "first_seen DESC",
        "dex_number": "dex_number ASC",
        "rarity": "rarity",
    }
    order = order_map.get(sort, "detection_count DESC")
    vessels = _db.list_vessels(order_by=order, limit=limit)
    for v in vessels:
        v["icon"] = category_icon(v.get("category") or "Other")
    return vessels


def _compute_vessel_badges(vessel: Dict[str, Any], sightings: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    badges: List[Dict[str, str]] = []

    def add(label, color, title):
        badges.append({"label": label, "color": color, "title": title})

    count = vessel.get("detection_count") or 0
    if count >= 100:
        add("Harbor Regular", "#e64980", f"Seen {count} times")
    elif count >= 10:
        add("Frequent Visitor", "#FFD700", f"Seen {count} times")
    elif count >= 3:
        add("Regular", "#30A7D7", f"Seen {count} times")
    elif count <= 1:
        add("First Sighting", "#4ade80", "New to your Fleetdex")

    length = vessel.get("length")
    if length and length >= 200:
        add("Big Ship", "#7038F8", f"{int(length)} m length")

    if is_anchored(vessel.get("nav_status"), vessel.get("speed")):
        add("Anchored", "#78909c", "Currently at anchor / moored")

    cat = vessel.get("category")
    from vessels import CATEGORY_COLORS
    if cat and cat not in ("Other", "Pleasure"):
        add(cat, CATEGORY_COLORS.get(cat, "#888"), f"{cat} vessel")

    night = dawn = False
    for s in sightings:
        ts = s.get("started_at")
        if ts:
            try:
                h = datetime.fromtimestamp(float(ts)).hour
                if h >= 21 or h < 5:
                    night = True
                elif 5 <= h < 8:
                    dawn = True
            except (ValueError, OSError, TypeError):
                pass
    if night:
        add("Night Owl", "#5c6bc0", "Seen after dark")
    if dawn:
        add("Dawn Patrol", "#ffa94d", "Seen at dawn")
    return badges


@app.get("/api/vessel/{mmsi}")
async def get_vessel_detail(mmsi: str) -> Dict[str, Any]:
    """Full detail for one vessel (SeaDex card)."""
    if _db is None:
        return {"error": "Database not initialized"}
    mmsi = str(mmsi).strip()
    try:
        vessel = _db.get_vessel(mmsi)
        live = _ais.get_vessel(mmsi) if _ais else None
        if not vessel:
            if not live:
                return {"error": "Vessel not found"}
            vessel = {"mmsi": mmsi, "dex_number": None, "detection_count": 0, "rarity": "Common"}
        if live:
            for k in ("name", "callsign", "speed", "course", "heading", "destination",
                      "distance_miles", "bearing", "length", "lat", "lon", "imo"):
                if live.get(k) is not None:
                    vessel[k] = live[k]
            if live.get("country"):
                vessel["flag"] = live["country"]
            if live.get("ship_type") is not None:
                vessel["ship_type"] = live["ship_type"]
            vessel["nav_status_text"] = nav_status_text(live.get("nav_status"))

        vessel["category"] = ship_category(vessel.get("ship_type"), vessel.get("length"))
        vessel["icon"] = category_icon(vessel["category"])
        vessel["rarity"] = vessel_rarity(vessel.get("ship_type"), vessel.get("length"))
        vessel["flag_name"] = country_name(vessel.get("flag"))

        # Resolve a photo once (by IMO via Commons, else notable named vessels),
        # then cache the URL + credit on the row so we never look it up again.
        if not vessel.get("photo_url") and not vessel.get("photo_checked") \
                and (vessel.get("imo") or is_notable_for_photo(vessel.get("category"), vessel.get("length"))):
            url, credit = _resolve_vessel_photo(vessel)
            try:
                _db.update_vessel(mmsi, photo_url=url or None, photo_credit=credit or None, photo_checked=1)
            except Exception:
                pass
            if url:
                vessel["photo_url"] = url
                vessel["photo_credit"] = credit

        # A Wikipedia blurb for named vessels that have a page ("might be cool").
        wiki = None
        name = (vessel.get("name") or "").strip()
        if name and _wikipedia is not None and vessel.get("category") in ("Superyacht", "Passenger", "HSC", "Government"):
            wiki = _wikipedia.summary_for(name.title())

        sightings = _db.get_vessel_sightings(mmsi, 12)
        badges = _compute_vessel_badges(vessel, sightings)
        return {
            "vessel": vessel,
            "sightings": sightings,
            "badges": badges,
            "total_sightings": len(sightings),
            "type_fact": get_vessel_type_fact(vessel.get("category")),
            "wiki": wiki,
        }
    except Exception as e:
        logger.warning("vessel detail error for %s: %s", mmsi, e, exc_info=True)
        return {"error": "Failed to load vessel detail"}


@app.get("/api/sea-stats")
async def get_sea_stats() -> Dict[str, Any]:
    """SeaDex stats + graph data."""
    if _db is None:
        return {}
    stats = _db.get_vessel_stats()
    live = len(_ais.get_vessels_in_range(_config.marine.radius_miles)) if _ais else 0

    activity_by_type_day: Dict[str, List[int]] = {}
    try:
        for cat, dow in _db.get_vessel_category_dow():
            if dow is None or not (0 <= dow <= 6):
                continue
            activity_by_type_day.setdefault(cat or "Other", [0] * 7)[dow] += 1
    except Exception as e:
        logger.debug("sea activity-by-type-day failed: %s", e)

    # Convert nav-status codes to readable labels for the breakdown.
    nav_text: Dict[str, int] = {}
    for code, count in (stats.get("nav_status_distribution") or {}).items():
        nav_text[nav_status_text(code) or "Unknown"] = nav_text.get(nav_status_text(code) or "Unknown", 0) + count
    stats["nav_status_distribution"] = nav_text

    # Spell out flag-state names (e.g. MH -> Marshall Islands).
    for f in stats.get("top_flags", []):
        f["name"] = country_name(f.get("label")) or f.get("label")

    return {**stats, "live_vessels": live, "activity_by_type_day": activity_by_type_day}


@app.get("/api/day-summary")
async def get_day_summary() -> Dict[str, Any]:
    """Combined air + sea report for today (linked from the Live views)."""
    if _db is None:
        return {}
    try:
        data = _db.get_day_summary()
    except Exception as e:
        logger.warning("day summary failed: %s", e, exc_info=True)
        data = {"air": {}, "sea": {}}
    # Add live "in range right now" counts for both worlds.
    try:
        data.setdefault("air", {})["live_now"] = len(_visible_contacts())
    except Exception:
        pass
    try:
        sea_live = len(_ais.get_vessels_in_range(_config.marine.radius_miles)) if _ais else 0
        data.setdefault("sea", {})["live_now"] = sea_live
    except Exception:
        pass
    # Turn route airport codes into "City (CODE) → City (CODE)" labels.
    try:
        for r in data.get("air", {}).get("top_routes", []):
            r["label"] = f"{_airport_label(r.get('origin'))} → {_airport_label(r.get('dest'))}"
    except Exception as e:
        logger.debug("route city labels failed: %s", e)
    # Spell out vessel flag-state names (US -> United States).
    try:
        for f in data.get("sea", {}).get("top_flags", []):
            f["label"] = country_name(f.get("label")) or f.get("label")
    except Exception as e:
        logger.debug("flag names failed: %s", e)
    try:
        data["date"] = datetime.now().strftime("%A, %B %d, %Y")
    except Exception:
        data["date"] = ""
    return data


@app.get("/api/airframe/{hex_code}")
async def get_airframe_detail(hex_code: str) -> Dict[str, Any]:
    """Full detail for a single airframe (Dex page).

    Works for any currently-visible aircraft even if it hasn't been logged to
    the database yet (e.g. it's outside the detection radius): in that case we
    synthesize the record from the live receiver contact.
    """
    if _db is None:
        return {"error": "Database not initialized"}

    hex_code = hex_code.upper().strip()
    try:
        airframe = _db.get_airframe(hex_code)
        live = _receiver.get_contact(hex_code) if _receiver else None

        if not airframe:
            if not live:
                return {"error": "Airframe not found"}
            # Build a minimal record straight from the live contact.
            airframe = {
                "hex": hex_code,
                "dex_number": None,
                "detection_count": 0,
                "rarity": "Common",
                "evolution_tier": "Spotted",
            }

        # Overlay current live telemetry so the detail page shows real-time data.
        if live:
            for key in ("altitude", "ground_speed", "track", "vertical_rate",
                        "distance_miles", "callsign", "lat", "lon"):
                if live.get(key) is not None:
                    airframe[key] = live[key]

        history = _db.get_detections_for_airframe(hex_code, limit=500)

        # Enrich (if missing) — local DBs, then adsbdb, then paid AeroDataBox
        if not airframe.get("model"):
            extra = (_localdb.lookup_hex(hex_code)
                     or _adsbdb.lookup_hex(hex_code)
                     or _aerodatabox.lookup_aircraft_info(hex_code))
            if extra:
                if _db.get_airframe(hex_code):
                    _db.update_airframe(hex_code, **extra)  # non-column keys are ignored
                airframe.update(extra)

        # Route lookup for the current flight (origin/dest/airline)
        route = {}
        if airframe.get("callsign"):
            route = _adsbdb.lookup_callsign(airframe["callsign"])
            airframe.update({k: v for k, v in route.items() if v})

        # Country of registration (offline, from the ICAO hex)
        airframe["country"] = country_for_hex(hex_code)

        # Resolve the route airports to full name / city / country.
        for pre in ("origin", "dest"):
            code = airframe.get(f"{pre}_icao") or airframe.get(f"{pre}_iata")
            info = _airports.resolve(code) if code else None
            if info:
                if not airframe.get(f"{pre}_city"):
                    airframe[f"{pre}_city"] = info.get("city")
                airframe[f"{pre}_name"] = info.get("name")
                airframe[f"{pre}_country"] = info.get("country")
                airframe[f"{pre}_country_iso"] = info.get("country_iso")

        # Real photo of this airframe, if we don't have one: free Planespotters
        # first (with photographer credit), then paid AeroDataBox.
        if not airframe.get("photo_url"):
            reg = airframe.get("registration") or ""
            photo, credit = _resolve_aircraft_photo(hex_code, reg)
            if photo:
                airframe["photo_url"] = photo
                if credit:
                    airframe["photo_credit"] = credit
                if _db.get_airframe(hex_code):
                    _db.update_airframe(hex_code, photo_url=photo, photo_credit=credit or None)

        types = _classifier.classify(airframe, history)

        schedule = None
        if history and len(history) >= 3:
            schedule = _schedule.analyze(history)

        # Curated fact if we have one, else a blurb generated from the spec sheet.
        tc = airframe.get("type_code", "") or ""
        type_fact = get_type_fact(tc) or spec_summary(tc)

        # Sighting log with resolved city names for each leg.
        sightings = _db.get_sightings_for_airframe(hex_code, 12)
        for s in sightings:
            oi = _airports.resolve(s.get("origin_airport"))
            di = _airports.resolve(s.get("dest_airport"))
            if oi:
                s["origin_city"] = oi.get("city") or oi.get("name")
            if di:
                s["dest_city"] = di.get("city") or di.get("name")

        # Sharpened rarity (type/role based) — keep it on the airframe too.
        airframe["rarity"] = rarity_for(airframe)

        # Collectible badges + this airframe's own departure/arrival regulars.
        badges = _compute_badges(airframe, sightings, types)
        route_stats = _db.get_airframe_route_stats(hex_code, 5)
        for grp in ("origins", "dests"):
            for r in route_stats.get(grp, []):
                info = _airports.resolve(r.get("code"))
                if info:
                    r["city"] = info.get("city")
                    r["name"] = info.get("name")

        count = airframe.get("detection_count", 0) or 0
        tier = airframe.get("evolution_tier") or "Spotted"
        for name, threshold in reversed(_config.game.evolution_tiers):
            if count >= threshold:
                tier = name
                break

        return {
            "airframe": airframe,
            "history": history[:50],  # Last 50 telemetry rows for the altitude graph
            "sightings": sightings,
            "badges": badges,
            "route_stats": route_stats,
            "types": types,
            "specs": get_specs(airframe.get("type_code")),
            "schedule": schedule,
            "type_fact": type_fact,
            "evolution_tier": tier,
            "phase": flight_phase(airframe.get("altitude"), airframe.get("vertical_rate"), airframe.get("ground_speed")),
            "contrail_likely": contrail_likely(airframe.get("altitude")),
            "total_detections": len(history),
        }
    except Exception as e:
        logger.warning("airframe detail error for %s: %s", hex_code, e, exc_info=True)
        return {"error": "Failed to load aircraft detail"}


@app.get("/api/dex")
async def get_dex(
    sort: str = "detection_count",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """All collected airframes (the Planedex)."""
    if _db is None:
        return []

    order_map = {
        "detection_count": "detection_count DESC",
        "first_seen": "first_seen DESC",
        "dex_number": "dex_number ASC",
        "rarity": "rarity",
    }
    order = order_map.get(sort, "detection_count DESC")
    return _db.list_airframes(order_by=order, limit=limit)


@app.get("/api/stats")
async def get_stats() -> Dict[str, Any]:
    """Overall SkyDex statistics."""
    if _db is None:
        return {}

    stats = _db.get_stats()

    # Add live contact count
    live_count = len(_visible_contacts())

    # Top airframes
    top = _db.get_top_airframes(3)

    # Fleet breakdown by behavioral type (Rotor / Hauler / Hopper / ...), plus a
    # hex -> primary-type map we reuse for the per-day activity chart.
    type_breakdown: Dict[str, int] = {}
    hex_type: Dict[str, str] = {}
    try:
        for af in _db.list_airframes(order_by="detection_count DESC", limit=100000):
            classes = _classifier.classify(af)
            primary = classes[0]["type"] if classes else "Aircraft"
            type_breakdown[primary] = type_breakdown.get(primary, 0) + 1
            hex_type[(af.get("hex") or "").upper()] = primary
    except Exception as e:
        logger.debug("type breakdown failed: %s", e)

    # Resolve the route airports (top/rarest) to name/city/country.
    for key in ("top_origin", "top_dest", "bottom_origin", "bottom_dest"):
        if stats.get(key):
            _enrich_airport(stats[key])

    # Activity by fleet type by day-of-week (0=Sun..6=Sat): {type: [7 counts]}.
    activity_by_type_day: Dict[str, List[int]] = {}
    try:
        for hex_code, dow in _db.get_sightings_dow():
            if dow is None or not (0 <= dow <= 6):
                continue
            t = hex_type.get((hex_code or "").upper(), "Aircraft")
            activity_by_type_day.setdefault(t, [0] * 7)[dow] += 1
    except Exception as e:
        logger.debug("activity-by-type-day failed: %s", e)

    # Emergency squawk events (for the Graphs page).
    emergency_counts = _db.get_emergency_counts()
    emergencies = _db.get_emergencies(12)
    for e in emergencies:
        af = _db.get_airframe(e.get("hex"))
        if af:
            e["model"] = af.get("model") or af.get("registration")

    # Departure / arrival cities (airports aggregated to cities), top + rarest.
    dep_all = _agg_cities(_db.get_route_counts("origin", 1000))
    arr_all = _agg_cities(_db.get_route_counts("dest", 1000))
    dep_cities = sorted(dep_all, key=lambda x: x["count"], reverse=True)[:8]
    arr_cities = sorted(arr_all, key=lambda x: x["count"], reverse=True)[:8]
    dep_cities_rare = sorted(dep_all, key=lambda x: (x["count"], x["city"]))[:8]
    arr_cities_rare = sorted(arr_all, key=lambda x: (x["count"], x["city"]))[:8]

    return {
        **stats,
        "live_contacts": live_count,
        "top_airframes": top,
        "type_breakdown": type_breakdown,
        "activity_by_type_day": activity_by_type_day,
        "dep_cities": dep_cities,
        "arr_cities": arr_cities,
        "dep_cities_rare": dep_cities_rare,
        "arr_cities_rare": arr_cities_rare,
        "emergency_counts": emergency_counts,
        "emergencies": emergencies,
        "top_models": _db.get_model_counts(8),
        "top_operators": _db.get_operator_counts(8),
        "location": {
            "name": _config.location.name,
            "lat": _config.location.lat,
            "lon": _config.location.lon,
            "airport": _config.location.home_airport_name,
            "icao": _config.location.home_airport_icao,
        },
    }


@app.get("/api/weather")
async def get_weather() -> Optional[Dict[str, Any]]:
    """Current weather."""
    if _weather is None:
        return None
    return _weather.fetch()


def _cloud_pct_from(condition: Optional[str]) -> Optional[float]:
    """Rough cloud-cover % from an NWS/Open-Meteo condition string."""
    if not condition:
        return None
    c = condition.lower()
    if any(k in c for k in ("rain", "storm", "snow", "shower", "thunder")):
        return 95.0
    if "overcast" in c or "cloudy" in c:
        return 90.0 if "mostly" in c or "overcast" in c else 60.0
    if "partly" in c or "scattered" in c:
        return 40.0
    if "few" in c or "mainly clear" in c:
        return 20.0
    if "clear" in c or "sunny" in c or "fair" in c:
        return 10.0
    return None


@app.get("/api/weather-log")
async def get_weather_log() -> Dict[str, Any]:
    """StormDex — logged weather catches + 'on this day' from past years."""
    if _db is None:
        return {"events": [], "on_this_day": []}
    return {
        "events": _db.list_weather_events(80),
        "on_this_day": _db.weather_on_this_day(datetime.now().strftime("%m-%d")),
    }


@app.get("/api/atmo")
async def get_atmo() -> Dict[str, Any]:
    """AtmoDex — tonight's sky: moon, sun/twilight, planets, meteor showers,
    sky tips, viewing quality, plus weather/alerts/tide for convenience."""
    if _config is None or not _config.atmo.enabled:
        return {}
    lat, lon = _config.location.lat, _config.location.lon
    w = None
    try:
        w = _weather.fetch() if _weather else None
    except Exception as e:
        logger.debug("atmo weather failed: %s", e)
    rep = sky_report(lat, lon, _cloud_pct_from((w or {}).get("condition")))
    rep["weather"] = w
    try:
        rep["alerts"] = _weather.fetch_alerts(_config.marine.nws_marine_zone) if _weather else []
    except Exception:
        rep["alerts"] = []
    try:
        rep["tide"] = _tide.fetch()
    except Exception:
        rep["tide"] = None
    return rep


@app.get("/api/atmo/apod")
async def get_apod() -> Optional[Dict[str, Any]]:
    """NASA Astronomy Picture of the Day (cached)."""
    if _apod is None:
        return None
    return _apod.fetch()


@app.get("/api/atmo/passes")
async def get_iss_passes() -> Dict[str, Any]:
    """Upcoming ISS passes overhead (cached)."""
    if _sat is None or _config is None:
        return {}
    return _sat.fetch(_config.atmo.iss_norad_id) or {}


@app.get("/api/atmo/launches")
async def get_launches() -> List[Dict[str, Any]]:
    """Upcoming rocket launches (Wallops ones may be visible from CT)."""
    if _launch is None:
        return []
    return _launch.fetch()


@app.get("/api/atmo/satellite/{norad}")
async def get_satellite_detail(norad: int) -> Dict[str, Any]:
    """Full detail for one satellite (catalog metadata + live passes + a fact)."""
    meta = get_satellite(norad)
    if not meta:
        return {"error": "Satellite not found"}
    passes, position = [], None
    if _sat is not None:
        try:
            p = _sat.fetch(norad)
            passes = (p or {}).get("passes") or []
            for pp in passes:                       # build a history as we predict
                try:
                    _db.log_satellite_pass(norad, pp["start"], pp.get("peak"),
                                           pp.get("end"), pp.get("max_elevation"))
                except Exception:
                    pass
        except Exception as e:
            logger.debug("sat detail passes %s failed: %s", norad, e)
        try:
            position = _sat.position(norad)
        except Exception as e:
            logger.debug("sat detail position %s failed: %s", norad, e)
    near = []
    if _nearmiss is not None:
        try:
            near = _nearmiss.fetch(norad)
        except Exception as e:
            logger.debug("sat detail near-miss %s failed: %s", norad, e)
    history, total_logged = [], 0
    if _db is not None:
        try:
            history = _db.get_satellite_passes(norad, 10)
            total_logged = _db.get_satellite_pass_count(norad)
        except Exception as e:
            logger.debug("sat pass history %s failed: %s", norad, e)
    return {"satellite": {"norad": int(norad), **meta}, "passes": passes,
            "position": position, "near_misses": near,
            "history": history, "total_logged": total_logged,
            "fact": get_atmo_fact("satellites")}


@app.get("/api/atmo/asteroids")
async def get_asteroids() -> List[Dict[str, Any]]:
    """Near-Earth asteroids this week (NASA NeoWs)."""
    if _asteroid is None:
        return []
    try:
        return _asteroid.fetch()
    except Exception as e:
        logger.debug("asteroids endpoint error: %s", e)
        return []


@app.get("/api/atmo/satellites")
async def get_satellites() -> Dict[str, Any]:
    """Notable satellites (owner / purpose) + live passes for the bright ones."""
    if _config is None or not _config.atmo.enabled:
        return {}
    cat = catalog_list()
    passes: Dict[str, Any] = {}
    if _sat is not None:
        for norad in _config.atmo.tracked_satellites:
            try:
                p = _sat.fetch(norad)
                pl = (p or {}).get("passes") or []
                if pl:
                    passes[str(norad)] = pl
                    for pp in pl:
                        try:
                            _db.log_satellite_pass(norad, pp["start"], pp.get("peak"),
                                                   pp.get("end"), pp.get("max_elevation"))
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("sat passes %s failed: %s", norad, e)
    return {"catalog": cat, "passes": passes}


@app.get("/api/forecast")
def get_forecast() -> Dict[str, Any]:
    """Forecast view bundle: NWS periods + today's all-time record high/low
    (Open-Meteo archive, one-time build) + the most serious weather anywhere in
    the country. Sync def — the first-ever climate build takes a few seconds
    and runs in the threadpool."""
    if _weather is None:
        return {"periods": [], "climate": None, "national": []}
    out: Dict[str, Any] = {"periods": [], "climate": None, "national": []}
    try:
        out["periods"] = _weather.fetch_forecast()
    except Exception as e:
        logger.debug("forecast endpoint error: %s", e)
    try:
        out["climate"] = _weather.fetch_climate_record()
    except Exception as e:
        logger.debug("climate record error: %s", e)
    try:
        out["national"] = _weather.fetch_national_extremes()
    except Exception as e:
        logger.debug("national extremes error: %s", e)
    try:
        out["alerts"] = _weather.fetch_alerts(_config.marine.nws_marine_zone) if _config else []
    except Exception:
        out["alerts"] = []
    try:
        out["hourly"] = _weather.fetch_hourly()
    except Exception as e:
        logger.debug("hourly endpoint error: %s", e)
        out["hourly"] = []
    if _config is not None:
        out["home"] = {"lat": _config.location.lat, "lon": _config.location.lon}
    return out


@app.get("/api/alerts")
async def get_alerts() -> List[Dict[str, Any]]:
    """Active NWS weather + marine advisories/warnings for the heading."""
    if _weather is None:
        return []
    zone = _config.marine.nws_marine_zone if _config else ""
    try:
        return _weather.fetch_alerts(zone)
    except Exception as e:
        logger.debug("alerts endpoint error: %s", e)
        return []


@app.get("/api/tide")
async def get_tide() -> Optional[Dict[str, Any]]:
    """Current tide data from NOAA for Long Island Sound."""
    try:
        return _tide.fetch()
    except Exception as e:
        logger.debug("Tide endpoint error: %s", e)
        return None


_STARTED_AT = time.time()


def _code_version() -> Dict[str, Any]:
    """Newest source-file mtime — proves which code build is actually running.
    The deploy script compares this against the files it just transferred."""
    newest, newest_file = 0.0, ""
    for pattern in ("*.py", "static/js/*.js", "static/css/*.css", "templates/*.html"):
        for p in BASE_DIR.glob(pattern):
            try:
                m = p.stat().st_mtime
                if m > newest:
                    newest, newest_file = m, str(p.relative_to(BASE_DIR))
            except OSError:
                pass
    return {"code_mtime": int(newest), "newest_file": newest_file,
            "code_mtime_str": datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M:%S") if newest else ""}


@app.get("/api/health")
async def get_health() -> Dict[str, Any]:
    """Diagnostic health check — shows receiver status, source stats, etc."""
    result: Dict[str, Any] = {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "database": _db is not None,
        "receiver": None,
        "location": {
            "name": _config.location.name,
            "lat": _config.location.lat,
            "lon": _config.location.lon,
        },
        "uptime_seconds": int(time.time() - _STARTED_AT),
        "started_at": datetime.fromtimestamp(_STARTED_AT).strftime("%Y-%m-%d %H:%M:%S"),
        "version": _code_version(),
        "db_size_bytes": _db.get_db_size_bytes() if _db else 0,
    }

    if _receiver:
        try:
            result["receiver"] = _receiver.get_health()
        except Exception as e:
            result["receiver"] = {"error": str(e)}
    else:
        result["receiver"] = {"error": "Receiver not initialized"}

    if _ais:
        try:
            result["marine"] = _ais.get_health()
        except Exception as e:
            result["marine"] = {"error": str(e)}

    if _db:
        try:
            stats = _db.get_stats()
            result["database_stats"] = {
                "total_aircraft": stats.get("total_aircraft", 0),
                "total_detections": stats.get("total_detections", 0),
            }
        except Exception as e:
            result["database_stats"] = {"error": str(e)}

    return result


@app.get("/api/marine")
async def get_marine() -> Optional[Dict[str, Any]]:
    """Marine conditions from Stormglass.io — water temp, wave height, sea state.
    30-minute cache (10 free calls/day budget)."""
    if _stormglass is None:
        return None
    return _stormglass.fetch()


@app.get("/api/photo/{hex_code}")
def get_photo(hex_code: str):
    """Image proxy: returns the aircraft's photo bytes through localhost.

    Resolves the photo URL (stored, else Planespotters, else AeroDataBox) and
    streams the image itself, so it works even if the kiosk browser can't reach
    external image hosts. 404 -> the front-end falls back to the SVG icon.
    Defined as a sync def so FastAPI runs the blocking fetch in a threadpool.
    """
    hex_code = hex_code.upper().strip()

    cached = _photo_cache.get(hex_code, "MISS")
    if cached != "MISS":
        if not cached:
            return Response(status_code=404)
        ct, data = cached
        return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=604800"})

    af = _db.get_airframe(hex_code) if _db else None
    reg = (af.get("registration") if af else "") or ""
    url = af.get("photo_url") if af else None
    if not url and not _disk_get("aircraft", hex_code):
        url, credit = _resolve_aircraft_photo(hex_code, reg)
        if url and af:
            _db.update_airframe(hex_code, photo_url=url, photo_credit=credit or None)

    result = _cached_image("aircraft", hex_code, url)
    if len(_photo_cache) > 800:
        _photo_cache.clear()
    _photo_cache[hex_code] = result
    if not result:
        return Response(status_code=404)
    ct, data = result
    return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/model-photo/{type_code}")
def get_model_photo(type_code: str):
    """Generic photo of an aircraft *type* (a representative airframe of that
    model we already have a photo for) — used as the fallback when we have no
    photo of the specific tail. 404 -> caller falls back to icon."""
    tc = type_code.upper().strip()
    cached = _model_photo_cache.get(tc, "MISS")
    if cached != "MISS":
        if not cached:
            return Response(status_code=404)
        ct, data = cached
        return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=604800"})

    url = None
    if not _disk_get("model", tc):
        url = _db.get_photo_for_type(tc) if _db else None
        if not url:
            # Nothing in the collection yet — try a generic Wikipedia model photo.
            specs = get_specs(tc)
            if specs and specs.get("name"):
                url = _wikipedia.image_for(specs["name"])

    result = _cached_image("model", tc, url)
    if len(_model_photo_cache) > 600:
        _model_photo_cache.clear()
    _model_photo_cache[tc] = result
    if not result:
        return Response(status_code=404)
    ct, data = result
    return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/photo-vessel/{mmsi}")
def get_vessel_photo(mmsi: str):
    """Image proxy for a vessel's stored (Wikipedia) photo. 404 -> icon fallback.
    The URL is resolved + stored when the vessel detail is first opened."""
    mmsi = str(mmsi).strip()
    cached = _vessel_photo_cache.get(mmsi, "MISS")
    if cached != "MISS":
        if not cached:
            return Response(status_code=404)
        ct, data = cached
        return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=604800"})

    vessel = _db.get_vessel(mmsi) if _db else None
    url = vessel.get("photo_url") if vessel else None
    result = _cached_image("vessel", mmsi, url)
    if len(_vessel_photo_cache) > 600:
        _vessel_photo_cache.clear()
    _vessel_photo_cache[mmsi] = result
    if not result:
        return Response(status_code=404)
    ct, data = result
    return Response(content=data, media_type=ct, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/aircraft-photo/{hex_code}")
async def get_aircraft_photo(hex_code: str) -> Dict[str, Any]:
    """Aircraft photo URL from Aerodatabox."""
    url = _aerodatabox.lookup_aircraft_photo(hex_code)
    return {"hex": hex_code.upper(), "photo_url": url}


@app.get("/api/aircraft-info/{hex_code}")
async def get_aircraft_info(hex_code: str) -> Dict[str, Any]:
    """Aircraft registration, type, operator from Aerodatabox."""
    return _aerodatabox.lookup_aircraft_info(hex_code)


@app.get("/api/acars/plane/{hex_code}")
async def get_acars_for_plane(hex_code: str, reg: str = "", flight: str = "",
                              n: int = 40) -> Dict[str, Any]:
    """Datalink (ACARS/VDL-2) messages for one airframe, oldest first — the
    Dex detail page renders these as a plane <-> ground chat thread. Matching
    uses the ICAO hex (VDL-2 frames carry it) plus the registration and flight
    the frontend already knows."""
    if _acars is None:
        return {"enabled": False, "messages": []}
    msgs = _acars.for_aircraft(hex_code=hex_code, reg=reg, flight=flight,
                               n=max(1, min(int(n), 200)))
    return {"enabled": True, "messages": msgs, "stats": _acars.stats}


@app.get("/api/acars/live")
async def get_acars_live(since: float = 0.0, n: int = 12) -> Dict[str, Any]:
    """Fresh datalink messages matched to planes currently in range — the map
    pops these up as transient word bubbles next to the plane markers. Pass the
    `now` from the previous call as `since` to get only what's new."""
    now = time.time()
    if _acars is None or _receiver is None:
        return {"enabled": False, "bubbles": [], "now": now}
    cutoff = since if since > 0 else now - 30
    msgs = [m for m in _acars.recent(60) if m["ts"] > cutoff]
    if not msgs:
        return {"enabled": True, "bubbles": [], "now": now}

    def reg_of(hx: str) -> str:
        # Registration for a live hex, via the Dex DB (tiny cache: regs don't change).
        if hx not in _acars_reg_cache:
            if len(_acars_reg_cache) > 500:
                _acars_reg_cache.clear()
            af = _db.get_airframe(hx) if _db else None
            _acars_reg_cache[hx] = (af or {}).get("registration") or ""
        return _acars_reg_cache[hx]

    bubbles = acars_match(msgs, _receiver.get_all_contacts() or {}, reg_of,
                          limit=max(1, min(int(n), 30)))
    return {"enabled": True, "bubbles": bubbles, "now": now}


@app.get("/api/acars/recent")
async def get_acars_recent(n: int = 30) -> Dict[str, Any]:
    """The latest datalink messages from ANY aircraft, newest first."""
    if _acars is None:
        return {"enabled": False, "messages": []}
    return {"enabled": True, "stats": _acars.stats,
            "messages": _acars.recent(max(1, min(int(n), 200)))}


@app.get("/api/api-balance")
async def get_api_balance() -> Dict[str, Any]:
    """Check remaining RapidAPI quota for Aerodatabox."""
    balance = _aerodatabox.get_api_balance()
    return balance or {"error": "Unable to fetch balance"}


@app.get("/api/badges")
async def get_badges() -> List[Dict[str, Any]]:
    """Earned badges."""
    if _db is None:
        return []
    return _db.list_badges()


@app.get("/api/facts")
async def get_facts(n: int = 3, domain: str = "air") -> List[str]:
    """Random facts for the ticker / empty state. domain='sea' returns SeaDex lore."""
    if domain == "sea":
        return get_sea_facts_for_empty_state(n)
    if domain == "atmo":
        return get_atmo_facts_for_empty_state(n)
    if domain == "land":
        return get_land_facts_for_empty_state(n)
    if domain == "ether":
        return get_ether_facts_for_empty_state(n)
    return get_facts_for_empty_state(n)


# ===========================================================================
# EtherDex — the invisible radio neighborhood
# ===========================================================================

@app.get("/api/ether")
async def get_ether() -> Dict[str, Any]:
    """Recently heard RF/Bluetooth devices + listener status. Residents (the
    Shield, the soundbar — things that live here) are flagged so the Airwaves
    view can fold them away instead of re-announcing the furniture."""
    if _ether is None:
        return {"live": [], "status": {"rtl_running": False}, "collection_count": 0}
    live = _ether.recent(20)
    try:
        residents = {d["device_key"] for d in _db.list_ether(500) if d.get("resident")}
        for v in live:
            v["resident"] = v["key"] in residents
    except Exception:
        pass
    return {"live": live, "status": _ether.status(),
            "collection_count": _db.get_ether_count() if _db else 0}


@app.get("/api/ether/collection")
async def get_ether_collection() -> List[Dict[str, Any]]:
    """The Etherdex — every device ever heard (90-day retention)."""
    if _db is None:
        return []
    return _db.list_ether()


_hamdb = None
_radio_fb = None


@app.get("/api/ham/{callsign}")
def api_ham(callsign: str) -> Dict[str, Any]:
    """HAM it Up — callsign lookup via hamdb.org (cached per call)."""
    global _hamdb
    if _hamdb is None:
        from ether import HamdbClient
        _hamdb = HamdbClient(os.environ.get("SKYDEX_RAPIDAPI_KEY", ""),
                             _config.location.lat, _config.location.lon)
    return _hamdb.lookup(callsign)


@app.post("/api/ether/retune")
async def api_ether_retune(request: Request) -> Dict[str, Any]:
    """Band chips on the Airwaves view: swap rtl_433 frequencies live."""
    data = await request.json()
    freqs = str(data.get("freqs") or "433.92M")
    settings.set_many({"ether_freqs": freqs})
    if _ether is not None:
        return {"freqs": _ether.retune(freqs)}
    return {"freqs": freqs.split(","), "note": "ether disabled"}


@app.post("/api/ether/listen")
async def api_ether_listen(request: Request) -> Dict[str, Any]:
    """Live tuner: demodulate a voice frequency to the Pi's speakers.
    Presets only — no arbitrary frequencies from the browser."""
    data = await request.json()
    if _ether is None:
        return {"error": "ether disabled"}
    return _ether.listen_live(str(data.get("preset") or ""))


@app.post("/api/ether/listen/stop")
async def api_ether_listen_stop() -> Dict[str, Any]:
    if _ether is None:
        return {"listening": None}
    return _ether.listen_stop()


# ============================================================================
# Trainer cards + games arcade
# ============================================================================
FAMILY = ["Dad", "Mom", "Kid 1", "Kid 2", "Kid 3", "Guest"]


@app.get("/api/profiles")
def api_profiles() -> Dict[str, Any]:
    return {"profiles": _db.get_profiles(FAMILY)}


@app.post("/api/profile/avatar")
async def api_profile_avatar(request: Request) -> Dict[str, Any]:
    d = await request.json()
    name = str(d.get("name") or "")
    if name not in FAMILY:
        return {"error": "unknown name"}
    _db.set_avatar(name, str(d.get("avatar") or "")[:24])
    return {"ok": True}


@app.post("/api/game/score")
async def api_game_score(request: Request) -> Dict[str, Any]:
    d = await request.json()
    name = str(d.get("name") or "")
    game = str(d.get("game") or "")[:20]
    try:
        score = float(d.get("score"))
    except (TypeError, ValueError):
        return {"error": "bad score"}
    if name not in FAMILY or not game:
        return {"error": "bad request"}
    return {"ok": True, "personal_best": _db.log_game_score(name, game, score)}


@app.get("/api/game/plane")
def api_game_plane() -> Dict[str, Any]:
    """Who's That Plane — drawn from the family's OWN photographed catches."""
    q = _db.get_plane_question()
    return q or {"error": "no photographed catches yet — the dex needs to grow first"}


_windycams = None
_windypoint = None

# Guess the Language: espeak-ng voices we allow the browser to request.
_TTS_VOICES = {"es", "fr", "de", "it", "pt", "ja", "ru", "hi", "sv", "tr", "sw", "nl"}


@app.get("/api/tts")
def api_tts(voice: str = "", text: str = "") -> Any:
    from fastapi.responses import Response
    if voice not in _TTS_VOICES or not text or len(text) > 90:
        return Response(status_code=400)
    from voice import espeak_wav
    wav = espeak_wav(voice, text)
    if not wav:
        return Response(status_code=503)
    return Response(content=wav, media_type="audio/wav")


@app.get("/api/game/timemachine")
def api_game_timemachine() -> Dict[str, Any]:
    """Weather Time Machine: same calendar date, two random years, real highs
    at OUR coordinates — which year was hotter?"""
    import random as _r
    from datetime import datetime as _dt
    if _weather is None:
        return {"error": "weather desk offline"}
    month, day = _r.randint(1, 12), _r.randint(1, 28)
    y1, y2 = _r.sample(range(1950, _dt.now().year - 1), 2)
    d1 = _weather.fetch_hist_day(f"{y1:04d}-{month:02d}-{day:02d}")
    d2 = _weather.fetch_hist_day(f"{y2:04d}-{month:02d}-{day:02d}")
    if not d1 or not d2:
        return {"error": "the time machine sputtered — spin it again"}
    # Question variety: temp always works; wind/rain/snow only when at least
    # one of the two days actually HAD some (a 0-vs-0 rain question is no fun).
    metrics = [("high", "HOTTER", "°", 0)]
    if max(d1["wind"], d2["wind"]) > 8:
        metrics.append(("wind", "WINDIER", " mph", 0))
    if max(d1["rain"], d2["rain"]) > 0.05:
        metrics.append(("rain", "RAINIER", '"', 2))
    if max(d1["snow"], d2["snow"]) > 0.3:
        metrics.append(("snow", "SNOWIER", '"', 1))
    key, ask, unit, dp = _r.choice(metrics)
    return {"date_label": _dt(2000, month, day).strftime("%B ") + str(day),
            "ask": ask, "unit": unit,
            "a": {"year": y1, "value": round(d1[key], dp) if dp else round(d1[key])},
            "b": {"year": y2, "value": round(d2[key], dp) if dp else round(d2[key])}}


@app.get("/api/ispy")
def api_ispy() -> Dict[str, Any]:
    """iSpy round: a random world webcam + decoy locations."""
    global _windycams
    if _windycams is None:
        from ispy import WindyCams
        _windycams = WindyCams(os.environ.get("SKYDEX_WINDY_KEY", ""))
    return _windycams.round()


@app.get("/api/wxgame")
def api_wxgame() -> Dict[str, Any]:
    """Daily high-temp guessing game state. Also settles any completed days
    (closest guess wins; ties share the win) and announces the winner once."""
    from datetime import datetime as _dt, timedelta as _td
    today = _dt.now().strftime("%Y-%m-%d")
    target = (_dt.now() + _td(days=1)).strftime("%Y-%m-%d")
    if _weather is not None:
        for day in _db.wx_unresolved_dates(today):
            actual = _weather.fetch_day_high(day)
            if actual is None:
                continue
            winners = _db.wx_resolve(day, actual)
            if winners:
                try:
                    from voice import announcer
                    announcer.say(
                        f"Weather game result: the high was {round(actual)} degrees. "
                        f"{' and '.join(winners)} guessed closest!",
                        "storm", dedup_key=f"wxwin{day}")
                except Exception:
                    pass
    hint = None
    try:
        days = [p for p in (_weather.fetch_forecast() or [])
                if p.get("is_daytime") is not False]
        if len(days) >= 2:
            hint = days[1].get("temp")
    except Exception:
        pass
    # The Robot Forecast-Off: rival weather models' takes on tomorrow's high.
    robots = []
    try:
        global _windypoint
        if _windypoint is None:
            from ispy import WindyPoint
            _windypoint = WindyPoint(os.environ.get("SKYDEX_WINDY_POINT_KEY", ""),
                                     _config.location.lat if _config else 41.1635,
                                     _config.location.lon if _config else -73.1262)
        robots = _windypoint.tomorrow_highs()
    except Exception as e:
        logger.debug("forecast robots failed: %s", e)
    return {"target_date": target, "hint": hint, "family": FAMILY, "robots": robots,
            "guesses": {g["name"]: g["guess"] for g in _db.wx_guesses_for(target)},
            "last_result": _db.wx_last_result()}


@app.post("/api/wxgame/guess")
async def api_wxgame_guess(request: Request) -> Dict[str, Any]:
    from datetime import datetime as _dt, timedelta as _td
    d = await request.json()
    name = str(d.get("name") or "")
    try:
        temp = float(d.get("temp"))
    except (TypeError, ValueError):
        return {"error": "bad temp"}
    if name not in FAMILY or not (-30 <= temp <= 130):
        return {"error": "bad request"}
    target = (_dt.now() + _td(days=1)).strftime("%Y-%m-%d")
    _db.wx_guess(target, name, temp)
    return {"ok": True, "target_date": target}


# ============================================================================
# Journeys — follow a tagged plane/vessel beyond the home radius
# ============================================================================
@app.post("/api/follow")
async def api_follow(request: Request) -> Dict[str, Any]:
    data = await request.json()
    kind = str(data.get("kind") or "")
    craft_id = str(data.get("id") or "").strip()
    if kind not in ("air", "sea") or not craft_id:
        return {"error": "need kind ('air'|'sea') and id"}
    res = _db.follow_craft(kind, craft_id, str(data.get("name") or "") or None)
    logger.info("follow request: %s %s -> %s", kind, craft_id, res)
    if res.get("ok") and _journeys is not None:
        _journeys.poke()                 # first fix within seconds, not minutes
    return res


@app.post("/api/unfollow")
async def api_unfollow(request: Request) -> Dict[str, Any]:
    data = await request.json()
    _db.unfollow_craft(str(data.get("kind") or ""), str(data.get("id") or "").strip())
    return {"ok": True}


@app.get("/api/journeys")
def api_journeys() -> Dict[str, Any]:
    """Everything the Journeys view needs: followed craft + their trails."""
    now = time.time()
    out = []
    for f in _db.list_followed():
        trail = _db.get_journey(f["id"], limit=800)
        status = "waiting"
        if f.get("last_seen"):
            age = now - f["last_seen"]
            status = "live" if age < 1800 else "dark"
        dist = None
        if f.get("last_lat") is not None and _config is not None:
            dist = round(_haversine_mi(_config.location.lat, _config.location.lon,
                                       f["last_lat"], f["last_lon"]), 1)
        out.append(dict(f, trail=[[p["lat"], p["lon"]] for p in trail
                                  if p["lat"] is not None],
                        status=status, miles_from_home=dist))
    return {"followed": out,
            "home": {"lat": _config.location.lat if _config else 41.1635,
                     "lon": _config.location.lon if _config else -73.1262},
            "sea_enabled": bool(_journeys is not None and getattr(_journeys, "ais_key", ""))}


@app.get("/api/radio/fallback")
def api_radio_fallback() -> List[Dict[str, Any]]:
    """World Radio backup stations (keyed APIs, heavily cached) — used only
    when the free Radio-Browser service is unreachable."""
    global _radio_fb
    if _radio_fb is None:
        from ether import RadioFallbackClient
        _radio_fb = RadioFallbackClient(os.environ.get("SKYDEX_RAPIDAPI_KEY", ""))
    return _radio_fb.random_stations()


@app.post("/api/admin/say")
async def api_admin_say(request: Request) -> Dict[str, Any]:
    """Test the voice: POST {"text": "..."}."""
    from voice import announcer
    data = await request.json()
    text = str(data.get("text") or "SkyDex voice check. All systems nominal.")
    announcer.say(text, category="air", dedup_seconds=0)
    return {"spoken": True, "engine": announcer.engine}


# ===========================================================================
# LandDex — trains (Stratford schedule board + live Amtrak + Traindex)
# ===========================================================================

@app.get("/api/land")
def get_land() -> Dict[str, Any]:
    """Board + passing trains + collection size. Sync def: the first call of
    the day may parse the GTFS zip (a second or two) in the threadpool."""
    if _land is None:
        return {"board": {"have_schedule": False}, "passing": [], "collection_count": 0}
    return _land.snapshot()


@app.get("/api/land/collection")
async def get_land_collection() -> List[Dict[str, Any]]:
    """The Traindex — every Amtrak train number ever logged passing."""
    if _db is None:
        return []
    return _db.list_trains()


@app.get("/api/land/road")
def get_land_road() -> Dict[str, Any]:
    """Drive times (OSRM baseline; TomTom live when a key is set in /admin)
    plus the scanner stream URL. Sync def — routing calls block briefly."""
    if _land is None:
        return {"commutes": []}
    tomtom = str(settings.get("tomtom_key"))
    commutes = _land.road.commutes(tomtom)

    # Train vs car: same station, next train's ride time vs the drive.
    tvc = []
    try:
        rides = _land.gtfs.next_rides()
        cars = _land.road.tvc_drives(tomtom)
        for name, _lat, _lon in TVC_TARGETS:
            train = rides.get(name)
            car = cars.get(name) or {}
            tvc.append({"name": name,
                        "train_min": train["minutes"] if train else None,
                        "train_depart": train["depart"] if train else None,
                        "car_min": car.get("minutes")})
    except Exception as e:
        logger.debug("train-vs-car failed: %s", e)

    return {
        "commutes_to": commutes.get("to", []),
        "commutes_from": commutes.get("from", []),
        "train_vs_car": tvc,
        "scanner_url": str(settings.get("road_scanner_url")),
        "live_traffic": bool(tomtom.strip()),
        "incidents": _land.waze.incidents(),
        "nyc_speeds": _land.nycdot.speeds() if settings.get("nycdot_speeds_enabled") else [],
        "news": _land.road_news.headlines(5),
    }


@app.get("/api/land/stations")
def get_land_stations() -> List[Dict[str, Any]]:
    """Every Metro-North station (coords + line) for the tappable map."""
    if _land is None:
        return []
    return _land.gtfs.stations()


@app.get("/api/land/journey")
def get_land_journey(to: str) -> Dict[str, Any]:
    """Trip plan: Stratford -> the tapped station, leaving now (CSA over
    today's GTFS timetable, transfers included)."""
    if _land is None:
        return {"error": "landdex disabled"}
    return _land.gtfs.journey(to)


@app.get("/api/land/live")
def get_land_live() -> Dict[str, Any]:
    """Live Metro-North train positions (MTA GTFS-RT, decoded natively).
    Sync def — the fetch blocks briefly; 25s server-side cache."""
    if _land is None:
        return {"trains": []}
    trains = [dict(t, kind="mnr") for t in
              _land.live.trains(str(settings.get("mta_rt_url")),
                                str(settings.get("mta_api_key")))]
    # Amtrak rides the same map: bullet-train icons, gold for Acelas.
    try:
        for t in _land.amtrak.region(120):
            trains.append({"kind": "amtrak", "lat": t["lat"], "lon": t["lon"],
                           "line": t["route"], "label": t["train_num"],
                           "speed_mph": t.get("speed_mph"),
                           "acela": "acela" in (t["route"] or "").lower()})
    except Exception as e:
        logger.debug("amtrak on live map failed: %s", e)
    return {"trains": trains, "updated": time.time()}


@app.get("/api/land/history")
def get_land_history() -> Dict[str, Any]:
    """The Grand Central view: all-lines GCT departure board, next trains
    Stratford<->GCT both ways, and Metro-North news. (History timeline cards
    are static content in the frontend.)"""
    if _land is None:
        return {"news": [], "gct": {"board": [], "to_gct": None, "from_gct": None}}
    return {"news": _land.news.headlines(), "gct": _land.gtfs.gct_snapshot()}


# -- WebSocket for live updates ---------------------------------------------

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            if _receiver:
                contacts = _visible_contacts()
                await websocket.send_json({
                    "count": len(contacts),
                    "contacts": contacts[:20],  # Max 20
                    "timestamp": datetime.now().isoformat(),
                })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket error: %s", e)


# ===========================================================================
# Runtime settings + admin controls
# ===========================================================================

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Control panel — open from any browser on the LAN (phone, PC, kiosk)."""
    return _template_response(request, "admin.html", {"v": STATIC_VERSION})


@app.get("/api/settings")
async def api_settings() -> Dict[str, Any]:
    """Current runtime settings (frontend polls this once per view load)."""
    return settings.client_values()


@app.get("/api/settings/admin")
async def api_settings_admin() -> Dict[str, Any]:
    """Settings + spec (labels, groups, help) for the admin form."""
    return settings.as_admin_payload()


@app.post("/api/settings")
async def api_settings_save(request: Request) -> Dict[str, Any]:
    data = await request.json()
    if not isinstance(data, dict):
        return {"applied": {}, "errors": {"_": "body must be a JSON object"}}
    result = settings.set_many(data)
    logger.info("settings updated via admin: %s", list(result["applied"].keys()))
    return result


@app.post("/api/admin/restart")
async def api_admin_restart() -> Dict[str, Any]:
    """Exit the process; systemd (Restart=on-failure) brings it back with fresh
    code + config. Under manual launch this just stops the server."""
    logger.warning("Restart requested via admin page")
    threading.Timer(0.7, os._exit, args=(3,)).start()
    return {"restarting": True}


@app.post("/api/admin/backup")
async def api_admin_backup() -> Dict[str, Any]:
    """Kick off scripts/backup.sh in the background (needs rclone configured)."""
    script = BASE_DIR / "scripts" / "backup.sh"
    if not script.exists():
        return {"started": False, "error": "scripts/backup.sh not found"}
    try:
        subprocess.Popen(["/bin/bash", str(script)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"started": True}
    except OSError as e:
        return {"started": False, "error": str(e)}


@app.post("/api/admin/maintenance")
async def api_admin_maintenance() -> Dict[str, Any]:
    """Run DB retention/checkpoint right now (also runs nightly on its own)."""
    if _db is None:
        return {"error": "no db"}
    return _db.run_maintenance(int(settings.get("detections_retention_days")))


# ===========================================================================
# Hall of Fame — records, achievements, almanac, quiz
# ===========================================================================

@app.get("/api/records")
async def api_records() -> Dict[str, Any]:
    if _db is None:
        return {"air": {}, "sea": {}}
    rec = _db.get_records()
    try:
        rec["spotters"] = _db.get_spotter_board()
    except Exception:
        rec["spotters"] = []
    return rec


@app.post("/api/spotter")
async def api_spotter(request: Request) -> Dict[str, Any]:
    """Who called the rare catch — family leaderboard credit."""
    data = await request.json()
    name = str(data.get("name") or "").strip()
    if _db is None or not name:
        return {"ok": False}
    _db.log_spotter(name, str(data.get("kind") or "air"), str(data.get("ident") or ""))
    return {"ok": True}


@app.get("/api/challenges")
def api_challenges() -> Dict[str, Any]:
    """Daily + weekly challenges — reset themselves at midnight / Sunday."""
    from challenges import compute_challenges
    if _db is None:
        return {"daily": [], "weekly": []}
    return compute_challenges(_db.get_challenge_stats())


@app.get("/api/achievements")
async def api_achievements() -> List[Dict[str, Any]]:
    if _db is None:
        return []
    achievements = compute_achievements(_db.get_achievement_stats())
    # Stamp first-unlock dates (persisted, so the popup can say "earned Jul 1").
    try:
        earned = _db.record_achievement_unlocks(
            [a["id"] for a in achievements if a["unlocked"]])
        for a in achievements:
            if a["unlocked"]:
                a["earned_at"] = earned.get(a["id"])
    except Exception as e:
        logger.debug("achievement unlock stamping failed: %s", e)
    return achievements


@app.get("/api/almanac")
async def api_almanac(days: int = 7) -> Dict[str, Any]:
    if _db is None:
        return {}
    return _db.get_almanac(max(1, min(days, 31)))


@app.get("/api/quiz")
async def api_quiz(n: int = 5, domain: str = "all") -> List[Dict[str, Any]]:
    return get_quiz(max(1, min(n, 10)), domain)


# ===========================================================================
# Map extras — route coordinates + day replay
# ===========================================================================

@app.get("/api/route-coords/{hex_code}")
async def api_route_coords(hex_code: str) -> Dict[str, Any]:
    """Origin/destination airport coordinates for an aircraft's current flight
    (from its latest sighting) — used to draw the route line on the map."""
    if _db is None:
        return {}
    s = _db.get_last_sighting(hex_code.upper())
    if not s:
        return {}

    def _pt(code):
        if not code or _airports is None:
            return None
        info = _airports.resolve(code)
        if not info or info.get("latitude") is None:
            return None
        return {"code": code, "lat": info["latitude"], "lon": info["longitude"],
                "label": _airport_label(code)}

    return {"origin": _pt(s.get("origin_airport")), "dest": _pt(s.get("dest_airport")),
            "callsign": s.get("callsign")}


@app.get("/api/replay")
async def api_replay(day: Optional[str] = None) -> Dict[str, Any]:
    """Aircraft tracks for a local date (default today) for time-lapse replay."""
    if _db is None:
        return {"tracks": []}
    return _db.get_replay(day)


@app.get("/api/airport-board")
def api_airport_board(icao: str = "KBDR") -> Dict[str, Any]:
    """KBDR ops board: scheduled movements (AeroDataBox FIDS, cached 6h) merged
    with traffic WE actually observed to/from the field (free, always fresh).
    Sync def so the blocking FIDS fetch runs in FastAPI's threadpool."""
    icao = icao.upper().strip()
    observed = _db.get_airport_movements(icao) if _db else {"departures": [], "arrivals": []}
    sched = {"departures": [], "arrivals": []}
    try:
        sched = _aerodatabox.airport_board(icao)
    except Exception as e:
        logger.debug("airport board FIDS failed: %s", e)

    def merge(kind: str):
        obs = observed.get(kind, [])
        seen_idents = {(o.get("ident") or "").strip().upper() for o in obs}
        extra = [s for s in sched.get(kind, [])
                 if (s.get("ident") or "").strip().upper() not in seen_idents]
        return obs + extra

    return {
        "icao": icao,
        "airport": _config.location.home_airport_name if _config else icao,
        "departures": merge("departures"),
        "arrivals": merge("arrivals"),
        "generated": time.time(),
    }


# ===========================================================================
# Sun times (lightweight, for auto night-dim) + SSE live stream
# ===========================================================================

@app.get("/api/sun")
async def api_sun() -> Dict[str, Any]:
    """Just today's sun/twilight times — cheap enough to poll hourly."""
    st = sun_times(_config.location.lat, _config.location.lon)
    st["now"] = time.time()
    return st


@app.get("/api/stream")
async def api_stream(request: Request):
    """Server-Sent Events: pushes live contacts + vessels once a second so the
    kiosk doesn't have to poll. The frontend falls back to polling if this
    drops or sse_enabled is off."""
    async def gen():
        while True:
            if await request.is_disconnected():
                return
            try:
                payload = {
                    "contacts": await get_contacts(),
                    "vessels": (await get_vessels()) if _ais is not None else [],
                    "ts": time.time(),
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:  # keep the stream alive through blips
                logger.debug("SSE payload error: %s", e)
                yield ": keepalive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
