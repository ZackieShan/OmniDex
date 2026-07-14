"""SeaDex AIS receiver — reads vessel JSON from a local AIS-catcher instance.

Mirrors receiver.ADSBReceiver. AIS-catcher's built-in web server exposes the
current vessels at /api/ships.json. We normalize each vessel and compute its
distance + bearing from home (same as the aircraft pipeline).

When the local AIS-catcher isn't reachable, we fall back to the AISHub cloud
feed (the marine equivalent of OpenSky for ADS-B) — if a username is configured.
"""

from __future__ import annotations

import json
import logging
import math
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from receiver import _haversine, _bearing  # reuse the geo math
from vessels import mmsi_country

try:
    import websocket  # from the 'websocket-client' package (for AISStream)
except ImportError:  # pragma: no cover - optional dependency
    websocket = None

logger = logging.getLogger(__name__)

# We request a cloud bounding box this many times the display radius, so we catch
# a vessel's (infrequent) static type/IMO message while it's still approaching —
# by the time it enters the display radius we already know what it is. Display is
# still filtered to the configured radius; this only affects what we *track*.
CLOUD_BOX_MULT = 2.5


def _radius_to_box(lat: float, lon: float, radius_miles: float) -> Tuple[float, float, float, float]:
    """A bounding box (lat_min, lon_min, lat_max, lon_max) that contains a circle
    of the given radius (miles) around home. Longitude degrees shrink with
    latitude, so lat and lon margins differ."""
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * max(0.1, math.cos(math.radians(lat))))
    return (lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta)


