"""EtherDex — the invisible radio neighborhood.

Two listeners:
  1. rtl_433 on the repurposed AIS dongle (the R820T that never had line of
     sight to the water — SeaDex rides AISStream anyway). Decodes the open
     433/315/915 MHz world: weather stations, tire-pressure sensors on passing
     cars, doorbells, remote thermometers.
       sudo apt install rtl-433
     Antenna tip: collapse the telescopic whip to ~16.5 cm (433 MHz quarter-wave).
  2. Bluetooth scan on the Pi's built-in radio (zero hardware): headphones,
     watches, car infotainment rolling past the house.

Privacy rule, enforced here: we log DEVICES, never people — model + broadcast
ID + signal metadata only, and anything unseen for 90 days is pruned by the
nightly maintenance job.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SESSION_GAP = 900   # 15 min gone = the next hearing is a new "sighting"

# Live tuner: the same dongle, demodulated to actual AUDIO via rtl_fm and played
# out the Pi's speakers. While one of these is on, the rtl_433 sensor hop pauses
# (one dongle, one job); it resumes automatically on stop or after the timeout.
LISTEN_TIMEOUT = 900          # auto-return to sensor-hopping after 15 min
LISTEN_PRESETS = {
    "wx":     {"freq": "162.55M", "mode": "fm", "sq": 0,
               "label": "NOAA Weather Radio",
               "blurb": "The robot voice reading the Sound's forecast, straight off the air"},
    "marine": {"freq": "156.80M", "mode": "fm", "sq": 40,
               "label": "Marine Ch 16",
               "blurb": "Boats hailing on Long Island Sound (quiet until someone keys up)"},
    "ham2m":  {"freq": "146.52M", "mode": "fm", "sq": 40,
               "label": "2m Ham Calling",
               "blurb": "The national simplex calling channel — hams saying hello directly"},
    "tower":  {"freq": "120.90M", "mode": "am", "sq": 35,
               "label": "KBDR Tower (off-air)",
               "blurb": "Bridgeport tower on YOUR antenna — no internet involved"},
    # The real thing. Only audible during a pass (check AtmoDex), and only when
    # ARISS is transmitting (crew contacts, SSTV events) — but when it works,
    # that's the Space Station, received on your own antenna, no internet involved.
    "iss":    {"freq": "145.80M", "mode": "fm", "sq": 0,
               "label": "ISS 145.800",
               "blurb": "The actual Space Station downlink — tune during a pass"},
    # --- the chatty ones ---
    "pilots": {"freq": "123.45M", "mode": "am", "sq": 35,
               "label": "Pilot Chat 123.45",
               "blurb": "The unofficial air-to-air channel — jets overhead gossiping, "
                        "swapping ride reports. Best when the sky is busy."},
    "bridge": {"freq": "156.65M", "mode": "fm", "sq": 40,
               "label": "Marine Ch 13",
               "blurb": "Bridge-to-bridge — tug and barge captains talking each other "
                        "through the channel. Workboat radio at its chattiest."},
    "rail":   {"freq": "160.92M", "mode": "fm", "sq": 40,
               "label": "Railroad 160.92",
               "blurb": "The railroad band — crews, dispatchers, and robot defect "
                        "detectors. If quiet, the line's channel may sit nearby (160-161)."},
    # --- the odd ones ---
    "guard":  {"freq": "121.50M", "mode": "am", "sq": 35,
               "label": "Guard 121.5",
               "blurb": "The aviation EMERGENCY channel. Usually dead silent — "
                        "occasionally pilots meow on it. (Really. It's a whole thing.)"},
    "aprs":   {"freq": "144.39M", "mode": "fm", "sq": 0,
               "label": "APRS 144.39",
               "blurb": "Ham GPS beacons — sounds like robot ducks arguing. Every "
                        "burst is a real station announcing where it is."},
}


def classify_rf(model: str, data: Dict[str, Any]) -> str:
    """rtl_433's decoder table IS the identification database: the `model` field
    it emits (e.g. 'Neptune-R900') names the protocol it decoded. Our job here is
    just mapping those model families onto kid-world kinds."""
    m = (model or "").lower()
    keys = {k.lower() for k in data}
    if "tpms" in m or "pressure_kpa" in keys or "pressure_psi" in keys or (data.get("type") or "").lower() == "tpms":
        return "tpms"
    # Utility meters (water/gas/electric AMR endpoints, mostly ~900 MHz) — every
    # house has a few, all quietly shouting their readings into the ether. Also
    # covers plug-in home energy monitors, which are the same idea from inside.
    if (any(s in m for s in ("r900", "ert-", "scmplus", "netidm", "badger", "sensus",
                             "neptune", "currentcost", "efergy", "emporia", "owl-"))
            or "consumption" in keys or "consumption_data" in keys):
        return "meter"
    # BBQ/meat thermometers — check before the generic temperature rule below,
    # or the neighbor's brisket gets filed as a weather station.
    if any(s in m for s in ("maverick", "meater", "bbq", "grill", "tp08", "tp12", "tp20")):
        return "bbq"
    if any(s in m for s in ("secplus", "garage")):
        return "garage"
    if any(s in m for s in ("oil-", "watchman")):
        return "oil"
    if any(s in m for s in ("security", "2gig", "interlogix", "visonic", "powercode")):
        return "security"
    # Both of these carry temperature too, so they must outrank the weather rule.
    if "pool" in m:
        return "pool"
    if "strike_count" in keys or any(s in m for s in ("6045", "lightning")):
        return "lightning"
    if any(k in data for k in ("temperature_C", "temperature_F", "humidity")):
        return "weather"
    if any(s in m for s in ("doorbell", "bell", "chime")):
        return "doorbell"
    if any(s in m for s in ("smoke", "co-", "alarm")):
        return "alarm"
    if any(s in m for s in ("remote", "keyfob", "button", "switch")):
        return "remote"
    return "mystery"


def classify_bt(name: str) -> str:
    """Kid-world classification from a Bluetooth device's advertised name."""
    n = (name or "").lower()
    if any(s in n for s in ("bud", "pod", "headphone", "headset", "wh-", "wf-", "jbl",
                            "bose", "beats", "soundcore", "earfun", "jabra")):
        return "headphones"
    if any(s in n for s in ("watch", "band", "versa", "sense", "garmin", "amazfit",
                            "fitbit", "charge ")):
        return "watch"
    if any(s in n for s in ("shield", "tv", "roku", "fire", "chromecast", "bravia",
                            "vizio", "hisense", "tcl")):
        return "tv"
    if any(s in n for s in ("speaker", "sonos", "echo", "homepod", "boombox",
                            "soundbar", "flip", "charge", "wonderboom", "srs-")):
        return "speaker"
    if any(s in n for s in ("uconnect", "sync ", "carplay", "honda", "toyota",
                            "subaru", "ford", "chevy", "chevrolet", "mazda", "nissan",
                            "hyundai", "kia", "jeep", "audi", "bmw", "mercedes",
                            "tesla", "vw ", "volkswagen", "my car")):
        return "car"
    if any(s in n for s in ("iphone", "pixel", "galaxy", "phone", "oneplus", "moto")):
        return "phone"
    if any(s in n for s in ("fridge", "refrigerator", "washer", "dryer", "dishwasher",
                            "thinq", "oven", "range")):
        return "appliance"
    if any(s in n for s in ("printer", "deskjet", "envy", "epson", "brother")):
        return "printer"
    return "bt"


