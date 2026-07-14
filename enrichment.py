"""SkyDex enrichment pipeline — fills in the blanks for each aircraft.

Fetches from:
  - adsbdb.com : callsign→route, hex→reg/type/operator/photo
  - NWS api.weather.gov : local weather
  - Open-Meteo : weather fallback

All fetches use urllib (no external deps) with in-memory caching.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class _Cache:
    """Simple TTL cache."""
    def __init__(self, ttl_seconds: float = 86400):
        self._ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        if key in self._store:
            ts, value = self._store[key]
            if time.time() - ts < self._ttl:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# adsbdb.com — free aircraft data enrichment
# ---------------------------------------------------------------------------

class AdsbdbClient:
    """Client for adsbdb.com — free aircraft/route lookups. No key needed."""

    BASE = "https://api.adsbdb.com/v0"
    TIMEOUT = 10

    def __init__(self):
        self._cache = _Cache(ttl_seconds=86400)  # 24h for aircraft metadata
        self._route_cache = _Cache(ttl_seconds=3600)  # 1h for routes

    def lookup_hex(self, hex_code: str) -> Dict[str, Any]:
        """Look up aircraft by ICAO 24-bit hex. Returns enrichment dict.

        adsbdb wraps its payload in a top-level ``response`` object::

            {"response": {"aircraft": {"icao_type": "B39M", "type": "737MAX 9",
             "manufacturer": "Boeing", "registration": "N37522",
             "registered_owner": "United Airlines", "url_photo": null, ...}}}
        """
        hex_code = hex_code.upper().strip()
        cached = self._cache.get(f"hex:{hex_code}")
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE}/aircraft/{hex_code}"
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            aircraft = (data.get("response") or {}).get("aircraft", {})
            if not aircraft:
                self._cache.set(f"hex:{hex_code}", {})  # cache the miss
                return {}

            # adsbdb returns a list sometimes
            if isinstance(aircraft, list) and aircraft:
                aircraft = aircraft[0]

            result = {
                "registration": aircraft.get("registration"),
                "type_code": aircraft.get("icao_type"),
                "model": aircraft.get("type"),
                "manufacturer": aircraft.get("manufacturer"),
                "operator": aircraft.get("registered_owner"),
                "photo_url": aircraft.get("url_photo") or aircraft.get("url_photo_thumbnail"),
            }
            # Filter out Nones / empty strings
            result = {k: v for k, v in result.items() if v}
            self._cache.set(f"hex:{hex_code}", result)
            logger.debug("adsbdb hex lookup OK for %s", hex_code)
            return result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                self._cache.set(f"hex:{hex_code}", {})  # not in adsbdb — don't keep retrying
            else:
                logger.debug("adsbdb hex lookup HTTP %d for %s", e.code, hex_code)
            return {}
        except Exception as e:
            logger.debug("adsbdb hex lookup failed for %s: %s", hex_code, e)
            return {}

    def lookup_callsign(self, callsign: str) -> Dict[str, str]:
        """Look up route by callsign. Returns origin/destination ICAO + names.

        adsbdb shape::

            {"response": {"flightroute": {
                "origin": {"icao_code": "KJFK", "name": "John F Kennedy ..."},
                "destination": {"icao_code": "KLAX", "name": "Los Angeles ..."}}}}
        """
        callsign = callsign.upper().strip()
        if not callsign:
            return {}

        cached = self._route_cache.get(f"cs:{callsign}")
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE}/callsign/{callsign}"
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            route = (data.get("response") or {}).get("flightroute", {})
            if not route:
                self._route_cache.set(f"cs:{callsign}", {})
                return {}

            result = {}
            origin = route.get("origin") or {}
            if origin:
                result["origin_airport"] = origin.get("name", "")
                result["origin_icao"] = origin.get("icao_code", "")
                result["origin_iata"] = origin.get("iata_code", "")
                result["origin_city"] = origin.get("municipality", "")
                result["origin_country"] = origin.get("country_name", "")
            dest = route.get("destination") or {}
            if dest:
                result["dest_airport"] = dest.get("name", "")
                result["dest_icao"] = dest.get("icao_code", "")
                result["dest_iata"] = dest.get("iata_code", "")
                result["dest_city"] = dest.get("municipality", "")
                result["dest_country"] = dest.get("country_name", "")
            airline = route.get("airline") or {}
            if airline:
                result["airline_name"] = airline.get("name", "")
                result["airline_iata"] = airline.get("iata", "")
                result["airline_icao"] = airline.get("icao", "")

            # Drop empties so callers can use truthiness checks.
            result = {k: v for k, v in result.items() if v}
            self._route_cache.set(f"cs:{callsign}", result)
            return result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                self._route_cache.set(f"cs:{callsign}", {})  # unknown route — cache the miss
            else:
                logger.debug("adsbdb callsign lookup HTTP %d for %s", e.code, callsign)
            return {}
        except Exception as e:
            logger.debug("adsbdb callsign lookup failed for %s: %s", callsign, e)
            return {}


# ---------------------------------------------------------------------------
# Local reference databases — FAA registry + OpenSky aircraft DB
# ---------------------------------------------------------------------------

class LocalDbClient:
    """Offline aircraft enrichment from locally-synced databases.

    Populated by ``sync_faa_db.py`` (US registry, great for N-numbered GA) and
    ``sync_opensky_db.py`` (global, includes ICAO type codes). These are fast,
    offline, and have no rate limits, so they are the preferred enrichment
    source — the adsbdb API is only used when a hex isn't found locally.

    Only returns keys that map to columns on the ``airframes`` table:
    registration, type_code, model, manufacturer, operator, photo_url.
    """

    def __init__(self, faa_db_path: str = "", opensky_db_path: str = ""):
        self.faa_db_path = os.path.expanduser(faa_db_path) if faa_db_path else ""
        self.opensky_db_path = os.path.expanduser(opensky_db_path) if opensky_db_path else ""
        self._cache = _Cache(ttl_seconds=86400)
        self._warned = False

    def available(self) -> bool:
        return bool(
            (self.faa_db_path and os.path.exists(self.faa_db_path))
            or (self.opensky_db_path and os.path.exists(self.opensky_db_path))
        )

    def lookup_hex(self, hex_code: str) -> Dict[str, Any]:
        hex_code = hex_code.upper().strip()
        if not hex_code:
            return {}
        cached = self._cache.get(f"local:{hex_code}")
        if cached is not None:
            return cached

        result: Dict[str, Any] = dict(self._lookup_faa(hex_code))
        # Fill any gaps (and the ICAO type code) from the OpenSky DB.
        for key, value in self._lookup_opensky(hex_code).items():
            if value and not result.get(key):
                result[key] = value

        self._cache.set(f"local:{hex_code}", result)
        return result

    def _lookup_faa(self, hex_code: str) -> Dict[str, Any]:
        if not (self.faa_db_path and os.path.exists(self.faa_db_path)):
            return {}
        try:
            conn = sqlite3.connect(self.faa_db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT m.n_number, m.name, m.kit_model, m.kit_mfr, m.year_mfr,
                          r.mfr AS mfr, r.model AS model
                   FROM faa_master m
                   LEFT JOIN faa_acftref r ON m.mfr_mdl_code = r.code
                   WHERE m.mode_s_code_hex = ?""",
                (hex_code,),
            ).fetchone()
            conn.close()
        except sqlite3.Error as e:
            logger.debug("FAA db lookup failed for %s: %s", hex_code, e)
            return {}

        if not row:
            return {}

        reg = (row["n_number"] or "").strip()
        if reg and not reg.upper().startswith("N"):
            reg = "N" + reg
        result = {
            "registration": reg or None,
            "model": (row["model"] or row["kit_model"] or "").strip() or None,
            "manufacturer": (row["mfr"] or row["kit_mfr"] or "").strip() or None,
            "operator": (row["name"] or "").strip() or None,
            "year_built": (row["year_mfr"] or "").strip() or None,
        }
        return {k: v for k, v in result.items() if v}

    def _lookup_opensky(self, hex_code: str) -> Dict[str, Any]:
        if not (self.opensky_db_path and os.path.exists(self.opensky_db_path)):
            return {}
        try:
            conn = sqlite3.connect(self.opensky_db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM opensky_aircraft WHERE icao24 = ?", (hex_code,)
            ).fetchone()
            conn.close()
        except sqlite3.Error as e:
            logger.debug("OpenSky db lookup failed for %s: %s", hex_code, e)
            return {}

        if not row:
            return {}

        result = {
            "registration": row["registration"],
            "type_code": row["typecode"],
            "model": row["model"],
            "manufacturer": row["manufacturername"],
            "operator": row["operator"] or row["owner"],
            "year_built": ((row["built"] or "")[:4] or None) if "built" in row.keys() else None,
        }
        return {k: v for k, v in result.items() if v}


