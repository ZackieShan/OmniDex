"""SkyDex runtime settings — a JSON overlay on top of config.py defaults.

config.py holds the hard defaults; this module holds the knobs that should be
tunable from the /admin page (or the kiosk settings drawer) WITHOUT editing
code. Values persist in ~/.skydex/settings.json, which lives outside the
project folder so Termius folder-replace deploys never wipe them.

Two kinds of settings:
  - live:    read by the frontend (or per-request on the server); apply instantly.
  - restart: baked into receiver constructors at startup; the admin page marks
             these and offers a Restart button.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(os.path.expanduser("~/.skydex/settings.json"))

# key -> spec. Order here is the display order on the admin page.
# type: "float" | "int" | "bool" | "str"
SPEC: Dict[str, Dict[str, Any]] = {
    # --- Air ---------------------------------------------------------------
    "air_radius_miles": {
        "default": 5.0, "type": "float", "group": "Air", "restart": True,
        "label": "Aircraft radius (mi)",
        "help": "Base 'nearby' range for low traffic; grows with altitude."},
    "opensky_poll_day_seconds": {
        "default": 15.0, "type": "float", "group": "Air", "restart": True,
        "label": "OpenSky poll — day (s)",
        "help": "Fallback poll rate during active hours. Beware the ~4000/day budget."},
    "opensky_poll_night_seconds": {
        "default": 60.0, "type": "float", "group": "Air", "restart": True,
        "label": "OpenSky poll — night (s)",
        "help": "Slower overnight rate to conserve API credits."},
    "opensky_active_start_hour": {
        "default": 9, "type": "int", "group": "Air", "restart": True,
        "label": "Active hours start (0-23)", "help": "Local hour fast polling begins."},
    "opensky_active_end_hour": {
        "default": 22, "type": "int", "group": "Air", "restart": True,
        "label": "Active hours end (0-23)", "help": "Local hour fast polling ends."},

    # --- Sea ---------------------------------------------------------------
    "sea_radius_miles": {
        "default": 10.0, "type": "float", "group": "Sea", "restart": True,
        "label": "Vessel radius (mi)", "help": "Show vessels within this range."},

    # --- Display -----------------------------------------------------------
    "night_dim_enabled": {
        "default": True, "type": "bool", "group": "Display", "restart": False,
        "label": "Auto night dim",
        "help": "Dim the screen from civil dusk to civil dawn (computed locally)."},
    "night_dim_brightness": {
        "default": 0.55, "type": "float", "group": "Display", "restart": False,
        "label": "Night brightness (0.2-1.0)", "help": "Screen brightness while dimmed."},
    "attract_enabled": {
        "default": True, "type": "bool", "group": "Display", "restart": False,
        "label": "Attract mode",
        "help": "After idle timeout, cycle highlights (catches, records, tonight's sky)."},
    "attract_idle_minutes": {
        "default": 10, "type": "int", "group": "Display", "restart": False,
        "label": "Attract after idle (min)", "help": "Minutes without touch before attract mode."},

    # --- Alerts ------------------------------------------------------------
    "iss_toast_enabled": {
        "default": True, "type": "bool", "group": "Alerts", "restart": False,
        "label": "ISS pass alerts",
        "help": "Toast + sound ~10 min before a good ISS pass."},
    "iss_toast_min_elevation": {
        "default": 30, "type": "int", "group": "Alerts", "restart": False,
        "label": "ISS alert min elevation (°)",
        "help": "Only alert for passes peaking above this. 30°+ is a good show."},

    # --- Audio -------------------------------------------------------------
    "liveatc_enabled": {
        "default": True, "type": "bool", "group": "Audio", "restart": False,
        "label": "LiveATC button", "help": "Show the tap-to-listen tower audio button."},
    "liveatc_url": {
        "default": "https://s1-fmt2.liveatc.net/kbdr_twr", "type": "str",
        "group": "Audio", "restart": False,
        "label": "LiveATC stream URL",
        "help": "KBDR feed mount. If silent, find the working mount on liveatc.net and paste it here."},

    # --- Data --------------------------------------------------------------
    "sse_enabled": {
        "default": True, "type": "bool", "group": "Data", "restart": False,
        "label": "Live push (SSE)",
        "help": "Push contacts to the kiosk instead of 1s polling. Falls back automatically."},
    "detections_retention_days": {
        "default": 30, "type": "int", "group": "Data", "restart": False,
        "label": "Raw telemetry retention (days)",
        "help": "Raw per-15s detections older than this are pruned nightly. Dex/stats keep forever."},

    # --- Road (LandDex) ------------------------------------------------------
    "tomtom_key": {
        "default": "", "type": "str", "group": "Road", "restart": False,
        "label": "TomTom API key (optional)",
        "help": "Free key from developer.tomtom.com unlocks LIVE traffic on the commute cards. Blank = typical times via OSRM."},
    "road_scanner_url": {
        "default": "", "type": "str", "group": "Road", "restart": False,
        "label": "Scanner stream URL (optional)",
        "help": "A Broadcastify stream URL (e.g. CT State Police Troop G / I-95 corridor) enables the Scanner listen button."},
    "nycdot_speeds_enabled": {
        "default": True, "type": "bool", "group": "Road", "restart": False,
        "label": "NYC highway speeds",
        "help": "Live speed detectors on the drive-to-the-city corridors (I-95/Cross Bronx, Hutch, Bruckner) via your NYC DOT key."},

    # --- Rail (live map) ------------------------------------------------------
    "mta_rt_url": {
        "default": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/mnr%2Fgtfs-mnr",
        "type": "str", "group": "Rail", "restart": False,
        "label": "MTA GTFS-RT feed URL",
        "help": "Metro-North realtime positions feed. If it returns 403, get a free key at api.mta.info and paste it below."},
    "mta_api_key": {
        "default": "", "type": "str", "group": "Rail", "restart": False,
        "label": "MTA API key (only if needed)",
        "help": "Sent as x-api-key. Most MTA feeds are keyless now — leave blank unless the live map says otherwise."},

    # --- Voice ---------------------------------------------------------------
    "voice_enabled": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Voice announcements",
        "help": "The kiosk speaks (Piper TTS or espeak-ng — see docs). Rare catches, ISS passes, Acelas, emergencies."},
    "voice_quiet_start_hour": {
        "default": 21, "type": "int", "group": "Voice", "restart": False,
        "label": "Quiet hours start (0-23)", "help": "No talking after this local hour."},
    "voice_quiet_end_hour": {
        "default": 8, "type": "int", "group": "Voice", "restart": False,
        "label": "Quiet hours end (0-23)", "help": "Talking resumes at this local hour."},
    "voice_air": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Announce aircraft", "help": "Rare/epic catches and emergency squawks."},
    "voice_sea": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Announce vessels", "help": "Superyachts and rare vessels."},
    "voice_rail": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Announce trains", "help": "Acelas passing Stratford."},
    "voice_iss": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Announce ISS passes", "help": "A 10-minute heads-up before good passes."},
    "voice_storm": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Announce weather records/storms", "help": "Record breakers and named storms."},
    "voice_earcons": {
        "default": True, "type": "bool", "group": "Voice", "restart": False,
        "label": "Chimes before announcements", "help": "A short per-category tone (train horn-ish for rail, bell for sea…) before the voice speaks."},
    "ntfy_topic": {
        "default": "", "type": "str", "group": "Voice", "restart": False,
        "label": "Phone push topic (ntfy.sh)",
        "help": "Pick any unique topic name (e.g. skydex-family-8137), subscribe in the free ntfy app on your phones, and announcements also push there. Blank = off."},

    # --- Ether ---------------------------------------------------------------
    "ether_enabled": {
        "default": True, "type": "bool", "group": "Ether", "restart": True,
        "label": "EtherDex", "help": "Listen to the RF neighborhood (needs rtl-433 + the repurposed dongle)."},
    "ether_device": {
        "default": "", "type": "str", "group": "Ether", "restart": True,
        "label": "rtl_433 device selector",
        "help": "Blank = first free dongle. Or pin by serial, e.g. ':00000102' (the old AIS one)."},
    "ether_freqs": {
        "default": "433.92M,315M", "type": "str", "group": "Ether", "restart": True,
        "label": "Frequencies",
        "help": "Comma list; hops each minute — more bands = less time on each. "
                "433.92M sensors/weather/doorbells · 915M utility meters "
                "· 345M security contacts · 315M US key fobs/garage/TPMS. "
                "Good spread: 433.92M,915M,345M."},
    "ether_bt": {
        "default": True, "type": "bool", "group": "Ether", "restart": True,
        "label": "Bluetooth sweep", "help": "5-min scans on the Pi's built-in radio (named devices only)."},
    "ether_wifi": {
        "default": True, "type": "bool", "group": "Ether", "restart": True,
        "label": "WiFi sweep",
        "help": "See the WiFi networks broadcasting nearby (the Pi's own radio, no dongle). "
                "Network names + signal only — never traffic, clients, or people."},
    "ether_audio_device": {
        "default": "", "type": "str", "group": "Ether", "restart": True,
        "label": "Audio dongle (live tuner)",
        "help": "Serial of a dedicated dongle for WX/marine/ISS listening, e.g. ':0303'. "
                "With one set, listening never pauses sensor hunting. Blank = share the sensor dongle."},
    "iss_auto_listen": {
        "default": True, "type": "bool", "group": "Ether", "restart": False,
        "label": "Auto-listen to ISS passes",
        "help": "When the ISS passes 25°+ overhead, tune 145.800 automatically. "
                "Needs the audio dongle; does nothing without it."},
    "antenna_tuner": {
        "default": False, "type": "bool", "group": "Ether", "restart": False,
        "label": "Antenna mode (off-air tuner chips)",
        "help": "Show the live RF listening chips (WX radio, Marine 16, ISS 145.800). "
                "Mostly static-flavored theater next to the internet streams — "
                "but the wiring is all here the day someone gets curious."},

    # --- Fun ---------------------------------------------------------------
    "quiz_enabled": {
        "default": True, "type": "bool", "group": "Fun", "restart": False,
        "label": "Quiz button", "help": "Show the Professor's Quiz button."},
}


def _coerce(key: str, value: Any) -> Any:
    """Coerce+validate a raw (possibly string) value to the spec'd type."""
    spec = SPEC[key]
    t = spec["type"]
    if t == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if t == "int":
        return int(float(value))
    if t == "float":
        return float(value)
    return str(value)


