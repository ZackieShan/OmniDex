"""SkyDex ADS-B receiver — reads dump1090/readsb JSON and normalizes aircraft.

Primary source: local dump1090-fa or readsb HTTP JSON feed.
Fallback: OpenSky Network API (authenticated, with your credentials).

Output: normalized aircraft dicts ready for the enrichment and classification
pipeline.  Each dict contains the fields the database expects:
  hex, lat, lon, altitude, ground_speed, track, callsign, squawk,
  category, distance_miles, timestamp
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Haversine math
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in statute miles."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2 (degrees, 0=N, clockwise)."""
    dlon = math.radians(lon2 - lon1)
    la1, la2 = math.radians(lat1), math.radians(lat2)
    y = math.sin(dlon) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# ---------------------------------------------------------------------------
# OpenSky fallback — OAuth2 client credentials (Bearer token)
# ---------------------------------------------------------------------------
# As of 2025 OpenSky ONLY accepts the OAuth2 client-credentials flow. HTTP
# Basic Auth with username/password is no longer accepted, so we must exchange
# the client_id/client_secret for a short-lived Bearer token and refresh it.
_OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)


class _OpenSkyFallback:
    """OpenSky Network API fallback using OAuth2 Bearer tokens.

    Authenticated users get a much larger daily credit budget than anonymous
    access (which OpenSky has heavily restricted). Tokens expire after ~30
    minutes, so we cache and refresh them as needed.
    """

    URL = "https://opensky-network.org/api/states/all"
    TIMEOUT = 15
    # Fetch cadence is adaptive (see _poll_seconds): faster by day, slower at
    # night to stay inside OpenSky's ~4000 credits/day budget. A local RTL-SDR
    # (dump1090) removes the limit entirely (~1s updates).

    def __init__(
        self,
        lamin: float,
        lomin: float,
        lamax: float,
        lomax: float,
        client_id: str = "",
        client_secret: str = "",
        poll_day: float = 15.0,
        poll_night: float = 60.0,
        active_start: int = 9,
        active_end: int = 22,
    ):
        self._bbox = f"?lamin={lamin}&lomin={lomin}&lamax={lamax}&lomax={lomax}"
        self._client_id = client_id
        self._client_secret = client_secret
        # Adaptive cadence: poll_day between [active_start, active_end) local,
        # poll_night otherwise. Conserves the OpenSky daily credit budget.
        self._poll_day = poll_day
        self._poll_night = poll_night
        self._active_start = active_start
        self._active_end = active_end
        self._last_good: List[Dict[str, Any]] = []
        self._last_fetch = 0.0
        self._auth_ok = bool(client_id and client_secret)  # False once creds rejected
        self._error_count = 0
        self._logged_first = False
        # Token cache
        self._token: Optional[str] = None
        self._token_expiry = 0.0

    # -- OAuth2 token management -------------------------------------------

    def _get_token(self) -> Optional[str]:
        """Return a valid Bearer token, fetching/refreshing if needed."""
        if not (self._client_id and self._client_secret):
            return None
        if self._token and time.time() < self._token_expiry:
            return self._token

        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        req = urllib.request.Request(
            _OPENSKY_TOKEN_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "SkyDex/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            self._token = data.get("access_token")
            # Refresh 60s before the token actually expires.
            expires_in = float(data.get("expires_in", 1800))
            self._token_expiry = time.time() + max(60.0, expires_in - 60.0)
            if self._token:
                logger.info("OpenSky OAuth2 token acquired (expires in %.0fs)", expires_in)
            return self._token
        except urllib.error.HTTPError as e:
            self._auth_ok = False
            logger.warning(
                "OpenSky token request rejected (HTTP %d). Check opensky_client_id/"
                "opensky_client_secret in config.py. Falling back to anonymous.",
                e.code,
            )
            return None
        except Exception as e:
            logger.warning("OpenSky token request failed: %s", e)
            return None

    def _poll_seconds(self) -> float:
        """Current cadence: faster during local waking hours, slower overnight."""
        hour = time.localtime().tm_hour
        active = self._active_start <= hour < self._active_end
        return self._poll_day if active else self._poll_night

    def read(self) -> List[Dict[str, Any]]:
        now = time.time()
        if now - self._last_fetch < self._poll_seconds():
            return self._last_good
        self._last_fetch = now

        url = self.URL + self._bbox
        req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})

        authed = False
        if self._auth_ok:
            token = self._get_token()
            if token:
                req.add_header("Authorization", f"Bearer {token}")
                authed = True

        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.load(resp)
            states = data.get("states") or []
            aircraft = []
            for s in states:
                if s[5] is None or s[6] is None:
                    continue
                aircraft.append({
                    "hex": str(s[0]).upper().strip(),
                    "callsign": (s[1] or "").strip(),
                    "lon": float(s[5]),
                    "lat": float(s[6]),
                    "altitude": float(s[13]) if s[13] is not None else (float(s[7]) if s[7] is not None else None),
                    "ground_speed": float(s[9]) * 1.94384 if s[9] is not None else None,  # m/s -> knots
                    "track": float(s[10]) if s[10] is not None else None,
                    "vertical_rate": float(s[11]) if s[11] is not None else None,
                    "squawk": s[14] or "",
                    "category": "",
                    "timestamp": time.time(),
                })
            self._last_good = aircraft
            self._error_count = 0
            if len(aircraft) > 0 or not self._logged_first:
                # Log first OpenSky response and whenever we get aircraft
                self._logged_first = True
                logger.info("OpenSky (%s): %d aircraft", "auth" if authed else "anon", len(aircraft))
            return aircraft

        except urllib.error.HTTPError as e:
            self._error_count += 1
            if e.code == 401 or e.code == 403:
                # Token expired or rejected — drop it so the next read refreshes.
                self._token = None
                self._token_expiry = 0.0
                logger.warning("OpenSky request rejected (HTTP %d); will refresh token.", e.code)
            elif e.code == 429:
                # OpenSky rate limit window is 5+ minutes. Back off hard.
                self._last_fetch = now + 300  # 5 minute cooldown
                logger.warning("OpenSky rate limited (HTTP 429). Cooling off for 5 minutes.")
            else:
                logger.debug("OpenSky HTTP error %d: %s", e.code, e.reason)
            return self._last_good

        except Exception as e:
            self._error_count += 1
            if self._error_count <= 3:
                logger.warning("OpenSky fetch failed: %s", e)
            return self._last_good