class PlanespottersClient:
    """Free Planespotters photo API (no key) — a real photo of the specific
    airframe by ICAO hex or registration. Photos are crowdsourced; their terms
    ask for attribution, which the photo links back to on planespotters.net.
    """

    BASE = "https://api.planespotters.net/pub/photos"
    TIMEOUT = 10

    def __init__(self):
        self._cache = _Cache(ttl_seconds=604800)  # 7 days

    def lookup_photo_info(self, hex_code: str, reg: str = "") -> Optional[Dict[str, Any]]:
        """Return {url, photographer, link} for the airframe, or None."""
        hex_code = (hex_code or "").upper().strip()
        cache_key = f"ps:{hex_code}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached or None

        # Planespotters stores hex in lowercase.
        info = self._fetch(f"{self.BASE}/hex/{hex_code.lower()}") if hex_code else {}
        if not info and reg:
            info = self._fetch(f"{self.BASE}/reg/{reg.upper().strip()}")

        self._cache.set(cache_key, info or {})
        return info or None

    def lookup_photo(self, hex_code: str, reg: str = "") -> Optional[str]:
        info = self.lookup_photo_info(hex_code, reg)
        return info.get("url") if info else None

    def _fetch(self, url: str) -> Dict[str, Any]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            photos = data.get("photos") or []
            if photos:
                p = photos[0]
                for key in ("thumbnail_large", "thumbnail"):
                    t = p.get(key)
                    if isinstance(t, dict) and t.get("src"):
                        return {"url": t["src"], "photographer": p.get("photographer") or "",
                                "link": p.get("link") or ""}
            return {}
        except Exception as e:
            logger.debug("Planespotters fetch failed (%s): %s", url, e)
            return {}


