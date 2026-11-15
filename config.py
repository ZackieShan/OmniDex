"""SkyDex configuration — single source of truth for settings.

Secrets (API keys) live in the project-root .env file so they can be rotated
without code edits; everything else is a plain default here. Runtime-tunable
values can additionally be overridden from ~/.skydex/settings.json via
settings.py (applied in main.py at startup).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

VERSION = "1.2.1"


def _load_dotenv() -> None:
    """Tiny stdlib .env loader (KEY=VALUE lines, # comments). Real environment
    variables win over the file, so systemd Environment= overrides still work."""
    path = Path(__file__).resolve().parent / ".env"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class LocationConfig:
    """Your location — right-click your house in Google Maps and paste here.
    (The defaults are the KBDR airfield, a public landmark — not a home.)"""
    name: str = "Stratford, CT"
    lat: float = 41.1635      # ← put YOUR latitude here
    lon: float = -73.1262     # ← put YOUR longitude here
    home_airport_icao: str = "KBDR"
    home_airport_name: str = "Igor I. Sikorsky Memorial Airport"
    zip_code: str = "06615"


@dataclass(frozen=True)
class RangeConfig:
    """Detection radius and altitude limits.

    radius_miles is the "nearby" radius — the Live view only shows aircraft
    within this many statute miles of home, and only these count toward the
    Planedex. Lower it to ~3 for "right overhead" only; raise it to ~15-20 to
    catch aircraft on approach/departure that are still visible from the ground.
    NOTE: without a local RTL-SDR you only see aircraft that broadcast ADS-B
    AND are in OpenSky's feed — many small GA aircraft, biplanes, and some
    helicopters won't appear until you add the SDR dongle.
    """
    radius_miles: float = 5.0           # base "nearby" range for LOW traffic (statute miles)
    # You can see high aircraft from much farther than low ones, so the visible
    # range grows with altitude: effective_range = radius_miles + (alt_ft/1000) *
    # visibility_miles_per_1000ft, capped at max_visible_radius_miles. Defaults:
    # a 1,000ft GA plane ~2.6mi, an 8,000ft regional ~6.8mi, a 33,000ft jet ~22mi.
    visibility_miles_per_1000ft: float = 0.6
    max_visible_radius_miles: float = 25.0
    max_altitude_ft: float = 45000.0    # ceiling
    min_altitude_ft: float = -100.0     # allow ground level
    stale_seconds: float = 60.0         # how long before we drop a contact


@dataclass(frozen=True)
class ReceiverConfig:
    """Local ADS-B receiver settings."""
    dump1090_url: str = "http://localhost:8080/data/aircraft.json"
    # Alternative paths that different dump1090 packages use:
    # readsb:  http://localhost:8080/data/aircraft.json
    # tar1090: http://localhost/tar1090/data/aircraft.json
    poll_interval_seconds: float = 1.0
    fallback_opensky: bool = True
    opensky_bbox_degrees: float = 1.0   # lat/lon box for OpenSky fallback
    # Adaptive OpenSky fallback cadence. OpenSky's authenticated budget is
    # ~4000 credits/day, so we poll faster during waking hours and back off
    # overnight to conserve calls. Day 15s + night 60s ≈ 3,800 calls/day —
    # comfortably under budget. (A local RTL-SDR/dump1090 bypasses all of this
    # with true ~1s updates.) Hours are LOCAL to the Pi, 24h clock.
    opensky_poll_day_seconds: float = 15.0
    opensky_poll_night_seconds: float = 60.0
    opensky_active_start_hour: int = 9    # 09:00 local — start fast polling
    opensky_active_end_hour: int = 22     # 22:00 local — back off after this
    # OpenSky OAuth2 client credentials (create an API client on your
    # OpenSky account page). As of 2025 OpenSky ONLY accepts OAuth2 client
    # credentials — HTTP Basic Auth with username/password no longer works.
    opensky_client_id: str = field(default_factory=lambda: _env("SKYDEX_OPENSKY_CLIENT_ID"))
    opensky_client_secret: str = field(default_factory=lambda: _env("SKYDEX_OPENSKY_CLIENT_SECRET"))


@dataclass(frozen=True)
class AcarsConfig:
    """ACARS / VDL-2 datalink — the planes' text messages.

    SkyDex doesn't demodulate ACARS itself; run acarsdec and/or dumpvdl2 on
    their own RTL-SDR(s) and point their JSON-over-UDP output at udp_port
    (see acars.py's docstring for the exact commands). Messages then appear
    as a chat thread on each plane's Dex detail page.
    """
    enabled: bool = True
    udp_port: int = 5555        # where acarsdec/dumpvdl2 send their JSON
    max_messages: int = 600     # rolling buffer (in memory only)


@dataclass(frozen=True)
class EnrichmentConfig:
    """Third-party API settings."""
    adsbdb_base_url: str = "https://api.adsbdb.com/v0"
    planespotters_base_url: str = "https://api.planespotters.net/pub/photos"
    nws_base_url: str = "https://api.weather.gov"
    openmeteo_base_url: str = "https://api.open-meteo.com/v1"
    request_timeout_seconds: float = 10.0
    cache_ttl_seconds: int = 86400      # 24h for aircraft metadata
    photo_cache_ttl_seconds: int = 604800  # 7 days for photos


@dataclass(frozen=True)
class MarineConfig:
    """SeaDex — AIS (marine traffic) settings.

    Reads vessel JSON from a local AIS-catcher instance. Run AIS-catcher on its
    own RTL-SDR tuned to the AIS band (161.975 / 162.025 MHz) with its web
    server enabled, e.g.:  AIS-catcher -d <serial> -N 8100  ->  serves
    http://localhost:8100/api/ships.json
    """
    enabled: bool = True
    ais_json_url: str = "http://localhost:8100/api/ships.json"
    poll_interval_seconds: float = 5.0
    radius_miles: float = 10.0          # show vessels within 10 mi (covers the Sound)
    stale_seconds: float = 180.0        # drop a vessel not heard from in this long
    # NWS marine forecast zone for marine advisories (Small Craft Advisory, etc.).
    # ANZ335 = Long Island Sound West of New Haven CT / Port Jefferson NY.
    nws_marine_zone: str = "ANZ335"

    # -- AISHub cloud fallback (like OpenSky for ADS-B) ---------------------
    # When the local AIS-catcher isn't reachable, pull vessels from AISHub.
    # You must contribute data to AISHub to be assigned a username; once you
    # have it, paste it here and flip aishub_enabled on. AISHub rate-limits to
    # one request per minute, so the fallback polls slowly.
    # Both cloud feeds below request a bounding box covering `radius_miles`.
    aishub_enabled: bool = False
    aishub_username: str = ""           # assigned by AISHub after your feed is verified
    aishub_url: str = "https://data.aishub.net/ws.php"
    aishub_poll_interval_seconds: float = 60.0   # AISHub minimum is 1 req/min
    # AISHub static-data enrichment: once your station is an ACTIVE contributor,
    # set this True (and aishub_username) to fill in ship type / IMO that the live
    # feed is missing — fixes vessels stuck classified as "Other".
    aishub_api_enabled: bool = False

    # -- AISStream.io cloud fallback (free WebSocket feed, just needs a key) -
    # Preferred over AISHub: no data-contribution requirement, real-time push.
    # Get a free key at https://aisstream.io and paste it below. Needs the
    # 'websocket-client' package (pip install websocket-client).
    aisstream_enabled: bool = True
    aisstream_api_key: str = field(default_factory=lambda: _env("SKYDEX_AISSTREAM_API_KEY"))
    aisstream_url: str = "wss://stream.aisstream.io/v0/stream"


@dataclass(frozen=True)
class GameConfig:
    """Game mechanics tuning."""
    # Evolution tiers
    evolution_tiers: Tuple[Tuple[str, int], ...] = (
        ("Spotted", 1),
        ("Tracked", 5),
        ("Tagged", 15),
        ("Bonded", 40),
    )

    # Rarity thresholds (detection count across all users is proxy)
    # For personal rarity: how many times YOU have seen this airframe
    rarity_personal_common: int = 10
    rarity_personal_uncommon: int = 5
    rarity_personal_rare: int = 2
    rarity_personal_epic: int = 1

    # Commuter detection
    commuter_min_detections: int = 3
    commuter_day_tolerance: int = 1   # day-of-week +/- 1 counts as match
    commuter_hour_tolerance: int = 2  # hour-of-day +/- 2 counts as match

    # Contrail
    contrail_altitude_threshold_ft: float = 26000.0

    # Telemetry logging interval: minimum seconds between logged telemetry rows
    # for the same aircraft. The raw detections table feeds the altitude chart.
    telemetry_interval_seconds: float = 15.0

    # Session gap: how long an aircraft must be OUT of range before its next
    # appearance counts as a new "sighting". Continuous presence (e.g. a trainer
    # doing laps) is one sighting; leaving and returning later is a new one.
    session_gap_seconds: float = 600.0  # 10 minutes

    # Photo backfill: how often (seconds) to fetch a real photo for one logged
    # airframe that doesn't have one yet (paid AeroDataBox). Each airframe is
    # tried once and remembered, so this only spends credits clearing the
    # backlog, then idles until new aircraft are logged.
    photo_backfill_interval_seconds: float = 10.0

    # Shiny triggers
    shiny_first_of_day: bool = True
    shiny_first_of_type: bool = True
    shiny_milestone_interval: int = 100   # every N detections


@dataclass(frozen=True)
class KioskConfig:
    """Display settings for the JRP7002."""
    screen_width: int = 1024
    screen_height: int = 600
    refresh_interval_ms: int = 1000     # live data poll rate
    timezone: str = "America/New_York"
    date_format: str = "%a %b %-d"      # "Mon Jun 23"
    time_format: str = "%H:%M"          # 24-hour, e.g. "14:30"


@dataclass(frozen=True)
class AtmoConfig:
    """AtmoDex — astronomy / sky-watching module.

    The core (moon phase, sun/twilight, visible planets, meteor showers, sky
    tips, viewing quality) is computed locally with no API. The optional extras
    below use RapidAPI / NASA and are cached for hours (they change slowly).
    """
    enabled: bool = True
    # NASA Astronomy Picture of the Day (free key from api.nasa.gov).
    nasa_apod_key: str = field(default_factory=lambda: _env("SKYDEX_NASA_API_KEY"))
    # Shared RapidAPI key (used only for satellite near-miss/conjunction data now).
    rapidapi_key: str = field(default_factory=lambda: _env("SKYDEX_RAPIDAPI_KEY"))
    # Satellite passes — computed locally via SGP4 (free). NORAD 25544 = ISS.
    iss_passes_enabled: bool = True
    iss_norad_id: int = 25544
    iss_min_elevation: int = 15
    # Satellites we compute passes for (NORAD ids): ISS, Tiangong, Hubble,
    # Terra, Aqua, NOAA-19. (All local SGP4 — adding more just costs a little CPU.)
    tracked_satellites: Tuple[int, ...] = (25544, 48274, 20580, 25994, 27424, 33591)
    # Passes are computed locally from CelesTrak TLEs via SGP4 — free, no API.
    # Needs the 'sgp4' package:  sudo apt install python3-sgp4  (or pip install sgp4)
    # How long to cache the slow-changing API data (seconds).
    apod_cache_seconds: int = 21600        # 6h
    passes_cache_seconds: int = 21600      # 6h
    # Spare keys for alternate providers (not wired in Phase 1).
    worldweather_key: str = field(default_factory=lambda: _env("SKYDEX_WORLDWEATHER_KEY"))
    marea_tide_key: str = field(default_factory=lambda: _env("SKYDEX_MAREA_TIDE_KEY"))


@dataclass(frozen=True)
class LandConfig:
    """LandDex — trains. Metro-North schedule board for Stratford station
    (static GTFS, downloaded weekly) + live Amtrak pass-throughs (Amtraker v3).
    Both free, no keys."""
    enabled: bool = True
    station_name: str = "Stratford"
    radius_miles: float = 15.0       # Amtrak trains inside this show as "passing"


@dataclass(frozen=True)
class SkyDexConfig:
    """Top-level config container."""
    location: LocationConfig = field(default_factory=LocationConfig)
    range: RangeConfig = field(default_factory=RangeConfig)
    receiver: ReceiverConfig = field(default_factory=ReceiverConfig)
    acars: AcarsConfig = field(default_factory=AcarsConfig)
    enrichment: EnrichmentConfig = field(default_factory=EnrichmentConfig)
    game: GameConfig = field(default_factory=GameConfig)
    marine: MarineConfig = field(default_factory=MarineConfig)
    atmo: AtmoConfig = field(default_factory=AtmoConfig)
    land: LandConfig = field(default_factory=LandConfig)
    kiosk: KioskConfig = field(default_factory=KioskConfig)
    db_path: str = "~/.skydex/skydex.db"
    # Locally-synced reference databases (populated by sync_faa_db.py and
    # sync_opensky_db.py). Used for fast, offline, rate-limit-free enrichment.
    faa_db_path: str = "~/.skydex/faa_registry.db"
    opensky_db_path: str = "~/.skydex/opensky_aircraft.db"
    airports_db_path: str = "~/.skydex/airports.db"
    # On-disk image cache (downloaded photos are saved here so they're never
    # re-fetched). Plenty of room on the Pi; survives restarts.
    photo_cache_dir: str = "~/.skydex/photos"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