def classify_wifi(ssid: str) -> str:
    """Kid-world classification from a WiFi network's broadcast name. Like the
    Bluetooth rule: we read the name the network SHOUTS on purpose — we never
    touch traffic, clients, or people."""
    n = (ssid or "").lower()
    if not ssid.strip():
        return "wifi_hidden"
    if any(s in n for s in ("xfinity", "optimum", "spectrum", "attwifi", "cablewifi",
                            "boingo", "starbucks", "guest", "public", "_free", "airport")):
        return "wifi_public"
    if any(s in n for s in ("eero", "orbi", "deco", "velop", "amplifi", "nest wifi",
                            "google wifi", "googlewifi", "mesh")):
        return "wifi_mesh"
    if any(s in n for s in ("hp-", "hp_", "epson", "canon", "brother", "deskjet",
                            "envy", "officejet", "direct-")):
        return "wifi_printer"
    if any(s in n for s in ("ring", "wyze", "nest", "blink", "arlo", "camera", "cam-")):
        return "wifi_camera"
    if any(s in n for s in ("netgear", "linksys", "tp-link", "tplink", "asus", "dlink",
                            "d-link", "arris", "belkin", "netgear", "router")):
        return "wifi_router"
    return "wifi_home"


def rf_rarity(kind: str) -> str:
    return {"weather": "Common", "tpms": "Common", "remote": "Uncommon",
            "doorbell": "Uncommon", "alarm": "Rare", "mystery": "Epic",
            "meter": "Uncommon", "security": "Uncommon", "garage": "Rare",
            "oil": "Rare", "bbq": "Epic", "pool": "Epic", "lightning": "Rare",
            "bt": "Common", "headphones": "Common", "watch": "Common",
            "tv": "Common", "speaker": "Common", "phone": "Common",
            "car": "Uncommon", "appliance": "Uncommon", "printer": "Uncommon",
            "wifi_home": "Common", "wifi_router": "Common", "wifi_mesh": "Common",
            "wifi_public": "Common", "wifi_printer": "Uncommon",
            "wifi_camera": "Rare", "wifi_hidden": "Rare",
            }.get(kind, "Rare")