class AISReceiver:
    """Polls AIS-catcher JSON and returns normalized vessels keyed by MMSI."""

    def __init__(
        self,
        home_lat: float,
        home_lon: float,
        ais_url: str = "http://localhost:8100/api/ships.json",
        poll_interval: float = 5.0,
        stale_seconds: float = 180.0,
        aishub_enabled: bool = False,
        aishub_username: str = "",
        aishub_url: str = "https://data.aishub.net/ws.php",
        aishub_interval: float = 60.0,
        aishub_api_enabled: bool = False,
        aisstream_enabled: bool = False,
        aisstream_api_key: str = "",
        aisstream_url: str = "wss://stream.aisstream.io/v0/stream",
        cloud_radius_miles: float = 5.0,
    ):
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.ais_url = ais_url
        self.poll_interval = poll_interval
        self.stale_seconds = stale_seconds
        # Both cloud feeds request a box covering this radius (matches the SeaDex
        # display radius, which mirrors SkyDex).
        self.cloud_radius_miles = cloud_radius_miles

        # AISHub cloud fallback (HTTP poll, requires you to contribute data)
        self.aishub_enabled = aishub_enabled and bool(aishub_username)
        self.aishub_username = aishub_username
        self.aishub_url = aishub_url
        self.aishub_interval = aishub_interval
        self._last_aishub = 0.0
        # AISHub static-data enrichment (fills ship type/IMO the live feed lacks)
        self.aishub_api_enabled = aishub_api_enabled and bool(aishub_username)
        self._last_aishub_enrich = 0.0

        # AISStream cloud fallback (WebSocket push, free with just an API key)
        self._aisstream: Optional["AISStreamClient"] = None
        if aisstream_enabled and aisstream_api_key:
            self._aisstream = AISStreamClient(
                api_key=aisstream_api_key,
                home_lat=home_lat,
                home_lon=home_lon,
                url=aisstream_url,
                radius_miles=cloud_radius_miles,
                stale_seconds=max(stale_seconds, 600.0),
            )

        self._vessels: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {"ais": 0, "aisstream": 0, "aishub": 0, "errors": 0, "last_source": "none"}

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._running = True
        if self._aisstream:
            self._aisstream.start()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("AISReceiver started (home=%.4f,%.4f  url=%s)", self.home_lat, self.home_lon, self.ais_url)

    def stop(self) -> None:
        self._running = False
        if self._aisstream:
            self._aisstream.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("AISReceiver stopped")

    def _run_loop(self) -> None:
        warned = False
        while self._running:
            try:
                ships = self._fetch()
                if ships is not None:
                    self._process(ships)
                    warned = False
            except Exception as e:
                self._stats["errors"] += 1
                if not warned:
                    logger.warning("AIS receiver error: %s", e)
                    warned = True
            try:
                self._maybe_enrich_aishub()
            except Exception as e:
                logger.debug("AISHub enrich error: %s", e)
            time.sleep(self.poll_interval)

    def _maybe_enrich_aishub(self) -> None:
        """Once a minute, pull AISHub's aggregated box and fill in ship type / IMO
        / length / name for vessels whose live feed didn't include them. AISHub
        aggregates many receivers, so it often has the static data we missed.
        Requires an ACTIVE AISHub contribution (its API is contributor-only)."""
        if not self.aishub_api_enabled:
            return
        now = time.time()
        if (now - self._last_aishub_enrich) < self.aishub_interval:
            return
        self._last_aishub_enrich = now
        ships = self._fetch_aishub()
        if not ships:
            return
        by_mmsi = {str(s.get("mmsi")): s for s in ships if s.get("mmsi") is not None}
        filled = 0
        with self._lock:
            for mmsi, v in self._vessels.items():
                src = by_mmsi.get(mmsi)
                if not src:
                    continue
                if v.get("ship_type") in (None, 0) and src.get("shiptype") not in (None, "", 0):
                    v["ship_type"] = src.get("shiptype")
                    filled += 1
                if not v.get("imo") and src.get("imo"):
                    v["imo"] = src.get("imo")
                if not v.get("name") and src.get("shipname"):
                    v["name"] = (src.get("shipname") or "").strip()
                if not v.get("length"):
                    a, b = src.get("to_bow"), src.get("to_stern")
                    if a is not None and b is not None:
                        v["length"] = a + b
        if filled:
            self._stats["aishub"] = self._stats.get("aishub", 0) + 1
            logger.info("AISHub enrichment filled ship type for %d vessel(s)", filled)

    # -- fetching -----------------------------------------------------------

    def _fetch(self) -> Optional[List[Dict[str, Any]]]:
        """Local AIS-catcher first; cloud fallback (AISStream, then AISHub).

        We fall through to the cloud not just when local is *down*, but also when
        it's up yet decoding *nothing* — a weak VHF antenna shouldn't leave SeaDex
        empty when the cloud has vessels in range.
        """
        local = self._fetch_local()  # None = unreachable, [] = up but no ships
        if local:  # non-empty -> local decoder is genuinely seeing traffic
            self._stats["ais"] += 1
            self._stats["last_source"] = "ais-catcher"
            return local

        # Local down or seeing nothing — prefer AISStream (live WebSocket feed).
        if self._aisstream and self._aisstream.is_connected():
            ships = self._aisstream.get_ships()
            if ships:
                self._stats["aisstream"] += 1
                self._stats["last_source"] = "aisstream"
                return ships

        # Then AISHub (throttled to its 1-request-per-minute rate limit).
        if self.aishub_enabled and (time.time() - self._last_aishub) >= self.aishub_interval:
            self._last_aishub = time.time()
            ships = self._fetch_aishub()
            if ships:
                self._stats["aishub"] += 1
                self._stats["last_source"] = "aishub"
                return ships

        # No cloud data either. If local was reachable (just empty), report that.
        if local is not None:
            self._stats["last_source"] = "ais-catcher"
            return local
        return None

    def _fetch_local(self) -> Optional[List[Dict[str, Any]]]:
        try:
            req = urllib.request.Request(self.ais_url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.load(resp)
        except urllib.error.URLError:
            # AIS-catcher not running — expected if the AIS dongle isn't set up.
            return None
        except Exception as e:
            logger.debug("AIS fetch error: %s", e)
            return None

        # AIS-catcher ships.json: {"count":N, "ships":[...]} (be defensive).
        if isinstance(data, dict):
            return data.get("ships") or data.get("vessels") or []
        if isinstance(data, list):
            return data
        return []

    def _fetch_aishub(self) -> Optional[List[Dict[str, Any]]]:
        """Pull a bounding box of vessels from AISHub and map to AIS-catcher keys."""
        lat_min, lon_min, lat_max, lon_max = _radius_to_box(
            self.home_lat, self.home_lon, self.cloud_radius_miles * CLOUD_BOX_MULT)
        params = {
            "username": self.aishub_username,
            "format": 1,          # human-readable values
            "output": "json",
            "compress": 0,
            "latmin": round(lat_min, 4),
            "latmax": round(lat_max, 4),
            "lonmin": round(lon_min, 4),
            "lonmax": round(lon_max, 4),
        }
        url = self.aishub_url + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
        except Exception as e:
            logger.debug("AISHub fetch error: %s", e)
            return None

        # AISHub returns [ {meta...}, [ {records...} ] ]
        if not isinstance(data, list) or len(data) < 2:
            meta = data[0] if isinstance(data, list) and data else data
            logger.warning("AISHub returned no records: %s", meta)
            return None
        records = data[1] if isinstance(data[1], list) else []

        mapped: List[Dict[str, Any]] = []
        for r in records:
            a, b = r.get("A"), r.get("B")  # distance antenna->bow / ->stern
            mapped.append({
                "mmsi": r.get("MMSI"),
                "lat": r.get("LATITUDE"),
                "lon": r.get("LONGITUDE"),
                "sog": r.get("SOG"),
                "cog": r.get("COG"),
                "heading": r.get("HEADING"),
                "shiptype": r.get("TYPE"),
                "status": r.get("NAVSTAT"),
                "destination": r.get("DEST"),
                "shipname": r.get("NAME"),
                "callsign": r.get("CALLSIGN"),
                "imo": r.get("IMO"),
                "to_bow": a,
                "to_stern": b,
            })
        return mapped

    def _process(self, ships: List[Dict[str, Any]]) -> None:
        now = time.time()
        vessels: Dict[str, Dict[str, Any]] = {}

        for s in ships:
            try:
                mmsi = str(s.get("mmsi") or "").strip()
                lat = s.get("lat")
                lon = s.get("lon")
                if not mmsi or lat is None or lon is None:
                    continue
                lat_f = float(lat)
                lon_f = float(lon)
                if lat_f == 0.0 and lon_f == 0.0:
                    continue

                def _num(*keys):
                    for k in keys:
                        v = s.get(k)
                        if v is not None:
                            try:
                                return float(v)
                            except (TypeError, ValueError):
                                pass
                    return None

                to_bow = _num("to_bow")
                to_stern = _num("to_stern")
                length = (to_bow + to_stern) if (to_bow is not None and to_stern is not None) else _num("length")

                dist = _haversine(self.home_lat, self.home_lon, lat_f, lon_f)
                vessels[mmsi] = {
                    "mmsi": mmsi,
                    "name": (s.get("shipname") or s.get("name") or "").strip(),
                    "lat": lat_f,
                    "lon": lon_f,
                    "speed": _num("speed", "sog"),          # knots
                    "course": _num("cog", "course"),        # degrees
                    "heading": _num("heading", "hdg"),
                    "ship_type": s.get("shiptype", s.get("ship_type")),
                    "nav_status": s.get("status", s.get("nav_status")),
                    "destination": (s.get("destination") or "").strip(),
                    "country": s.get("country") or s.get("flag") or mmsi_country(mmsi) or "",
                    "callsign": (s.get("callsign") or "").strip(),
                    "imo": s.get("imo") or None,
                    "length": length,
                    "distance_miles": round(dist, 2),
                    "bearing": round(_bearing(self.home_lat, self.home_lon, lat_f, lon_f), 1),
                    "timestamp": now,
                }
            except (TypeError, ValueError, KeyError) as e:
                logger.debug("Skipping malformed vessel: %s", e)
                continue

        with self._lock:
            # Carry forward known static data (type/IMO/name/length/etc.) that this
            # poll didn't include — so a position-only update, or an AISHub-enriched
            # type, doesn't get wiped back to None/0/"".
            for mmsi, nv in vessels.items():
                ov = self._vessels.get(mmsi)
                if not ov:
                    continue
                for key in ("ship_type", "imo", "name", "length", "callsign",
                            "nav_status", "destination"):
                    if not nv.get(key) and ov.get(key):
                        nv[key] = ov[key]
            # Keep recently-seen vessels even if this poll missed them entirely.
            for mmsi, v in self._vessels.items():
                if mmsi not in vessels and (now - v.get("timestamp", 0)) <= self.stale_seconds:
                    vessels[mmsi] = v
            self._vessels = vessels

    # -- public API ---------------------------------------------------------

    def get_all_vessels(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._vessels)

    def get_vessels_in_range(self, radius_miles: float) -> List[Dict[str, Any]]:
        with self._lock:
            vessels = list(self._vessels.values())
        in_range = [v for v in vessels if v.get("distance_miles", 9999) <= radius_miles]
        in_range.sort(key=lambda v: v.get("distance_miles", 9999))
        return in_range

    def get_vessel(self, mmsi: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._vessels.get(str(mmsi).strip())

    def get_health(self) -> Dict[str, Any]:
        with self._lock:
            vessels = list(self._vessels.values())
        health = {
            "running": self._running and self._thread is not None and self._thread.is_alive(),
            "vessel_count": len(vessels),
            "stats": dict(self._stats),
        }
        if self._aisstream:
            health["aisstream"] = {
                "connected": self._aisstream.is_connected(),
                "tracked": self._aisstream.count(),
            }
        return health


# ===========================================================================
# AISStream.io WebSocket client — free cloud AIS feed (push, no contribution)
# ===========================================================================

class AISStreamClient:
    """Maintains a WebSocket connection to aisstream.io and keeps a live dict of
    vessels inside a bounding box around home. Push-based, so there's no polling
    or rate limit. Output dicts use AIS-catcher-style keys so AISReceiver._process
    can consume them unchanged.
    """

    def __init__(
        self,
        api_key: str,
        home_lat: float,
        home_lon: float,
        url: str = "wss://stream.aisstream.io/v0/stream",
        radius_miles: float = 5.0,
        stale_seconds: float = 600.0,
    ):
        self.api_key = api_key
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.url = url
        self.radius_miles = radius_miles
        self.stale_seconds = stale_seconds

        self._vessels: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.api_key:
            logger.info("AISStream disabled (no API key set)")
            return
        if websocket is None:
            logger.warning(
                "AISStream is enabled but the 'websocket-client' package is not "
                "installed. Run: pip install websocket-client"
            )
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("AISStream client started (tracking ~%.0f-mile box, display %.0f mi)",
                    self.radius_miles * CLOUD_BOX_MULT, self.radius_miles)

    def stop(self) -> None:
        self._running = False  # the recv loop exits and closes the socket

    def _run(self) -> None:
        lat_min, lon_min, lat_max, lon_max = _radius_to_box(
            self.home_lat, self.home_lon, self.radius_miles * CLOUD_BOX_MULT)
        sub = {
            "APIKey": self.api_key,
            "BoundingBoxes": [[
                [lat_min, lon_min],
                [lat_max, lon_max],
            ]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        backoff = 2.0
        while self._running:
            ws = None
            try:
                ws = websocket.create_connection(self.url, timeout=15)
                ws.send(json.dumps(sub))
                ws.settimeout(60)   # recv timeout; idle water is normal (handled below)
                self._connected = True
                backoff = 2.0
                logger.info("AISStream connected & subscribed (box %.2f,%.2f → %.2f,%.2f)",
                            lat_min, lon_min, lat_max, lon_max)
                while self._running:
                    try:
                        raw = ws.recv()
                    except (websocket.WebSocketTimeoutException, socket.timeout):
                        # No AIS traffic in the box for a while — normal on quiet
                        # water. The socket is still fine; ping to confirm it's
                        # alive (raises if truly dead → outer handler reconnects),
                        # prune stale vessels, and keep waiting.
                        ws.ping()
                        self._prune()
                        continue
                    if not raw:
                        continue
                    try:
                        self._handle(json.loads(raw))
                    except (ValueError, TypeError) as e:
                        logger.debug("AISStream parse error: %s", e)
                    self._prune()
            except Exception as e:
                self._connected = False
                if self._running:
                    logger.warning("AISStream connection lost: %s (retry in %.0fs)", e, backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
            finally:
                self._connected = False
                try:
                    if ws is not None:
                        ws.close()
                except Exception:
                    pass

    def _handle(self, msg: Dict[str, Any]) -> None:
        mtype = msg.get("MessageType")
        if not mtype:
            # Non-data envelope — usually an error/ack (e.g. bad API key).
            err = msg.get("error") or msg.get("Error") or msg.get("message")
            if err:
                logger.warning("AISStream server message: %s", err)
            return
        meta = msg.get("MetaData") or {}
        mmsi = str(meta.get("MMSI") or "").strip()
        if not mmsi:
            return
        body = (msg.get("Message") or {}).get(mtype) or {}
        now = time.time()
        with self._lock:
            v = self._vessels.get(mmsi, {"mmsi": mmsi})
            name = (meta.get("ShipName") or "").strip()
            if name:
                v["shipname"] = name
            if mtype == "PositionReport":
                v["lat"] = body.get("Latitude", meta.get("latitude"))
                v["lon"] = body.get("Longitude", meta.get("longitude"))
                v["sog"] = body.get("Sog")
                v["cog"] = body.get("Cog")
                hdg = body.get("TrueHeading")
                v["heading"] = hdg if (hdg is not None and hdg != 511) else None
                v["status"] = body.get("NavigationalStatus")
            elif mtype == "ShipStaticData":
                v["shiptype"] = body.get("Type")
                imo = body.get("ImoNumber")
                if imo:
                    v["imo"] = imo
                dest = (body.get("Destination") or "").strip()
                if dest:
                    v["destination"] = dest
                cs = (body.get("CallSign") or "").strip()
                if cs:
                    v["callsign"] = cs
                dim = body.get("Dimension") or {}
                a, b = dim.get("A"), dim.get("B")
                if a is not None and b is not None:
                    v["length"] = a + b
                # static msgs carry a position in metadata too
                v.setdefault("lat", meta.get("latitude"))
                v.setdefault("lon", meta.get("longitude"))
            v["timestamp"] = now
            self._vessels[mmsi] = v

    def _prune(self) -> None:
        now = time.time()
        with self._lock:
            stale = [m for m, v in self._vessels.items()
                     if now - v.get("timestamp", 0) > self.stale_seconds]
            for m in stale:
                del self._vessels[m]

    def get_ships(self) -> List[Dict[str, Any]]:
        """Current vessels with a known position (AIS-catcher-style keys)."""
        with self._lock:
            return [dict(v) for v in self._vessels.values()
                    if v.get("lat") is not None and v.get("lon") is not None]

    def is_connected(self) -> bool:
        return self._connected

    def count(self) -> int:
        with self._lock:
            return len(self._vessels)