# ---------------------------------------------------------------------------
# Main receiver
# ---------------------------------------------------------------------------

class ADSBReceiver:
    """Polls a local dump1090/readsb instance and returns normalized aircraft.

    Usage::

        receiver = ADSBReceiver(home_lat=41.1635, home_lon=-73.1262)
        receiver.start()
        contacts = receiver.get_all_contacts()
        for hex_code, ac in contacts.items():
            print(ac["hex"], ac["distance_miles"], ac["callsign"])
        receiver.stop()
    """

    def __init__(
        self,
        home_lat: float,
        home_lon: float,
        dump1090_url: str = "http://localhost:8080/data/aircraft.json",
        poll_interval: float = 1.0,
        enable_opensky_fallback: bool = True,
        opensky_client_id: str = "",
        opensky_client_secret: str = "",
        opensky_poll_day: float = 15.0,
        opensky_poll_night: float = 60.0,
        opensky_active_start: int = 9,
        opensky_active_end: int = 22,
    ):
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.dump1090_url = dump1090_url
        self.poll_interval = poll_interval
        self.enable_opensky_fallback = enable_opensky_fallback

        # Candidate local decoder JSON endpoints, tried in order until one
        # responds (readsb / dump1090-fa / tar1090 / skyaware all differ).
        self._dump1090_urls: List[str] = []
        for u in (
            dump1090_url,
            "http://localhost:8080/data/aircraft.json",
            "http://localhost/tar1090/data/aircraft.json",
            "http://localhost/skyaware/data/aircraft.json",
            "http://localhost:8080/data.json",
            "http://localhost/data/aircraft.json",
        ):
            if u and u not in self._dump1090_urls:
                self._dump1090_urls.append(u)
        self._working_url: Optional[str] = None

        self._contacts: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._opensky: Optional[_OpenSkyFallback] = None

        # Source tracking for diagnostics
        self._source_stats = {"dump1090": 0, "opensky": 0, "errors": 0, "last_source": "none"}

        if enable_opensky_fallback:
            # ~30mi N/S, ~40mi E/W box around home — enough margin for the
            # in-range filter while keeping the OpenSky credit cost at 1/call.
            self._opensky = _OpenSkyFallback(
                home_lat - 0.45, home_lon - 0.6,
                home_lat + 0.45, home_lon + 0.6,
                client_id=opensky_client_id,
                client_secret=opensky_client_secret,
                poll_day=opensky_poll_day,
                poll_night=opensky_poll_night,
                active_start=opensky_active_start,
                active_end=opensky_active_end,
            )

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("ADSBReceiver started (home=%.4f,%.4f  poll=%.1fs)", self.home_lat, self.home_lon, self.poll_interval)

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("ADSBReceiver stopped")

    def _run_loop(self) -> None:
        consecutive_errors = 0
        while self._running:
            try:
                aircraft = self._fetch()
                if aircraft:
                    self._process(aircraft)
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors <= 5:
                        logger.warning("No aircraft data (attempt %d)", consecutive_errors)
            except Exception as e:
                consecutive_errors += 1
                self._source_stats["errors"] += 1
                if consecutive_errors <= 3:
                    logger.warning("Receiver error #%d: %s", consecutive_errors, e)
            time.sleep(self.poll_interval)

    # -- fetching -----------------------------------------------------------

    def _fetch(self) -> List[Dict[str, Any]]:
        """Try a local decoder (readsb/dump1090/tar1090) first, then OpenSky."""
        # Try the known-good URL first, then the rest of the candidates.
        candidates = ([self._working_url] if self._working_url else []) + \
                     [u for u in self._dump1090_urls if u != self._working_url]
        for url in candidates:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.load(resp)
            except urllib.error.URLError:
                continue  # not running at this path — try the next
            except Exception as e:
                logger.debug("local decoder error at %s: %s", url, e)
                continue

            if self._working_url != url:
                logger.info("Local ADS-B decoder found at %s", url)
                self._working_url = url
            aircraft_list = data.get("aircraft", [])
            self._source_stats["dump1090"] += 1
            self._source_stats["last_source"] = "dump1090"
            if aircraft_list:
                logger.info("dump1090: %d aircraft", len(aircraft_list))
            return aircraft_list  # running (even if empty) — trust the local SDR

        # No local decoder responded — fall back to OpenSky.
        if self._working_url:
            logger.info("Local decoder no longer responding, switching to OpenSky fallback")
            self._working_url = None
        if self._opensky and self.enable_opensky_fallback:
            result = self._opensky.read()
            if result:
                self._source_stats["opensky"] += 1
                self._source_stats["last_source"] = "opensky"
            return result

        return []

    def _process(self, raw_list: List[Dict[str, Any]]) -> None:
        """Normalize raw aircraft dicts and compute distances."""
        now = time.time()
        contacts: Dict[str, Dict[str, Any]] = {}

        for raw in raw_list:
            try:
                hex_code = raw.get("hex", "").upper().strip()
                if not hex_code:
                    continue

                # Extract lat/lon
                lat = raw.get("lat")
                lon = raw.get("lon")
                if lat is None or lon is None:
                    continue

                lat_f = float(lat)
                lon_f = float(lon)

                # Compute distance from home
                dist = _haversine(self.home_lat, self.home_lon, lat_f, lon_f)

                # Normalize altitude (dump1090 uses alt_baro; OpenSky uses altitude)
                alt = raw.get("alt_baro")
                if alt is None:
                    alt = raw.get("altitude")
                if alt is not None:
                    try:
                        alt = float(alt)
                        # Filter out "ground" string values
                        if alt < -1000:
                            alt = None
                    except (TypeError, ValueError):
                        alt = None

                # Normalize speed
                spd = raw.get("gs")
                if spd is None:
                    spd = raw.get("ground_speed")
                if spd is not None:
                    try:
                        spd = float(spd)
                    except (TypeError, ValueError):
                        spd = None

                # Normalize track
                trk = raw.get("track")
                if trk is not None:
                    try:
                        trk = float(trk)
                    except (TypeError, ValueError):
                        trk = None

                # Vertical rate
                vr = raw.get("baro_rate")
                if vr is None:
                    vr = raw.get("vert_rate")
                if vr is not None:
                    try:
                        vr = float(vr)
                    except (TypeError, ValueError):
                        vr = None

                # Callsign — dump1090 uses "flight", OpenSky uses "callsign"
                callsign = raw.get("flight", raw.get("callsign", "")) or ""
                callsign = callsign.strip()

                contacts[hex_code] = {
                    "hex": hex_code,
                    "callsign": callsign,
                    "lat": lat_f,
                    "lon": lon_f,
                    "altitude": alt,
                    "ground_speed": spd,
                    "track": trk,
                    "vertical_rate": vr,
                    "squawk": str(raw.get("squawk", "")).strip(),
                    "category": raw.get("category", ""),
                    "distance_miles": round(dist, 2),
                    "bearing": round(_bearing(self.home_lat, self.home_lon, lat_f, lon_f), 1),
                    "timestamp": now,
                }
            except (TypeError, ValueError, KeyError) as e:
                logger.debug("Skipping malformed aircraft record: %s", e)
                continue

        with self._lock:
            self._contacts = contacts

    # -- public API ---------------------------------------------------------

    def get_all_contacts(self) -> Dict[str, Dict[str, Any]]:
        """Return ALL contacts regardless of distance."""
        with self._lock:
            return dict(self._contacts)

    def get_contacts_in_range(self, radius_miles: float) -> List[Dict[str, Any]]:
        """Return contacts within radius_miles (horizontal), sorted by distance."""
        with self._lock:
            contacts = list(self._contacts.values())
        in_range = [c for c in contacts if c.get("distance_miles", 999) <= radius_miles]
        in_range.sort(key=lambda c: c.get("distance_miles", 999))
        return in_range

    def get_visible_contacts(
        self,
        base_radius_miles: float,
        miles_per_1000ft: float = 0.0,
        max_radius_miles: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Return contacts you could plausibly *see*, sorted by distance.

        Effective range grows with altitude (you can see high jets from much
        farther than low GA), capped at max_radius_miles. With miles_per_1000ft=0
        this behaves exactly like get_contacts_in_range(base_radius_miles).
        """
        with self._lock:
            contacts = list(self._contacts.values())

        cap = max_radius_miles if max_radius_miles else base_radius_miles

        def visible(c: Dict[str, Any]) -> bool:
            dist = c.get("distance_miles", 999)
            alt = c.get("altitude") or 0
            effective = base_radius_miles + (alt / 1000.0) * miles_per_1000ft
            if effective > cap:
                effective = cap
            return dist <= effective

        out = [c for c in contacts if visible(c)]
        out.sort(key=lambda c: c.get("distance_miles", 999))
        return out

    def get_contact(self, hex_code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._contacts.get(hex_code.upper())

    @property
    def contact_count(self) -> int:
        with self._lock:
            return len(self._contacts)

    def get_source_stats(self) -> Dict[str, Any]:
        """Diagnostic info about data sources."""
        return dict(self._source_stats)

    def get_health(self) -> Dict[str, Any]:
        """Health check info for /api/health."""
        with self._lock:
            contacts = list(self._contacts.values())
        return {
            "running": self._running and self._thread is not None and self._thread.is_alive(),
            "contact_count": len(contacts),
            "contacts_in_range_5mi": len([c for c in contacts if c.get("distance_miles", 999) <= 5.0]),
            "contacts_in_range_20mi": len([c for c in contacts if c.get("distance_miles", 999) <= 20.0]),
            "nearest_contact_mi": round(min((c.get("distance_miles", 999) for c in contacts), default=-1), 2),
            "source_stats": self.get_source_stats(),
            "opensky_auth_ok": self._opensky._auth_ok if self._opensky else None,
            "opensky_errors": self._opensky._error_count if self._opensky else 0,
        }