class EtherService:
    """Runs both listeners, keeps a live 'recently heard' dict, logs catches."""

    def __init__(self, db, device: str = "", freqs: str = "433.92M,315M",
                 bt_enabled: bool = True, audio_device: str = "", wifi_enabled: bool = True):
        self.db = db
        self.device = device.strip()        # rtl_433 -d selector ('' = first free)
        # Dedicated live-tuner dongle (e.g. ':0303'). With one set, listening
        # runs on its own stick and sensor hunting never pauses.
        self.audio_device = audio_device.strip()
        self.freqs = [f.strip() for f in freqs.split(",") if f.strip()]
        self.bt_enabled = bt_enabled
        self.wifi_enabled = wifi_enabled
        self._live: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self.rtl_ok = False
        self._listen: Optional[Dict[str, Any]] = None   # active live-tuner preset
        self._listen_proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._rtl_loop, daemon=True, name="ether-rtl").start()
        if self.bt_enabled:
            threading.Thread(target=self._bt_loop, daemon=True, name="ether-bt").start()
        if self.wifi_enabled:
            threading.Thread(target=self._wifi_loop, daemon=True, name="ether-wifi").start()
        logger.info("EtherDex started (rtl_433 freqs=%s, bt=%s, wifi=%s)",
                    self.freqs, self.bt_enabled, self.wifi_enabled)

    def stop(self) -> None:
        self._running = False

    # -- rtl_433 -----------------------------------------------------------------
    def _rtl_loop(self) -> None:
        import shutil
        if not shutil.which("rtl_433"):
            logger.warning("EtherDex: rtl_433 not installed (sudo apt install rtl-433)")
            return
        if not self.device:
            # No device pinned: rtl_433 would grab USB index 0 — which is very
            # likely the ADS-B dongle, killing dump1090. Wait for dump1090 to
            # claim its stick first, and nag until a serial is pinned.
            logger.warning(
                "EtherDex: no dongle pinned! Set /admin -> Ether -> device selector "
                "to ':<serial>' of the old AIS dongle (run 'rtl_test' to list serials). "
                "Waiting 60s so dump1090 can claim its dongle first...")
            time.sleep(60)
        while self._running:
            if self._listen and not self.audio_device:
                time.sleep(1)          # live tuner is sharing our dongle — wait
                continue
            # Command rebuilt each spawn so retune() (band chips on the
            # Airwaves view) takes effect by simply killing the old process.
            cmd = ["rtl_433", "-F", "json", "-M", "level"]
            for f in self.freqs:
                cmd += ["-f", f]
            if len(self.freqs) > 1:
                cmd += ["-H", "60"]        # hop between frequencies every 60s
            if self.device:
                cmd += ["-d", self.device]
            try:
                # stderr merged in: rtl_433 prints device-open errors there, and
                # hiding them is how "the ether is quiet" stays a mystery.
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                self._proc = proc
                noise = 0
                for line in proc.stdout:
                    if not self._running:
                        proc.kill()
                        return
                    line = line.strip()
                    if not line.startswith("{"):
                        # Startup banner / errors — surface the first few.
                        if line and noise < 8:
                            logger.info("rtl_433: %s", line)
                            noise += 1
                        if line and any(s in line.lower() for s in
                                        ("error", "usb", "no supported", "failed", "unable")):
                            self.last_error = line[:160]
                        continue
                    self.rtl_ok = True      # only true once real output flows
                    try:
                        self._heard_rf(json.loads(line))
                    except (ValueError, TypeError):
                        continue
                proc.wait()
                logger.warning("rtl_433 exited (code %s) — device busy or unplugged? "
                               "Pin the free dongle in /admin -> Ether (e.g. ':0162')",
                               proc.returncode)
            except Exception as e:
                logger.warning("rtl_433 failed to start: %s", e)
            if self.rtl_ok:
                self._fails = 0             # it worked before dying — quick retry
            else:
                self._fails = getattr(self, "_fails", 0) + 1
            self.rtl_ok = False
            # Escalating backoff: a missing dongle (e.g. waiting on the powered
            # hub) shouldn't spawn a doomed process every 15 seconds forever.
            time.sleep(min(15 * max(1, getattr(self, "_fails", 1)), 300))

    def _heard_rf(self, d: Dict[str, Any]) -> None:
        model = str(d.get("model") or "").strip()
        did = str(d.get("id") if d.get("id") is not None else "").strip()
        if not model:
            return
        key = f"rf:{model}#{did}"
        kind = classify_rf(model, d)
        meta = {}
        for src, dst in (("temperature_C", "temp_c"), ("humidity", "humidity"),
                         ("pressure_kPa", "pressure_kpa"), ("battery_ok", "battery"),
                         ("rssi", "rssi"), ("channel", "channel"),
                         ("consumption", "consumption"),
                         ("consumption_data", "consumption"),
                         ("wind_avg_km_h", "wind_kmh"), ("rain_mm", "rain_mm"),
                         ("strike_count", "strikes"), ("moisture", "moisture")):
            if d.get(src) is not None:
                meta[dst] = d[src]
        self._log(key, kind, model or "Unknown RF device", meta)

    # -- bluetooth ------------------------------------------------------------------
    # bluetoothctl emits property lines ([CHG] ... RSSI/ManufacturerData/...)
    # that must NEVER be mistaken for device names.
    _BT_GARBAGE = re.compile(
        r"^(ManufacturerData|ServiceData|RSSI|TxPower|UUIDs|AdvertisingFlags|"
        r"Name:|Alias:|Trusted|Paired|Bonded|Connected|LegacyPairing|Modalias|"
        r"Key:|Value:)", re.I)

    def _bt_loop(self) -> None:
        import shutil
        if not shutil.which("bluetoothctl"):
            logger.warning("EtherDex: bluetoothctl not available")
            return
        new_pat = re.compile(r"\[NEW\] Device ((?:[0-9A-F]{2}:){5}[0-9A-F]{2})\s+(.+)", re.I)
        dev_pat = re.compile(r"^Device ((?:[0-9A-F]{2}:){5}[0-9A-F]{2})\s+(.+)", re.I | re.M)
        rssi_pat = re.compile(r"Device ((?:[0-9A-F]{2}:){5}[0-9A-F]{2}) RSSI: .*\((-?\d+)\)", re.I)
        try:  # the controller is often soft-off on a fresh boot
            subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, timeout=10)
        except Exception:
            pass
        while self._running:
            try:
                scan = subprocess.run(["bluetoothctl", "--timeout", "20", "scan", "on"],
                                      capture_output=True, text=True, timeout=40).stdout or ""
                # Signal strength per device (for the "about 20 feet away" line).
                rssi = {}
                for mac, db_val in rssi_pat.findall(scan):
                    rssi[mac.upper()] = int(db_val)
                # Names: [NEW] lines from this sweep + the known-devices list.
                listing = subprocess.run(["bluetoothctl", "devices"],
                                         capture_output=True, text=True, timeout=10).stdout or ""
                seen = {}
                for mac, name in new_pat.findall(scan) + dev_pat.findall(listing):
                    seen.setdefault(mac.upper(), name.strip())
                for mac, name in seen.items():
                    if (not name or name.replace("-", ":").upper() == mac
                            or self._BT_GARBAGE.match(name)):
                        continue
                    kind = classify_bt(name)
                    meta = {"rssi_bt": rssi[mac]} if mac in rssi else {}
                    # Key by NAME, not MAC: gadgets rotate randomized MACs for
                    # privacy, which minted a dozen "SHIELD"s. One name = one entry.
                    key = f"btn:{name.lower().strip()[:40]}"
                    if mac in rssi or key not in self._live:
                        self._log(key, kind, name, meta)
            except Exception as e:
                logger.debug("bt scan failed: %s", e)
            time.sleep(300)                # one sweep every 5 min

    # -- wifi -------------------------------------------------------------------------
    # The Pi's own WiFi radio sees every ACCESS POINT broadcasting nearby — the
    # names houses shout on purpose. Privacy rule mirrors Bluetooth: we read
    # network NAMES + signal only, never clients, traffic, or people. Network
    # Manager scans in the background, so this never drops the Pi's connection.
    def _wifi_loop(self) -> None:
        import shutil
        if not shutil.which("nmcli"):
            logger.warning("EtherDex: nmcli not available — WiFi scan off")
            return
        while self._running:
            try:
                try:                          # nudge a fresh scan (harmless if rate-limited)
                    subprocess.run(["nmcli", "dev", "wifi", "rescan"],
                                   capture_output=True, timeout=20)
                    time.sleep(4)
                except Exception:
                    pass
                # -t = terse, -f = fields; SSID escapes ':' as '\:' in this mode.
                out = subprocess.run(
                    ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,CHAN", "dev", "wifi", "list"],
                    capture_output=True, text=True, timeout=25).stdout or ""
                best: Dict[str, Dict[str, Any]] = {}
                for line in out.splitlines():
                    parts = re.split(r"(?<!\\):", line)      # split on UN-escaped colons
                    if len(parts) < 4:
                        continue
                    ssid = parts[0].replace("\\:", ":").strip()
                    try:
                        signal = int(parts[1])
                    except ValueError:
                        signal = 0
                    security = parts[2].strip()
                    try:
                        chan = int(parts[3])
                    except ValueError:
                        chan = 0
                    name = ssid if ssid else "(hidden network)"
                    # One row per network name, strongest signal wins (dupes =
                    # the same AP on 2.4 + 5 GHz, or mesh nodes).
                    if name not in best or signal > best[name]["signal"]:
                        best[name] = {"ssid": ssid, "signal": signal,
                                      "security": security, "chan": chan}
                for name, w in best.items():
                    kind = classify_wifi(w["ssid"])
                    meta = {"signal_pct": w["signal"],
                            "band": "5 GHz" if w["chan"] > 15 else "2.4 GHz",
                            "locked": bool(w["security"] and w["security"] != "--")}
                    key = f"wifi:{name.lower().strip()[:40]}"
                    self._log(key, kind, name, meta)
            except Exception as e:
                logger.debug("wifi scan failed: %s", e)
            time.sleep(300)                # one sweep every 5 min

    # -- shared -----------------------------------------------------------------------
    def _log(self, key: str, kind: str, name: str, meta: Dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            prev = self._live.get(key)
            self._live[key] = {"key": key, "kind": kind, "name": name,
                               "meta": meta, "last": now,
                               "first": prev["first"] if prev else now}
            # Bound the live dict.
            if len(self._live) > 300:
                for k in sorted(self._live, key=lambda k: self._live[k]["last"])[:50]:
                    del self._live[k]
        try:
            if self.db:
                self.db.log_ether(key, kind, name, rf_rarity(kind),
                                  json.dumps(meta) if meta else None)
        except Exception as e:
            logger.debug("ether db log failed: %s", e)

    def retune(self, freqs: str) -> List[str]:
        """Swap the frequency hop list live — kills rtl_433; the loop respawns
        it with the new bands in a few seconds."""
        self.freqs = [f.strip() for f in (freqs or "").split(",") if f.strip()] or ["433.92M"]
        try:
            if getattr(self, "_proc", None):
                self._proc.kill()
        except Exception:
            pass
        logger.info("EtherDex retuned to %s", self.freqs)
        return self.freqs

    # -- live tuner (rtl_fm -> speakers) -------------------------------------------
    def listen_live(self, preset_id: str, seconds: Optional[int] = None) -> Dict[str, Any]:
        """Point a dongle at a voice frequency and play the audio on the Pi.
        With a dedicated audio dongle, sensor logging keeps running; otherwise
        it pauses and resumes on stop or after the timeout."""
        p = LISTEN_PRESETS.get(preset_id)
        if not p:
            return {"error": "unknown preset"}
        self.listen_stop()
        self._listen = dict(p, id=preset_id,
                            until=time.time() + (seconds or LISTEN_TIMEOUT))
        if not self.audio_device:
            try:
                if getattr(self, "_proc", None):
                    self._proc.kill()       # free the shared dongle for rtl_fm
            except Exception:
                pass
        threading.Thread(target=self._listen_loop, daemon=True,
                         name="ether-listen").start()
        return {"listening": self.listening()}

    def listen_stop(self) -> Dict[str, Any]:
        self._listen = None                 # rtl loop resumes within ~1s
        self._stop_listen_proc()
        return {"listening": None}

    def listening(self) -> Optional[Dict[str, Any]]:
        li = self._listen
        if not li:
            return None
        return {"id": li["id"], "label": li["label"], "freq": li["freq"],
                "seconds_left": max(0, int(li["until"] - time.time())),
                "dedicated": bool(self.audio_device)}

    def _listen_loop(self) -> None:
        li = self._listen
        if not li:
            return
        time.sleep(1.0)                     # let a killed rtl_433 release USB
        dev_sel = self.audio_device or self.device
        dev = f" -d {dev_sel}" if dev_sel else ""
        sq = f" -l {li['sq']}" if li.get("sq") else ""
        # Shell pipeline on purpose: rtl_fm demodulates, aplay plays. Killed as a
        # process group so neither half lingers holding the dongle or the sink.
        cmd = (f"rtl_fm{dev} -f {li['freq']} -M {li['mode']} -s 24k -g 40{sq} - | "
               f"aplay -q -t raw -r 24000 -f S16_LE -c 1")
        try:
            self._listen_proc = subprocess.Popen(
                cmd, shell=True, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.warning("live tuner failed to start: %s", e)
            self._listen = None
            return
        logger.info("Live tuner on %s (%s)", li["freq"], li["label"])
        while (self._running and self._listen is li
               and time.time() < li["until"]
               and self._listen_proc and self._listen_proc.poll() is None):
            time.sleep(1)
        self._stop_listen_proc()
        if self._listen is li:              # timeout/pipeline death, not listen_stop
            self._listen = None
        logger.info("Live tuner off (%s) — sensor hop resuming", li["label"])

    def _stop_listen_proc(self) -> None:
        proc, self._listen_proc = self._listen_proc, None
        if not proc:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def recent(self, minutes: float = 20) -> List[Dict[str, Any]]:
        cutoff = time.time() - minutes * 60
        with self._lock:
            out = [dict(v) for v in self._live.values() if v["last"] >= cutoff]
        out.sort(key=lambda x: -x["last"])
        return out

    def status(self) -> Dict[str, Any]:
        import shutil
        return {"rtl_running": self.rtl_ok, "bt_enabled": self.bt_enabled,
                "live_count": len(self._live), "freqs": self.freqs,
                "rtl_installed": bool(shutil.which("rtl_433")),
                "device": self.device or "(none pinned!)",
                "audio_device": self.audio_device,
                "last_error": getattr(self, "last_error", ""),
                "listening": self.listening()}


class IssAutoListener:
    """When a decent ISS pass begins, tune the audio dongle to 145.800
    automatically — the kiosk listens to space by itself. Requires a dedicated
    audio dongle (never steals the sensor stick) and steps aside if someone is
    already using the live tuner. One trigger per pass."""

    MIN_ELEVATION = 25    # degrees — below this the pass is mostly rooftops

    def __init__(self, ether, passes_provider, enabled, announcer=None):
        self.ether = ether
        self.passes = passes_provider      # callable -> [{start, end, max_elevation}]
        self.enabled = enabled             # callable -> bool (read live, no restart)
        self.announcer = announcer
        self._done: set = set()            # pass start stamps already handled
        threading.Thread(target=self._loop, daemon=True, name="iss-listen").start()

    def _loop(self) -> None:
        time.sleep(90)                     # let TLEs load and the tuner settle
        while True:
            try:
                self._tick()
            except Exception as e:
                logger.debug("iss auto-listen tick failed: %s", e)
            time.sleep(60)

    def _tick(self) -> None:
        if not (self.enabled() and self.ether and self.ether.audio_device):
            return
        if self.ether._listen is not None:
            return                         # tuner busy — a human picked something
        now = time.time()
        for p in (self.passes() or []):
            start, end = p.get("start"), p.get("end")
            if not start or not end or start in self._done:
                continue
            if (p.get("max_elevation") or 0) < self.MIN_ELEVATION:
                continue
            if start <= now < end:
                self._done.add(start)
                if len(self._done) > 50:
                    self._done = set(sorted(self._done)[-20:])
                self.ether.listen_live("iss", seconds=int(end - now) + 30)
                logger.info("ISS overhead (max el %s) — auto-tuned 145.800",
                            p.get("max_elevation"))
                if self.announcer:
                    self.announcer.say(
                        "The Space Station is overhead. Listening on one four five point eight.",
                        category="iss", dedup_key=f"issl{int(start)}")
                break


# ===========================================================================
# HAM it Up — callsign lookups via hamdb.org (RapidAPI)
# ===========================================================================
class HamdbClient:
    def __init__(self, rapidapi_key: str, home_lat: float = 41.1635, home_lon: float = -73.1262):
        self.key = rapidapi_key
        self.home = (home_lat, home_lon)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def lookup(self, call: str) -> Dict[str, Any]:
        import urllib.request
        call = (call or "").strip().upper()[:12]
        if not call or not call.isalnum():
            return {"error": "bad callsign"}
        if call in self._cache:
            return self._cache[call]
        try:
            url = f"https://hamdb-org.p.rapidapi.com/{call}/json/rapidapi"
            req = urllib.request.Request(url, headers={
                "x-rapidapi-host": "hamdb-org.p.rapidapi.com",
                "x-rapidapi-key": self.key, "User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
            cs = ((data.get("hamdb") or {}).get("callsign") or {})
            status = ((data.get("hamdb") or {}).get("messages") or {}).get("status", "")
            if not cs.get("call") or cs.get("call") == "NOT_FOUND" or "NOT_FOUND" in str(status):
                out = {"call": call, "not_found": True}
            else:
                out = {"call": cs.get("call"), "name": " ".join(
                           x for x in (cs.get("fname"), cs.get("name")) if x and x != "NOT_FOUND"),
                       "class": cs.get("class"), "grid": cs.get("grid"),
                       "city": cs.get("addr2"), "state": cs.get("state"),
                       "country": cs.get("country"), "expires": cs.get("expires")}
                try:
                    lat, lon = float(cs.get("lat")), float(cs.get("lon"))
                    out["lat"], out["lon"] = lat, lon
                    from receiver import _haversine
                    out["miles_away"] = round(_haversine(self.home[0], self.home[1], lat, lon))
                except (TypeError, ValueError):
                    pass
            self._cache[call] = out
            return out
        except Exception as e:
            logger.debug("hamdb lookup failed: %s", e)
            return {"call": call, "error": "lookup failed"}


# ===========================================================================
# World Radio fallback — RapidAPI station sources, used only if the free
# Radio-Browser API is down (protects the 300/month + 25/day quotas)
# ===========================================================================
class RadioFallbackClient:
    def __init__(self, rapidapi_key: str):
        self.key = rapidapi_key
        self._cache: List[Dict[str, Any]] = []
        self._cache_at = 0.0

    def _get(self, host: str, path: str):
        import urllib.request
        req = urllib.request.Request(f"https://{host}{path}", headers={
            "x-rapidapi-host": host, "x-rapidapi-key": self.key,
            "User-Agent": "SkyDex/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)

    def random_stations(self) -> List[Dict[str, Any]]:
        """A page of stations from the keyed providers, heavily cached (6h)
        so a broken Radio-Browser day costs at most ~4 quota calls."""
        if self._cache and time.time() - self._cache_at < 21600:
            return self._cache
        for host, path in (
            ("radio-world-75-000-worldwide-fm-radio-stations.p.rapidapi.com",
             "/get_quotes.php?limit=20&page=1"),                       # 25/day
            ("50k-radio-stations.p.rapidapi.com", "/radios/random?limit=20"),  # 300/mo
        ):
            try:
                data = self._get(host, path)
                rows = data if isinstance(data, list) else \
                    next((v for v in data.values() if isinstance(v, list)), [])
                out = []
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    url = r.get("url") or r.get("stream_url") or r.get("radio_url")
                    name = r.get("name") or r.get("radio_name") or r.get("title")
                    if url and name:
                        out.append({"name": name, "url_resolved": url,
                                    "country": r.get("country") or r.get("radio_country") or "",
                                    "tags": r.get("genre") or "", "fallback": True})
                if out:
                    self._cache, self._cache_at = out, time.time()
                    return out
            except Exception as e:
                logger.debug("radio fallback %s failed: %s", host, e)
        return self._cache