class WikipediaImageClient:
    """Fetch a representative image for an aircraft *model* from Wikipedia.

    Used as a generic 'model photo' fallback when we don't yet have a photo of
    the specific tail OR any same-type airframe. Wikipedia lead images are
    CC/public-domain (attribution lives on the Wikipedia page).
    """

    BASE = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    TIMEOUT = 8

    def __init__(self):
        self._cache = _Cache(ttl_seconds=604800)  # 7 days

    def image_for(self, title: str) -> Optional[str]:
        if not title:
            return None
        cached = self._cache.get(f"wiki:{title}")
        if cached is not None:
            return cached or None
        url = ""
        try:
            import urllib.parse
            req = urllib.request.Request(
                self.BASE + urllib.parse.quote(title.replace(" ", "_")),
                headers={"User-Agent": "SkyDex/1.0 (personal aircraft-spotting kiosk)"},
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            thumb = data.get("thumbnail") or {}
            url = thumb.get("source") or (data.get("originalimage") or {}).get("source") or ""
        except Exception as e:
            logger.debug("Wikipedia image lookup failed for %s: %s", title, e)
        self._cache.set(f"wiki:{title}", url)
        return url or None

    def summary_for(self, title: str) -> Optional[Dict[str, Any]]:
        """A short Wikipedia summary ({extract, url}) for a specific subject
        (e.g. a named ship). None if there's no matching page."""
        if not title:
            return None
        cached = self._cache.get(f"wikisum:{title}")
        if cached is not None:
            return cached or None
        info: Dict[str, Any] = {}
        try:
            import urllib.parse
            req = urllib.request.Request(
                self.BASE + urllib.parse.quote(title.replace(" ", "_")),
                headers={"User-Agent": "SkyDex/1.0 (personal spotting kiosk)"},
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            # Skip disambiguation / missing pages.
            if data.get("type") == "standard" and data.get("extract"):
                info = {
                    "extract": data.get("extract"),
                    "url": ((data.get("content_urls") or {}).get("desktop") or {}).get("page") or "",
                }
        except Exception as e:
            logger.debug("Wikipedia summary failed for %s: %s", title, e)
        self._cache.set(f"wikisum:{title}", info)
        return info or None


class JetApiClient:
    """Aircraft photos from JetPhotos via the jetapi.dev scraping API, looked up
    by registration. JetPhotos has a much larger library than Planespotters, so
    we use it to fill the gaps. Returns {url, thumbnail, photographer, link}.

    Hosted endpoint is a third-party scraper, so calls are cached for 7 days and
    every failure degrades gracefully to None.
    """

    BASE = "https://www.jetapi.dev/api"
    TIMEOUT = 12

    def __init__(self, base_url: str = ""):
        self.base = (base_url or self.BASE).rstrip("/")
        self._cache = _Cache(ttl_seconds=604800)  # 7 days

    def lookup_photo_info(self, reg: str) -> Optional[Dict[str, Any]]:
        reg = (reg or "").upper().strip()
        if not reg:
            return None
        cached = self._cache.get(f"jetapi:{reg}")
        if cached is not None:
            return cached or None

        info: Dict[str, Any] = {}
        try:
            import urllib.parse
            url = (f"{self.base}?reg={urllib.parse.quote(reg)}"
                   "&photos=1&flights=0&only_jp=true")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            images = data.get("Images") or []
            if images:
                img = images[0]
                src = img.get("Image") or img.get("Thumbnail")
                if src:
                    info = {
                        "url": src,
                        "thumbnail": img.get("Thumbnail"),
                        "photographer": img.get("Photographer"),
                        "link": img.get("Link"),
                    }
        except Exception as e:
            logger.debug("jetapi lookup failed for %s: %s", reg, e)

        self._cache.set(f"jetapi:{reg}", info)
        return info or None


class CommonsImageClient:
    """Search Wikimedia Commons for a vessel photo — by IMO number or name.
    Commons hosts huge numbers of ship photos tagged with their IMO, which is the
    most reliable free way to get a real photo of a commercial vessel.
    Returns {url, photographer, link} (license attribution included)."""

    API = "https://commons.wikimedia.org/w/api.php"
    TIMEOUT = 10

    def __init__(self):
        self._cache = _Cache(ttl_seconds=604800)  # 7 days

    def search_image(self, query: str) -> Optional[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return None
        cached = self._cache.get(f"commons:{query}")
        if cached is not None:
            return cached or None

        info: Dict[str, Any] = {}
        try:
            import urllib.parse
            params = {
                "action": "query", "format": "json",
                "generator": "search", "gsrsearch": query,
                "gsrnamespace": "6", "gsrlimit": "1",      # namespace 6 = File:
                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "800",
            }
            url = self.API + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0 (personal vessel-spotting kiosk)"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            pages = ((data.get("query") or {}).get("pages") or {})
            for page in pages.values():
                ii = page.get("imageinfo") or []
                if not ii:
                    continue
                meta = ii[0]
                src = meta.get("thumburl") or meta.get("url")
                if not src:
                    continue
                artist = ((meta.get("extmetadata") or {}).get("Artist") or {}).get("value") or ""
                artist = re.sub(r"<[^>]+>", "", artist).strip()  # strip HTML
                info = {
                    "url": src,
                    "photographer": artist or None,
                    "link": meta.get("descriptionurl") or meta.get("url"),
                }
                break
        except Exception as e:
            logger.debug("Commons search failed for %s: %s", query, e)

        self._cache.set(f"commons:{query}", info)
        return info or None


class AirportResolver:
    """Resolve an airport code (ICAO or IATA) to name / city / country.

    Backed by the locally-synced OurAirports DB (sync_airports_db.py): offline,
    comprehensive (~78k airports), and free. Returns None for unknown codes.
    """

    def __init__(self, db_path: str = ""):
        self.db_path = os.path.expanduser(db_path) if db_path else ""
        self._cache = _Cache(ttl_seconds=86400)

    def resolve(self, code: Optional[str]) -> Optional[Dict[str, Any]]:
        if not code:
            return None
        code = code.upper().strip()
        cached = self._cache.get(f"apt:{code}")
        if cached is not None:
            return cached or None
        result = self._lookup(code)
        self._cache.set(f"apt:{code}", result or {})
        return result

    def _lookup(self, code: str) -> Optional[Dict[str, Any]]:
        if not (self.db_path and os.path.exists(self.db_path)):
            return None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT a.ident, a.iata_code, a.name, a.municipality, a.iso_country,
                          a.latitude, a.longitude, c.name AS country_name
                   FROM airports a
                   LEFT JOIN airport_countries c ON a.iso_country = c.code
                   WHERE a.ident = ? OR a.iata_code = ?
                   ORDER BY (a.iata_code IS NULL) LIMIT 1""",
                (code, code),
            ).fetchone()
            conn.close()
        except sqlite3.Error as e:
            logger.debug("Airport lookup failed for %s: %s", code, e)
            return None
        if not row:
            return None

        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        return {
            "icao": row["ident"],
            "iata": row["iata_code"],
            "name": row["name"],
            "city": row["municipality"],
            "country_iso": row["iso_country"],
            "country": row["country_name"],
            "lat": _f(row["latitude"]),
            "lon": _f(row["longitude"]),
        }


# ---------------------------------------------------------------------------
# Weather — NWS api.weather.gov (primary) + Open-Meteo (fallback)
# ---------------------------------------------------------------------------

class WeatherClient:
    """Fetches local weather. Tries NWS first (US-only, no key), then Open-Meteo."""

    NWS_BASE = "https://api.weather.gov"
    OM_BASE = "https://api.open-meteo.com/v1"
    TIMEOUT = 10

    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        self._cache = _Cache(ttl_seconds=300)  # 5 min weather cache

    def fetch(self) -> Optional[Dict[str, Any]]:
        """Get current weather. Returns dict or None."""
        cache_key = f"wx:{self.lat:.3f}:{self.lon:.3f}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        result = self._fetch_nws()
        if not result:
            result = self._fetch_openmeteo()

        if result:
            self._cache.set(cache_key, result)
        return result

    def _fetch_nws(self) -> Optional[Dict[str, Any]]:
        """Fetch from NWS api.weather.gov (US only, no key)."""
        try:
            # Step 1: get grid point for lat/lon
            url = f"{self.NWS_BASE}/points/{self.lat:.4f},{self.lon:.4f}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "SkyDex/1.0 (skydex@localhost)",
            })
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                point_data = json.load(resp)

            props = point_data.get("properties", {})
            forecast_url = props.get("forecast")
            if not forecast_url:
                return None

            # Step 2: get forecast
            req2 = urllib.request.Request(forecast_url, headers={
                "User-Agent": "SkyDex/1.0 (skydex@localhost)",
            })
            with urllib.request.urlopen(req2, timeout=self.TIMEOUT) as resp2:
                forecast = json.load(resp2)

            periods = forecast.get("properties", {}).get("periods", [])
            if not periods:
                return None

            current = periods[0]
            return {
                "temp_f": current.get("temperature"),
                "condition": current.get("shortForecast", ""),
                "wind_speed": current.get("windSpeed", ""),
                "wind_direction": current.get("windDirection", ""),
                "humidity_pct": current.get("relativeHumidity", {}).get("value") if isinstance(current.get("relativeHumidity"), dict) else None,
                "source": "nws",
            }

        except Exception as e:
            logger.debug("NWS fetch failed: %s", e)
            return None

    def _fetch_openmeteo(self) -> Optional[Dict[str, Any]]:
        """Fetch from Open-Meteo (global, no key)."""
        try:
            url = (
                f"{self.OM_BASE}/forecast"
                f"?latitude={self.lat}&longitude={self.lon}"
                f"&current=temperature_2m,weather_code,wind_speed_10m,wind_direction_10m,relative_humidity_2m"
                f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            cur = data.get("current", {})
            return {
                "temp_f": cur.get("temperature_2m"),
                "condition": self._decode_weather_code(cur.get("weather_code")),
                "wind_speed": f"{cur.get('wind_speed_10m', 0):.0f} mph",
                "wind_direction": f"{cur.get('wind_direction_10m', 0):.0f} deg",
                "humidity_pct": cur.get("relative_humidity_2m"),
                "source": "openmeteo",
            }

        except Exception as e:
            logger.debug("Open-Meteo fetch failed: %s", e)
            return None

    def fetch_alerts(self, marine_zone: str = "") -> List[Dict[str, Any]]:
        """Active NWS alerts: weather advisories for our point + marine
        advisories/warnings for the marine zone (Small Craft Advisory, Gale
        Warning, etc.). Returns a de-duplicated list, cached 5 minutes."""
        ck = f"alerts:{self.lat:.3f}:{self.lon:.3f}:{marine_zone}"
        cached = self._cache.get(ck)
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        try:
            out += self._alerts_from(
                f"{self.NWS_BASE}/alerts/active?point={self.lat:.4f},{self.lon:.4f}", "weather")
        except Exception as e:
            logger.debug("weather alerts failed: %s", e)
        if marine_zone:
            try:
                out += self._alerts_from(
                    f"{self.NWS_BASE}/alerts/active/zone/{marine_zone}", "marine")
            except Exception as e:
                logger.debug("marine alerts failed: %s", e)
        seen, uniq = set(), []
        for a in out:
            key = (a["kind"], a["event"])
            if key not in seen:
                seen.add(key)
                uniq.append(a)
        self._cache.set(ck, uniq)
        return uniq

    def _alerts_from(self, url: str, kind: str) -> List[Dict[str, Any]]:
        req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0 (skydex@localhost)"})
        with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
            data = json.load(resp)
        res = []
        for feat in (data.get("features") or []):
            p = feat.get("properties") or {}
            event = p.get("event")
            if not event:
                continue
            res.append({
                "event": event,
                "severity": p.get("severity") or "",
                "headline": p.get("headline") or "",
                "kind": kind,
                "onset": p.get("onset") or p.get("effective") or "",
                "ends": p.get("ends") or p.get("expires") or "",
            })
        return res

    def fetch_forecast(self) -> List[Dict[str, Any]]:
        """Multi-day forecast periods. NWS day/night periods lead (best local
        text, ~7 days max), then Open-Meteo dailies extend the tail to 10 days.
        Cached 5 min."""
        ck = f"fc:{self.lat:.3f}:{self.lon:.3f}"
        cached = self._cache.get(ck)
        if cached is not None:
            return cached
        out = self._forecast_nws() or []
        om = self._forecast_openmeteo() or []
        if out:
            # Dates already covered by NWS: one per daytime period, plus one
            # if the forecast opens with a lone "Tonight" period.
            day_ct = sum(1 for p in out if p.get("is_daytime") is not False)
            if out and out[0].get("is_daytime") is False:
                day_ct += 1
            out = out + om[day_ct:]
        else:
            out = om
        self._cache.set(ck, out)
        return out

    def fetch_hourly(self) -> List[Dict[str, Any]]:
        """The next 24 hours (Open-Meteo). Cached with the forecast."""
        ck = f"fh:{self.lat:.3f}:{self.lon:.3f}"
        cached = self._cache.get(ck)
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        try:
            url = (f"{self.OM_BASE}/forecast?latitude={self.lat}&longitude={self.lon}"
                   "&hourly=temperature_2m,precipitation_probability,weather_code,wind_speed_10m"
                   "&temperature_unit=fahrenheit&wind_speed_unit=mph&forecast_days=2&timezone=auto")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                h = (json.load(resp).get("hourly") or {})
            times = h.get("time") or []
            now_key = datetime.now().strftime("%Y-%m-%dT%H:00")
            start = next((i for i, t in enumerate(times) if t >= now_key), 0)
            n = len(times)
            for i in range(start, min(start + 24, n)):
                hr = datetime.strptime(times[i], "%Y-%m-%dT%H:%M")
                out.append({
                    "label": hr.strftime("%-I %p"),
                    "temp": (h.get("temperature_2m") or [None] * n)[i],
                    "precip": (h.get("precipitation_probability") or [None] * n)[i],
                    "short": self._decode_weather_code((h.get("weather_code") or [None] * n)[i]),
                    "wind": (h.get("wind_speed_10m") or [None] * n)[i],
                })
            self._cache.set(ck, out)
        except Exception as e:
            logger.debug("hourly forecast failed: %s", e)
        return out

    def _forecast_nws(self) -> Optional[List[Dict[str, Any]]]:
        try:
            url = f"{self.NWS_BASE}/points/{self.lat:.4f},{self.lon:.4f}"
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0 (skydex@localhost)"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                forecast_url = (json.load(resp).get("properties") or {}).get("forecast")
            if not forecast_url:
                return None
            req2 = urllib.request.Request(forecast_url, headers={"User-Agent": "SkyDex/1.0 (skydex@localhost)"})
            with urllib.request.urlopen(req2, timeout=self.TIMEOUT) as resp2:
                periods = (json.load(resp2).get("properties") or {}).get("periods") or []
            out = []
            for p in periods[:14]:
                out.append({
                    "name": p.get("name"),
                    "is_daytime": p.get("isDaytime"),
                    "temp": p.get("temperature"),
                    "temp_unit": p.get("temperatureUnit", "F"),
                    "wind": p.get("windSpeed"),
                    "wind_dir": p.get("windDirection"),
                    "short": p.get("shortForecast"),
                    "detailed": p.get("detailedForecast"),
                    "precip": (p.get("probabilityOfPrecipitation") or {}).get("value"),
                })
            return out or None
        except Exception as e:
            logger.debug("NWS forecast failed: %s", e)
            return None

    def _forecast_openmeteo(self) -> Optional[List[Dict[str, Any]]]:
        try:
            url = (f"{self.OM_BASE}/forecast?latitude={self.lat}&longitude={self.lon}"
                   "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
                   "precipitation_probability_max,wind_speed_10m_max"
                   "&temperature_unit=fahrenheit&wind_speed_unit=mph&forecast_days=10&timezone=auto")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                daily = (json.load(resp).get("daily") or {})
            dates = daily.get("time") or []
            out = []
            for i, day in enumerate(dates):
                try:
                    # "Saturday 7/12" — weekday first so alert badges still match.
                    dt = datetime.strptime(day, "%Y-%m-%d")
                    label = dt.strftime("%A") + dt.strftime(" %-m/%-d")
                except ValueError:
                    label = day
                out.append({
                    "name": label,
                    "is_daytime": True,
                    "temp": daily.get("temperature_2m_max", [None] * len(dates))[i],
                    "temp_low": daily.get("temperature_2m_min", [None] * len(dates))[i],
                    "temp_unit": "F",
                    "wind": f"{daily.get('wind_speed_10m_max', [0]*len(dates))[i]:.0f} mph",
                    "short": self._decode_weather_code(daily.get("weather_code", [None]*len(dates))[i]),
                    "precip": daily.get("precipitation_probability_max", [None]*len(dates))[i],
                })
            return out or None
        except Exception as e:
            logger.debug("Open-Meteo forecast failed: %s", e)
            return None

    def fetch_day_high(self, date_str: str) -> Optional[float]:
        """Actual max temperature for a recent past date (settles the daily
        weather-guess game the morning after)."""
        try:
            url = (f"{self.OM_BASE}/forecast?latitude={self.lat}&longitude={self.lon}"
                   "&daily=temperature_2m_max&past_days=3&forecast_days=1"
                   "&temperature_unit=fahrenheit&timezone=auto")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                d = (json.load(resp).get("daily") or {})
            for i, day in enumerate(d.get("time") or []):
                if day == date_str:
                    v = (d.get("temperature_2m_max") or [None] * (i + 1))[i]
                    return float(v) if v is not None else None
        except Exception as e:
            logger.debug("day-high lookup failed: %s", e)
        return None

    def fetch_hist_day(self, date_str: str) -> Optional[Dict[str, Any]]:
        """One historical day at our coordinates: high temp, rain, snow, and
        peak wind — the Weather Time Machine's full fuel. 1950 onward."""
        try:
            url = ("https://archive-api.open-meteo.com/v1/archive"
                   f"?latitude={self.lat}&longitude={self.lon}"
                   f"&start_date={date_str}&end_date={date_str}"
                   "&daily=temperature_2m_max,precipitation_sum,snowfall_sum,wind_speed_10m_max"
                   "&temperature_unit=fahrenheit&precipitation_unit=inch"
                   "&wind_speed_unit=mph&timezone=auto")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                d = (json.load(resp).get("daily") or {})
            g = lambda k: (d.get(k) or [None])[0]
            if g("temperature_2m_max") is None:
                return None
            return {"high": float(g("temperature_2m_max")),
                    "rain": float(g("precipitation_sum") or 0),
                    "snow": float(g("snowfall_sum") or 0),
                    "wind": float(g("wind_speed_10m_max") or 0)}
        except Exception as e:
            logger.debug("hist day (%s) failed: %s", date_str, e)
            return None

    def fetch_hist_high(self, date_str: str) -> Optional[float]:
        d = self.fetch_hist_day(date_str)
        return d["high"] if d else None

    def fetch_climate_record(self) -> Optional[Dict[str, Any]]:
        """Record high/low FOR TODAY'S CALENDAR DATE since 1950, from the
        Open-Meteo ERA5 archive. The full history (~75 years of daily highs and
        lows) downloads ONCE and is cached to disk forever; per-day lookups are
        instant after that."""
        today_key = datetime.now().strftime("%m-%d")
        cache_path = os.path.expanduser("~/.skydex/climate_records.json")

        records = None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, ValueError):
            pass

        if records is None:
            try:
                end = datetime.now().year - 1
                url = ("https://archive-api.open-meteo.com/v1/archive"
                       f"?latitude={self.lat}&longitude={self.lon}"
                       f"&start_date=1950-01-01&end_date={end}-12-31"
                       "&daily=temperature_2m_max,temperature_2m_min"
                       "&temperature_unit=fahrenheit&timezone=auto")
                req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    daily = (json.load(resp).get("daily") or {})
                dates = daily.get("time") or []
                tmax = daily.get("temperature_2m_max") or []
                tmin = daily.get("temperature_2m_min") or []
                records = {}
                for i, d in enumerate(dates):
                    key = d[5:]                       # "MM-DD"
                    hi = tmax[i] if i < len(tmax) else None
                    lo = tmin[i] if i < len(tmin) else None
                    r = records.setdefault(key, {"record_high": None, "high_year": None,
                                                 "record_low": None, "low_year": None})
                    if hi is not None and (r["record_high"] is None or hi > r["record_high"]):
                        r["record_high"], r["high_year"] = round(hi), int(d[:4])
                    if lo is not None and (r["record_low"] is None or lo < r["record_low"]):
                        r["record_low"], r["low_year"] = round(lo), int(d[:4])
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(records, f)
                logger.info("Climate records built: %d calendar days (1950-%d)", len(records), end)
            except Exception as e:
                logger.warning("climate record build failed: %s", e)
                return None

        rec = records.get(today_key)
        if not rec:
            return None
        return {"date": today_key, "since": 1950, **rec}

    def fetch_national_extremes(self, limit: int = 5) -> List[Dict[str, Any]]:
        """The most serious weather in the country right now (NWS active alerts,
        Extreme severity first). Cached 30 min."""
        ck = "natl-extremes"
        cached = self._cache.get(ck)
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        seen = set()
        for severity in ("Extreme", "Severe"):
            if len(out) >= limit:
                break
            try:
                url = f"{self.NWS_BASE}/alerts/active?severity={severity}&limit=100"
                req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0 (skydex@localhost)"})
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                    feats = (json.load(resp).get("features") or [])
                for feat in feats:
                    p = feat.get("properties") or {}
                    event = p.get("event") or ""
                    if not event or event in seen:
                        continue
                    # Skip the routine stuff — only headline-worthy events.
                    if any(s in event for s in ("Small Craft", "Rip Current", "Frost",
                                                "Air Quality", "Beach", "Test")):
                        continue
                    seen.add(event)
                    area = (p.get("areaDesc") or "").split(";")[0].strip()
                    out.append({"event": event, "area": area, "severity": severity})
                    if len(out) >= limit:
                        break
            except Exception as e:
                logger.debug("national extremes (%s) failed: %s", severity, e)
        self._cache.set(ck, out)
        return out

    @staticmethod
    def _decode_weather_code(code: Optional[int]) -> str:
        codes = {
            0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Foggy", 51: "Light drizzle", 53: "Drizzle",
            55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
            71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
            80: "Rain showers", 81: "Heavy showers", 82: "Violent showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail",
        }
        return codes.get(code, "Unknown") if code is not None else "Unknown"


# ---------------------------------------------------------------------------
# NOAA Tides & Currents — free tide data for Long Island Sound
# ---------------------------------------------------------------------------

class TideClient:
    """Fetches tide data from NOAA CO-OPS API. No key needed.

    Default station: Bridgeport, CT (8467150) — nearest to Stratford.
    Other nearby stations:
      - New Haven, CT: 8465705
      - Stratford Point, CT: 8465193
      - Kings Point, NY: 8516945
    """

    NOAA_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    TIMEOUT = 15

    # Station info for Long Island Sound area
    STATIONS = {
        "8467150": {"name": "Bridgeport, CT", "lat": 41.176, "lon": -73.188},
        "8465705": {"name": "New Haven, CT", "lat": 41.295, "lon": -72.918},
        "8465193": {"name": "Stratford Point, CT", "lat": 41.152, "lon": -73.211},
    }

    def __init__(self, station_id: str = "8467150"):
        self.station_id = station_id
        self._cache = _Cache(ttl_seconds=300)  # 5 min cache

    def fetch(self) -> Optional[Dict[str, Any]]:
        """Get current tide info: water level, next high/low, and tide state."""
        cache_key = f"tide:{self.station_id}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        result = self._fetch_combined()
        if result:
            self._cache.set(cache_key, result)
        return result

    def _fetch_combined(self) -> Optional[Dict[str, Any]]:
        """Combine water level + predictions into one snapshot."""
        import datetime as dt

        try:
            # 1. Current water level
            water_level = self._fetch_water_level()

            # 2. Today's predictions (for next high/low)
            predictions = self._fetch_predictions()

            if not predictions:
                return None

            now = time.time()
            now_dt = dt.datetime.now()

            # Find next high/low tide
            next_events = []
            for p in predictions:
                try:
                    pt = dt.datetime.strptime(p["t"], "%Y-%m-%d %H:%M")
                    if pt > now_dt:
                        next_events.append({
                            "time": pt.strftime("%H:%M"),
                            "type": p["type"],  # H = High, L = Low
                            "height_ft": float(p["v"]),
                        })
                except (ValueError, KeyError):
                    continue

            # Determine if tide is rising or falling
            tide_state = "unknown"
            if len(predictions) >= 2:
                # Compare most recent prediction to next
                recent = [p for p in predictions if dt.datetime.strptime(p["t"], "%Y-%m-%d %H:%M") <= now_dt]
                if recent:
                    latest = recent[-1]
                    next_p = next_events[0] if next_events else None
                    if next_p:
                        tide_state = "rising" if next_p["type"] == "H" else "falling"

            # Current water level (or estimate from predictions)
            current_height = water_level if water_level is not None else None
            if current_height is None and recent:
                current_height = float(recent[-1]["v"])

            result = {
                "station_id": self.station_id,
                "station_name": self.STATIONS.get(self.station_id, {}).get("name", "Unknown"),
                "current_height_ft": round(current_height, 1) if current_height else None,
                "tide_state": tide_state,
                "next_high": None,
                "next_low": None,
                "predictions": [],
            }

            # Split next events into high and low
            for ev in next_events[:4]:  # Next 4 events
                if ev["type"] == "H" and not result["next_high"]:
                    result["next_high"] = ev
                elif ev["type"] == "L" and not result["next_low"]:
                    result["next_low"] = ev
                result["predictions"].append(ev)

            # Sea condition estimate based on tide state
            result["sea_condition"] = self._estimate_sea_condition(tide_state)

            return result

        except Exception as e:
            logger.debug("Tide fetch failed: %s", e)
            return None

    def _fetch_water_level(self) -> Optional[float]:
        """Fetch latest observed water level."""
        try:
            url = (
                f"{self.NOAA_API}"
                f"?date=latest"
                f"&station={self.station_id}"
                f"&product=water_level"
                f"&datum=mllw"
                f"&units=english"
                f"&time_zone=lst_ldt"
                f"&format=json"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            observations = data.get("data", [])
            if observations:
                return float(observations[0]["v"])
        except Exception as e:
            logger.debug("Water level fetch failed: %s", e)
        return None

    def _fetch_predictions(self) -> list:
        """Fetch high/low tide predictions for today and tomorrow.

        Using a today+tomorrow window (rather than just today) guarantees there
        is always a "next high" and "next low" even late in the evening.
        """
        import datetime as dt
        try:
            today = dt.date.today()
            begin = today.strftime("%Y%m%d")
            end = (today + dt.timedelta(days=1)).strftime("%Y%m%d")
            url = (
                f"{self.NOAA_API}"
                f"?begin_date={begin}"
                f"&end_date={end}"
                f"&station={self.station_id}"
                f"&product=predictions"
                f"&datum=mllw"
                f"&units=english"
                f"&time_zone=lst_ldt"
                f"&interval=hilo"   # high/low events only (each has a 'type': H or L)
                f"&format=json"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            return data.get("predictions", [])
        except Exception as e:
            logger.debug("Tide predictions fetch failed: %s", e)
            return []

    @staticmethod
    def _estimate_sea_condition(tide_state: str) -> str:
        """Estimate sea condition label based on tide state."""
        # This is a rough estimate — real sea conditions depend on wind too
        conditions = {
            "rising": "Incoming tide — currents strengthening",
            "falling": "Outgoing tide — currents easing",
            "unknown": "Tide data unavailable",
        }
        return conditions.get(tide_state, "Unknown")


# ---------------------------------------------------------------------------
# Stormglass.io — marine weather (sea temp, wave height, wind)
# 10 free calls/day. Hardcoded key as requested.
# ---------------------------------------------------------------------------

class StormglassClient:
    """Marine weather from Stormglass.io — sea conditions for Long Island Sound."""

    # Key comes from .env (SKYDEX_STORMGLASS_KEY) — see config.py's loader.
    API_KEY = os.environ.get("SKYDEX_STORMGLASS_KEY", "")
    BASE = "https://api.stormglass.io/v2"
    TIMEOUT = 15

    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        self._cache = _Cache(ttl_seconds=1800)  # 30 min cache (10 calls/day budget)

    def fetch(self) -> Optional[Dict[str, Any]]:
        """Get marine conditions: water temp, wave height, wind, tide."""
        cache_key = f"sg:{self.lat:.3f}:{self.lon:.3f}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        result = self._fetch_weather()
        if result:
            self._cache.set(cache_key, result)
        return result

    def _fetch_weather(self) -> Optional[Dict[str, Any]]:
        try:
            import datetime as dt
            now = dt.datetime.now(dt.timezone.utc)
            # Stormglass accepts unix timestamps for start/end (no URL-unsafe spaces).
            start = int(now.timestamp())
            end = int((now + dt.timedelta(hours=1)).timestamp())

            params = "waterTemperature,waveHeight,wavePeriod,windSpeed,windDirection,airTemperature,seaLevel"
            url = (
                f"{self.BASE}/weather/point"
                f"?lat={self.lat}&lng={self.lon}"
                f"&params={params}"
                f"&start={start}"
                f"&end={end}"
            )
            req = urllib.request.Request(url, headers={
                "Authorization": self.API_KEY,
                "User-Agent": "SkyDex/1.0",
            })
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            hours = data.get("hours", [])
            if not hours:
                return None

            h = hours[0]

            def _get(values, source_priority=["sg", "noaa", "meto"]):
                """Extract value from Stormglass multi-source response."""
                if not values:
                    return None
                for src in source_priority:
                    for v in values:
                        if v.get("source") == src and v.get("value") is not None:
                            return v["value"]
                # Fallback: any source
                for v in values:
                    if v.get("value") is not None:
                        return v["value"]
                return None

            return {
                "water_temp_f": self._c_to_f(_get(h.get("waterTemperature"))),
                "wave_height_ft": self._m_to_ft(_get(h.get("waveHeight"))),
                "wave_period_s": _get(h.get("wavePeriod")),
                "wind_speed_kts": self._ms_to_kts(_get(h.get("windSpeed"))),
                "wind_direction": _get(h.get("windDirection")),
                "air_temp_f": self._c_to_f(_get(h.get("airTemperature"))),
                "sea_level_m": _get(h.get("seaLevel")),
                "source": "stormglass",
            }

        except Exception as e:
            logger.debug("Stormglass fetch failed: %s", e)
            return None

    @staticmethod
    def _c_to_f(c):
        return round(c * 9 / 5 + 32, 1) if c is not None else None

    @staticmethod
    def _m_to_ft(m):
        return round(m * 3.28084, 1) if m is not None else None

    @staticmethod
    def _ms_to_kts(ms):
        return round(ms * 1.94384, 1) if ms is not None else None


# ---------------------------------------------------------------------------
# Aerodatabox — aircraft photos, airport data, routes
# RapidAPI key hardcoded as requested.
# ---------------------------------------------------------------------------

class AerodataboxClient:
    """Aerodatabox via RapidAPI — aircraft photos, airport info, routes."""

    # Your RapidAPI credentials (hardcoded as requested)
    RAPIDAPI_KEY = os.environ.get("SKYDEX_RAPIDAPI_KEY", "")
    HOST = "aerodatabox.p.rapidapi.com"
    BASE = f"https://{HOST}"
    TIMEOUT = 10

    def __init__(self):
        self._cache = _Cache(ttl_seconds=86400)   # 24h (photos/info)
        self._fids_cache = _Cache(ttl_seconds=21600)  # 6h (airport board)

    def _get_json(self, url: str) -> Any:
        req = urllib.request.Request(url, headers={
            "x-rapidapi-host": self.HOST,
            "x-rapidapi-key": self.RAPIDAPI_KEY,
            "User-Agent": "SkyDex/1.0",
        })
        with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
            return json.load(resp)

    @staticmethod
    def _extract_image(data: Any) -> Optional[str]:
        """Pull a usable image URL out of the various AeroDataBox shapes."""
        if not isinstance(data, dict):
            return None
        img = data.get("image")
        if isinstance(img, dict) and img.get("url"):
            return img["url"]
        if data.get("url"):  # the reg image/beta endpoint returns the image object directly
            return data["url"]
        images = data.get("images")
        if isinstance(images, list):
            for im in images:
                if isinstance(im, dict) and im.get("url"):
                    return im["url"]
        return None

    def airport_board(self, icao: str = "KBDR") -> Dict[str, Any]:
        """Scheduled/expected movements at an airport (AeroDataBox FIDS).

        Cached 6h (≈4 credit-spends/day). KBDR is mostly GA, so withPrivate=true
        matters — and on quiet days the board may legitimately be empty; the
        /api/airport-board endpoint merges in our own observed traffic so the
        kiosk board is never blank.
        """
        icao = icao.upper().strip()
        cache_key = f"adb:fids:{icao}"
        cached = self._fids_cache.get(cache_key)
        if cached is not None:
            return cached

        from datetime import datetime as _dt, timedelta as _td
        start = _dt.now() - _td(hours=2)
        end = start + _td(hours=11)   # API max window is 12h
        url = (f"{self.BASE}/flights/airports/icao/{icao}/"
               f"{start.strftime('%Y-%m-%dT%H:%M')}/{end.strftime('%Y-%m-%dT%H:%M')}"
               "?withLeg=true&direction=Both&withCancelled=false"
               "&withCodeshared=false&withCargo=true&withPrivate=true&withLocation=false")
        result: Dict[str, Any] = {"departures": [], "arrivals": []}
        try:
            data = self._get_json(url)
            for kind in ("departures", "arrivals"):
                for f in (data.get(kind) or [])[:30]:
                    if not isinstance(f, dict):
                        continue
                    mv = f.get("movement") or {}
                    sched = (mv.get("revisedTime") or mv.get("scheduledTime") or {})
                    ac = f.get("aircraft") or {}
                    result[kind].append({
                        "time_local": (sched.get("local") or "")[:16],
                        "ident": f.get("callSign") or f.get("number") or (ac.get("reg") or ""),
                        "reg": ac.get("reg"),
                        "model": ac.get("model"),
                        "airline": (f.get("airline") or {}).get("name"),
                        "other_airport": (mv.get("airport") or {}).get("name"),
                        "status": f.get("status") or "Scheduled",
                        "source": "sched",
                    })
        except urllib.error.HTTPError as e:
            logger.debug("Aerodatabox FIDS error %d for %s", e.code, icao)
        except Exception as e:
            logger.debug("Aerodatabox FIDS failed for %s: %s", icao, e)

        # Cache even an empty/failed board so errors don't burn credits (6h TTL
        # -> ~4 credit-spends/day).
        self._fids_cache.set(cache_key, result)
        return result

    def lookup_aircraft_photo(self, icao24: str, reg: str = "") -> Optional[str]:
        """Real photo of the specific airframe (paid AeroDataBox).

        Tries ``/aircrafts/icao24/{hex}?withImage=true`` first, then falls back
        to the registration image endpoint. Misses are cached so we don't keep
        spending RapidAPI credits on aircraft that have no photo.
        """
        icao24 = icao24.upper().strip()
        cache_key = f"adb:photo:{icao24}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached or None

        url_value = ""
        try:
            data = self._get_json(f"{self.BASE}/aircrafts/icao24/{icao24}?withImage=true")
            url_value = self._extract_image(data) or ""
        except urllib.error.HTTPError as e:
            if e.code != 404:
                logger.debug("Aerodatabox photo error %d for %s", e.code, icao24)
        except Exception as e:
            logger.debug("Aerodatabox photo fetch failed for %s: %s", icao24, e)

        if not url_value and reg:
            try:
                data = self._get_json(f"{self.BASE}/aircrafts/reg/{reg.upper().strip()}/image/beta")
                url_value = self._extract_image(data) or ""
            except Exception as e:
                logger.debug("Aerodatabox reg image failed for %s: %s", reg, e)

        self._cache.set(cache_key, url_value)
        return url_value or None

    def lookup_aircraft_info(self, icao24: str) -> Dict[str, Any]:
        """Get aircraft registration, type, operator by ICAO 24-bit hex."""
        icao24 = icao24.upper().strip()
        cache_key = f"adb:info:{icao24}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = self._get_json(f"{self.BASE}/aircrafts/icao24/{icao24}")
            result = {
                "registration": data.get("reg") or data.get("regNumber"),
                "model": data.get("model"),
                "manufacturer": data.get("productionLine") or data.get("producer") or data.get("manufacturer"),
                "type_code": data.get("typeCode") or data.get("icaoCode") or data.get("typecode"),
                "operator": data.get("airlineName") or data.get("ownerName") or data.get("owner"),
                "icao24": icao24,
                "source": "aerodatabox",
            }
            result = {k: v for k, v in result.items() if v}
            self._cache.set(cache_key, result)
            return result

        except urllib.error.HTTPError as e:
            if e.code != 404:
                logger.debug("Aerodatabox info error %d for %s", e.code, icao24)
            return {}
        except Exception as e:
            logger.debug("Aerodatabox info failed for %s: %s", icao24, e)
            return {}

    def lookup_airport(self, iata_or_icao: str) -> Dict[str, Any]:
        """Get airport name, location by IATA or ICAO code."""
        code = iata_or_icao.upper().strip()
        cache_key = f"adb:apt:{code}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.BASE}/airports/iata/{code}"
            req = urllib.request.Request(url, headers={
                "x-rapidapi-host": self.HOST,
                "x-rapidapi-key": self.RAPIDAPI_KEY,
                "User-Agent": "SkyDex/1.0",
            })
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)

            result = {
                "name": data.get("name"),
                "iata": data.get("iata"),
                "icao": data.get("icao"),
                "city": data.get("municipalityName"),
                "country": data.get("countryCode"),
                "lat": data.get("location", {}).get("lat"),
                "lon": data.get("location", {}).get("lon"),
                "timezone": data.get("timeZone"),
            }
            result = {k: v for k, v in result.items() if v is not None}
            self._cache.set(cache_key, result)
            return result

        except Exception as e:
            logger.debug("Aerodatabox airport failed for %s: %s", code, e)
            return {}

    def get_api_balance(self) -> Optional[Dict[str, Any]]:
        """Check remaining RapidAPI quota."""
        try:
            url = "https://aerodatabox.p.rapidapi.com/subscriptions/balance"
            req = urllib.request.Request(url, headers={
                "x-rapidapi-host": self.HOST,
                "x-rapidapi-key": self.RAPIDAPI_KEY,
                "User-Agent": "SkyDex/1.0",
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            return data
        except Exception as e:
            logger.debug("Aerodatabox balance check failed: %s", e)
            return None