class Settings:
    """Thread-safe runtime settings with a JSON overlay file."""

    def __init__(self, path: Path = SETTINGS_PATH):
        self._path = path
        self._lock = threading.Lock()
        self._values: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if k in SPEC:
                    try:
                        self._values[k] = _coerce(k, v)
                    except (ValueError, TypeError):
                        logger.warning("settings: bad value for %s: %r (using default)", k, v)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            logger.warning("settings: could not read %s: %s", self._path, e)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._values, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as e:
            logger.error("settings: could not write %s: %s", self._path, e)

    def get(self, key: str) -> Any:
        with self._lock:
            return self._values.get(key, SPEC[key]["default"])

    def set_many(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Validate + persist a batch. Returns {applied:{...}, restart_required:bool,
        errors:{key:msg}}."""
        applied: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        restart = False
        with self._lock:
            for k, v in updates.items():
                if k not in SPEC:
                    errors[k] = "unknown setting"
                    continue
                try:
                    cv = _coerce(k, v)
                except (ValueError, TypeError):
                    errors[k] = f"expected {SPEC[k]['type']}"
                    continue
                self._values[k] = cv
                applied[k] = cv
                if SPEC[k]["restart"]:
                    restart = True
            if applied:
                self._save()
        return {"applied": applied, "restart_required": restart, "errors": errors}

    def as_admin_payload(self) -> Dict[str, Any]:
        """Everything the admin page needs to render the form."""
        with self._lock:
            values = {k: self._values.get(k, s["default"]) for k, s in SPEC.items()}
        items: List[Dict[str, Any]] = []
        for k, s in SPEC.items():
            items.append({"key": k, "value": values[k], **{f: s[f] for f in
                          ("type", "group", "label", "help", "restart", "default")}})
        return {"values": values, "spec": items}

    def client_values(self) -> Dict[str, Any]:
        """The subset the kiosk frontend polls (all non-restart keys + a few more)."""
        with self._lock:
            return {k: self._values.get(k, s["default"]) for k, s in SPEC.items()}

    def apply_to_config(self, config):
        """Overlay restart-class settings onto the frozen config dataclasses.
        Called once in main.py before receivers are constructed."""
        g = self.get
        rng = dataclasses.replace(config.range, radius_miles=g("air_radius_miles"))
        recv = dataclasses.replace(
            config.receiver,
            opensky_poll_day_seconds=g("opensky_poll_day_seconds"),
            opensky_poll_night_seconds=g("opensky_poll_night_seconds"),
            opensky_active_start_hour=g("opensky_active_start_hour"),
            opensky_active_end_hour=g("opensky_active_end_hour"),
        )
        marine = dataclasses.replace(config.marine, radius_miles=g("sea_radius_miles"))
        return dataclasses.replace(config, range=rng, receiver=recv, marine=marine)


# Module-level singleton — import `settings` everywhere.
settings = Settings()
