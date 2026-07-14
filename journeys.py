"""Journeys — follow a tagged plane or vessel far beyond the home radius.

Planes: polled from the community ADS-B aggregators (adsb.lol, then
airplanes.live), falling back to OpenSky. Thousands of receivers worldwide;
coverage is excellent over land, thin mid-ocean.

Boats: a second AISStream WebSocket subscribed to the WHOLE WORLD but filtered
to just the followed MMSIs. Free AIS is shore-station based, so expect a tagged
ship to go dark crossing open water and reappear near the far coast — the UI
reports that honestly instead of pretending.

Set SKYDEX_AISSTREAM_KEY2 in .env for the boat socket (a second free
aisstream.io key, so the SeaDex live feed keeps its own connection).
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from receiver import _haversine

try:
    import websocket  # websocket-client, already required for AISStream
except ImportError:  # pragma: no cover
    websocket = None

logger = logging.getLogger(__name__)

POLL_SECONDS = 180        # air poll cadence (per cycle, all followed planes)
DARK_AFTER = 1800         # no fix for 30 min = shown as "dark"
_UA = {"User-Agent": "SkyDex-kiosk/1.0 (family aircraft kiosk)"}


class AdsbFollowClient:
    """Position of one aircraft by ICAO hex, from free global aggregators."""

    def fetch(self, hex_code: str) -> Optional[Dict[str, Any]]:
        hex_code = hex_code.strip().lower()
        for source, url in (
            ("adsb.lol", f"https://api.adsb.lol/v2/hex/{hex_code}"),
            ("airplanes.live", f"https://api.airplanes.live/v2/hex/{hex_code}"),
        ):
            fix = self._try_v2(url, source)
            if fix:
                return fix
        return self._try_opensky(hex_code)

    def _try_v2(self, url: str, source: str) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(url, headers=_UA)
            d = json.load(urllib.request.urlopen(req, timeout=10))
            ac = d.get("ac") or []
            if not ac:
                return None
            a = ac[0]
            lat, lon = a.get("lat"), a.get("lon")
            if lat is None or lon is None:
                return None
            alt = a.get("alt_baro")
            alt = 0 if alt == "ground" else (float(alt) if alt is not None else None)
            return {"lat": lat, "lon": lon, "alt": alt, "speed": a.get("gs"),
                    "callsign": (a.get("flight") or "").strip(), "source": source}
        except Exception:
            return None

    def _try_opensky(self, hex_code: str) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(
                f"https://opensky-network.org/api/states/all?icao24={hex_code}",
                headers=_UA)
            d = json.load(urllib.request.urlopen(req, timeout=10))
            s = (d.get("states") or [None])[0]
            if not s or s[6] is None:
                return None
            alt_m = s[13] if s[13] is not None else s[7]
            return {"lat": s[6], "lon": s[5],
                    "alt": alt_m * 3.28084 if alt_m is not None else None,
                    "speed": s[9] * 1.944 if s[9] is not None else None,
                    "callsign": (s[1] or "").strip(), "source": "opensky"}
        except Exception:
            return None


class AisFollowSocket:
    """AISStream, world bounding box, filtered to the followed MMSIs only.
    Reconnects with a fresh filter whenever the follow list changes."""

    def __init__(self, api_key: str, on_fix: Callable[[str, float, float, Optional[float], str], None],
                 url: str = "wss://stream.aisstream.io/v0/stream"):
        self.api_key = api_key
        self.on_fix = on_fix
        self.url = url
        self._mmsis: List[str] = []
        self._resub = False
        self._running = False

    def start(self) -> None:
        if self._running or websocket is None or not self.api_key:
            return
        self._running = True
        threading.Thread(target=self._run, daemon=True, name="journeys-ais").start()

    def stop(self) -> None:
        self._running = False

    def set_mmsis(self, mmsis: List[str]) -> None:
        mmsis = sorted(str(m) for m in mmsis)
        if mmsis != self._mmsis:
            self._mmsis = mmsis
            self._resub = True          # recv loop closes + reconnects w/ new filter

    def _run(self) -> None:
        backoff = 5.0
        while self._running:
            if not self._mmsis:
                time.sleep(5)
                continue
            ws = None
            try:
                sub = {"APIKey": self.api_key,
                       "BoundingBoxes": [[[-90, -180], [90, 180]]],
                       "FiltersShipMMSI": list(self._mmsis),
                       "FilterMessageTypes": ["PositionReport"]}
                ws = websocket.create_connection(self.url, timeout=15)
                ws.send(json.dumps(sub))
                ws.settimeout(60)
                self._resub = False
                backoff = 5.0
                logger.info("Journeys AIS socket following %s", ", ".join(self._mmsis))
                while self._running and not self._resub:
                    try:
                        raw = ws.recv()
                    except (websocket.WebSocketTimeoutException, socket.timeout):
                        continue        # tagged ships are often out of range — normal
                    try:
                        msg = json.loads(raw)
                        pr = (msg.get("Message") or {}).get("PositionReport") or {}
                        meta = msg.get("MetaData") or {}
                        lat, lon = pr.get("Latitude"), pr.get("Longitude")
                        if lat is None or lon is None:
                            continue
                        self.on_fix(str(meta.get("MMSI") or ""), lat, lon,
                                    pr.get("Sog"), (meta.get("ShipName") or "").strip())
                    except (ValueError, TypeError):
                        continue
            except Exception as e:
                logger.debug("journeys AIS socket: %s (retry in %.0fs)", e, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass


class JourneyService:
    """Keeps every followed craft's position fresh and its breadcrumb trail
    growing; announces when something reappears after going dark."""

    def __init__(self, db, home_lat: float, home_lon: float,
                 announcer=None, ais_key: str = ""):
        self.db = db
        self.home = (home_lat, home_lon)
        self.announcer = announcer
        self.air = AdsbFollowClient()
        self.ais_key = ais_key
        self._ais: Optional[AisFollowSocket] = None
        self._was_dark: Dict[int, bool] = {}
        self._poke = False
        threading.Thread(target=self._loop, daemon=True, name="journeys").start()

    def poke(self) -> None:
        """A new follow was added — poll soon for instant gratification."""
        self._poke = True

    def _loop(self) -> None:
        time.sleep(20)
        while True:
            try:
                self._tick()
            except Exception as e:
                logger.debug("journeys tick failed: %s", e)
            for _ in range(POLL_SECONDS // 5):
                if self._poke:
                    self._poke = False
                    break
                time.sleep(5)

    def _tick(self) -> None:
        follows = self.db.list_followed()
        self._sync_ais([f["craft_id"] for f in follows if f["kind"] == "sea"])
        for f in follows:
            if f["kind"] != "air":
                continue
            fix = self.air.fetch(f["craft_id"])
            if fix:
                self.db.update_follow_position(
                    f["id"], fix["lat"], fix["lon"], fix.get("alt"),
                    fix.get("speed"), fix["source"], callsign=fix.get("callsign"))
                self._reappear_check(f, fix["lat"], fix["lon"])
                self._was_dark[f["id"]] = False
            elif f.get("last_seen") and time.time() - f["last_seen"] > DARK_AFTER:
                self._was_dark[f["id"]] = True
            time.sleep(1)                # be polite to the free aggregators

    def _sync_ais(self, mmsis: List[str]) -> None:
        if not mmsis:
            if self._ais:
                self._ais.stop()
                self._ais = None
            return
        if not self.ais_key or websocket is None:
            return
        if self._ais is None:
            self._ais = AisFollowSocket(self.ais_key, self._on_sea_fix)
            self._ais.start()
        self._ais.set_mmsis(mmsis)

    def _on_sea_fix(self, mmsi: str, lat: float, lon: float,
                    sog: Optional[float], name: str) -> None:
        f = self.db.get_follow("sea", mmsi)
        if not f:
            return
        self.db.update_follow_position(f["id"], lat, lon, None, sog,
                                       "aisstream", name=name or None)
        self._reappear_check(f, lat, lon)
        self._was_dark[f["id"]] = False

    def _reappear_check(self, f: Dict[str, Any], lat: float, lon: float) -> None:
        """Voice moment: a tagged craft comes back after 30+ min of silence."""
        if not self._was_dark.get(f["id"]):
            return
        if not self.announcer:
            return
        label = f.get("name") or f.get("callsign") or f.get("craft_id")
        miles = int(_haversine(self.home[0], self.home[1], lat, lon))
        self.announcer.say(
            f"{label} is back on the radar, {miles} miles away.",
            category="air" if f["kind"] == "air" else "sea",
            dedup_key=f"jrny{f['id']}", dedup_seconds=3600)
