#!/usr/bin/env python3
"""SkyDex — entry point.

Starts three things:
  1. ADS-B receiver (background thread, reads dump1090/OpenSky)
  2. Enrichment + logging pipeline (background, every 2s)
  3. FastAPI web server (serves the kiosk UI and API)

Run:
    cd /home/skywatch/skydex
    python3 main.py

Then point a browser at http://localhost:8000
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

# Ensure local imports work
sys.path.insert(0, str(Path(__file__).parent))

from config import SkyDexConfig
from database import Database
from settings import settings
from voice import announcer, IssVoiceWatcher
from receiver import ADSBReceiver, _haversine
from ais_receiver import AISReceiver
from enrichment import AdsbdbClient, LocalDbClient, WeatherClient, AerodataboxClient, PlanespottersClient, JetApiClient
from classifier import Classifier, contrail_likely, rarity_for
from vessels import ship_category, vessel_rarity, is_anchored
from facts import get_type_fact
from api import app, set_globals

logger = logging.getLogger("skydex")


# ── Background enrichment pipeline ─────────────────────────────────────────

class EnrichmentPipeline:
    """Runs in a background thread. Every 2 seconds:
    1. Fetches contacts in range from receiver
    2. Logs each detection to SQLite
    3. Enriches airframe data from adsbdb.com
    4. Classifies aircraft type
    5. Awards badges (only on new detections, not every ping)
    
    A detection is only counted if >15 minutes elapsed since the last
    detection for that same aircraft. This prevents a single flyover from
    generating hundreds of "detections" (it was one visit).
    """

    def __init__(
        self,
        db: Database,
        receiver: ADSBReceiver,
        config: SkyDexConfig,
    ):
        self.db = db
        self.receiver = receiver
        self.config = config
        self.adsbdb = AdsbdbClient()
        self.localdb = LocalDbClient(config.faa_db_path, config.opensky_db_path)
        self.aerodatabox = AerodataboxClient()
        self.planespotters = PlanespottersClient()
        self.jetapi = JetApiClient()
        self.classifier = Classifier()
        self._photo_thread: threading.Thread | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        # Active sightings (sessions): hex -> {"id": sighting_id, "last_seen": ts}
        self._sessions: dict[str, dict] = {}
        # Track last time we logged a telemetry row per aircraft (hex -> timestamp)
        self._last_log_time: dict[str, float] = {}
        # Track current emergency squawk per aircraft so we log each event once
        self._emergency_state: dict[str, str] = {}

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Separate thread so slow photo API calls never stall live tracking.
        self._photo_thread = threading.Thread(target=self._photo_loop, daemon=True)
        self._photo_thread.start()
        logger.info("Enrichment pipeline started")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.warning("Pipeline tick error: %s", e, exc_info=True)
            time.sleep(2.0)

    def _photo_loop(self) -> None:
        """Background: fetch a real photo for one logged airframe at a time."""
        while self._running:
            try:
                self._backfill_one_photo()
            except Exception as e:
                logger.debug("Photo backfill error: %s", e)
            time.sleep(self.config.game.photo_backfill_interval_seconds)

    def _backfill_one_photo(self) -> None:
        cands = self.db.get_airframes_needing_photo(1)
        if not cands:
            return
        cand = cands[0]
        hex_code = cand["hex"]
        # Free Planespotters first (broad coverage, no credits), then adsbdb,
        # then paid AeroDataBox for whatever's left.
        reg = cand.get("registration") or ""
        info = self.planespotters.lookup_photo_info(hex_code, reg)
        photo = info.get("url") if info else None
        credit = info.get("photographer") if info else None
        if not photo and reg:
            # JetPhotos via jetapi (by registration) — huge library, fills gaps.
            j = self.jetapi.lookup_photo_info(reg)
            if j and j.get("url"):
                photo = j["url"]
                credit = j.get("photographer")
        if not photo:
            photo = (self.adsbdb.lookup_hex(hex_code) or {}).get("photo_url")
        if not photo:
            photo = self.aerodatabox.lookup_aircraft_photo(hex_code, reg)
        # Mark checked either way so we don't keep spending credits on it.
        if photo:
            self.db.update_airframe(hex_code, photo_url=photo, photo_checked=1, photo_credit=credit or None)
            logger.info("Backfilled photo for %s", hex_code)
        else:
            self.db.update_airframe(hex_code, photo_checked=1)

    def _tick(self) -> None:
        contacts = self.receiver.get_visible_contacts(
            self.config.range.radius_miles,
            self.config.range.visibility_miles_per_1000ft,
            self.config.range.max_visible_radius_miles,
        )
        now = time.time()

        for ac in contacts:
            hex_code = ac["hex"]

            # 1. Ensure airframe exists (get or create with dex number)
            airframe = self.db.get_or_create_airframe(hex_code)

            # 2. Enrich airframe metadata if missing. Local DBs (FAA / OpenSky)
            #    are tried first — fast, offline, no rate limits — then the
            #    adsbdb API as a fallback.
            if not airframe.get("model"):
                enriched = self.localdb.lookup_hex(hex_code) or self.adsbdb.lookup_hex(hex_code)
                if enriched:
                    self.db.update_airframe(hex_code, **enriched)
                    airframe.update(enriched)

            # Rarity (type-based) — set once we know the type code
            if airframe.get("type_code"):
                rarity = rarity_for(airframe)
                if rarity != airframe.get("rarity"):
                    self.db.update_airframe(hex_code, rarity=rarity)
                    airframe["rarity"] = rarity

            # Behavioral type — classify with full context (incl. callsign) and
            # store the primary so the Planedex can filter/sort by it.
            classes = self.classifier.classify({**airframe, **ac})
            primary = classes[0]["type"] if classes else "Aircraft"
            if primary != airframe.get("primary_type"):
                self.db.update_airframe(hex_code, primary_type=primary)
                airframe["primary_type"] = primary

            # Persist the military flag so the "Military" badge filter works and
            # the client can override the display type for tankers/transports.
            is_mil = 1 if any(c["type"] == "Sentinel" for c in classes) else 0
            if is_mil != airframe.get("is_military"):
                self.db.update_airframe(hex_code, is_military=is_mil)
                airframe["is_military"] = is_mil

            # Emergency squawk detection (7500 hijack / 7600 radio / 7700 general).
            sq = (ac.get("squawk") or "").strip()
            if sq in ("7500", "7600", "7700"):
                if self._emergency_state.get(hex_code) != sq:
                    self._emergency_state[hex_code] = sq
                    self.db.log_emergency(hex_code, sq, ac.get("callsign"))
                    self.db.update_airframe(hex_code, emergency_seen=now)
                    logger.warning("EMERGENCY squawk %s from %s (%s)", sq, hex_code, ac.get("callsign") or "")
                    kind = {"7500": "hijack code", "7600": "radio failure",
                            "7700": "general emergency"}[sq]
                    d = ac.get("distance_miles")
                    announcer.say(
                        f"Emergency. Squawk {' '.join(sq)} — {kind}"
                        f"{f', {round(d)} miles out' if d else ''}.",
                        "air", dedup_key=f"emg-{hex_code}", dedup_seconds=1800)
            elif hex_code in self._emergency_state:
                del self._emergency_state[hex_code]

            # 3. Route lookup (per-flight, keyed on callsign — not stored on the
            #    airframe, which has no route columns; it goes on the detection).
            route = {}
            if ac.get("callsign"):
                route = self.adsbdb.lookup_callsign(ac["callsign"])

            # 4. Log telemetry — at most once per telemetry_interval per aircraft
            #    (feeds the altitude chart + pattern stats; throttled so a single
            #    lingering flyover doesn't write hundreds of rows).
            last_log = self._last_log_time.get(hex_code, 0)
            if (now - last_log) >= self.config.game.telemetry_interval_seconds:
                self._last_log_time[hex_code] = now
                self.db.log_detection(
                    hex_code=hex_code,
                    lat=ac.get("lat"),
                    lon=ac.get("lon"),
                    altitude=ac.get("altitude"),
                    ground_speed=ac.get("ground_speed"),
                    track=ac.get("track"),
                    callsign=ac.get("callsign"),
                    origin_airport=route.get("origin_icao") or route.get("origin_airport"),
                    dest_airport=route.get("dest_icao") or route.get("dest_airport"),
                    distance_miles=ac.get("distance_miles"),
                    contrail_likely=1 if contrail_likely(ac.get("altitude")) else 0,
                )

            # 5. Sighting (session) tracking — CAPTURE only inside the base
            #    radius (the pokeball). High jets are *visible* from 20+ miles
            #    (altitude-scaled range) and stay on the Live view with full
            #    info, but they only join the Planedex if they actually enter
            #    the pokeball. The ball only closes up close.
            if (ac.get("distance_miles") or 1e9) > self.config.range.radius_miles:
                continue

            origin = route.get("origin_icao") or route.get("origin_airport")
            dest = route.get("dest_icao") or route.get("dest_airport")
            callsign = ac.get("callsign") or None

            gap = self.config.game.session_gap_seconds
            sess = self._sessions.get(hex_code)

            # If we have no in-memory session (e.g. just after a restart), try to
            # resume a sighting that's still "open" in the DB so we don't double-log.
            if sess is None:
                last = self.db.get_last_sighting(hex_code)
                if last and last.get("ended_at") is not None and (now - last["ended_at"]) <= gap:
                    sess = {"id": last["id"], "last_seen": last["ended_at"]}
                    self._sessions[hex_code] = sess

            if sess is not None and (now - sess["last_seen"]) <= gap:
                # Continue the current sighting (extend it, fill route once known)
                sess["last_seen"] = now
                self.db.update_sighting(sess["id"], now, callsign, origin, dest)
            else:
                # Brand-new sighting
                sighting_id = self.db.start_sighting(hex_code, now, callsign, origin, dest)
                self._sessions[hex_code] = {"id": sighting_id, "last_seen": now}
                new_count = self.db.increment_detection_count(hex_code)

                tier = "Spotted"
                for name, threshold in reversed(self.config.game.evolution_tiers):
                    if new_count >= threshold:
                        tier = name
                        break
                self.db.update_airframe(hex_code, evolution_tier=tier)
                self._check_badges(new_count, hex_code, airframe)

                # Voice: rare metal overhead gets a call-out.
                rar = airframe.get("rarity") or ""
                if rar in ("Epic", "Legendary"):
                    what = airframe.get("model") or airframe.get("type_code") or "aircraft"
                    who = airframe.get("operator") or ""
                    announcer.say(
                        f"{'Legendary' if rar == 'Legendary' else 'Rare'} catch: "
                        f"{what}{', ' + who if who else ''} now in range.",
                        "air", dedup_key=f"rare-{hex_code}", dedup_seconds=3600)
                elif airframe.get("is_military"):
                    announcer.say(
                        f"Military contact: {airframe.get('model') or 'unidentified type'} in range.",
                        "air", dedup_key=f"mil-{hex_code}", dedup_seconds=3600)

        # Drop sessions for aircraft gone longer than the gap (so their next
        # appearance starts a fresh sighting) — also bounds memory.
        gap = self.config.game.session_gap_seconds
        for h in [h for h, s in self._sessions.items() if now - s["last_seen"] > gap]:
            del self._sessions[h]

        # Save weather periodically
        if int(now) % 300 == 0:  # Every 5 minutes
            self._fetch_weather()

    def _check_badges(self, count: int, hex_code: str, airframe: dict) -> None:
        """Award badges based on milestones."""
        # First detection badge
        self.db.award_badge("first_contact", "Logged your first aircraft contact")

        # Count milestones
        if count == 10:
            self.db.award_badge("ten_spotted", "Logged 10 aircraft contacts")
        elif count == 50:
            self.db.award_badge("fifty_spotted", "Logged 50 aircraft contacts")
        elif count == 100:
            self.db.award_badge("century", "Logged 100 aircraft contacts")

        # Type badges
        if airframe.get("model"):
            model = airframe["model"].upper()
            if "HELICOPTER" in model or any(h in model for h in ["R44", "R66", "EC135", "H135"]):
                self.db.award_badge("first_rotor", "Spotted your first helicopter")

    def _fetch_weather(self) -> None:
        try:
            weather = WeatherClient(self.config.location.lat, self.config.location.lon)
            data = weather.fetch()
            if data:
                self.db.save_weather(
                    temp_f=data.get("temp_f"),
                    wind_speed=data.get("wind_speed"),
                    wind_dir_deg=None,  # Would need parsing
                    condition=data.get("condition"),
                    source=data.get("source", "api"),
                )
        except Exception as e:
            logger.debug("Weather fetch failed: %s", e)


# ── SeaDex marine pipeline ─────────────────────────────────────────────────

# How far a vessel must move from its last position to count as having "moved"
# (anchor swing + GPS jitter live well under this).
ANCHOR_MOVE_MILES = 0.1


class MarinePipeline:
    """Background thread that logs AIS vessels into the SeaDex collection —
    a sea-side mirror of EnrichmentPipeline, kept entirely separate."""

    def __init__(self, db: Database, ais, config: SkyDexConfig):
        self.db = db
        self.ais = ais
        self.config = config
        self._running = False
        self._thread: threading.Thread | None = None
        self._sessions: dict[str, dict] = {}

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Marine pipeline started")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.warning("Marine pipeline tick error: %s", e, exc_info=True)
            time.sleep(3.0)

    def _tick(self) -> None:
        vessels = self.ais.get_vessels_in_range(self.config.marine.radius_miles)
        now = time.time()
        gap = self.config.game.session_gap_seconds

        for v in vessels:
            mmsi = v["mmsi"]
            vessel = self.db.get_or_create_vessel(mmsi)

            updates = {}
            for src, col in (("name", "name"), ("callsign", "callsign"),
                             ("ship_type", "ship_type"), ("destination", "destination"),
                             ("country", "flag"), ("imo", "imo")):
                val = v.get(src)
                if val not in (None, "") and val != vessel.get(col):
                    updates[col] = val
            if v.get("length") and not vessel.get("length"):
                updates["length"] = v["length"]
            # Classify from the BEST info we have — live values, else what's
            # already stored. AIS ship-type/length arrive in separate, less
            # frequent messages than position, so computing from live-only data
            # would clobber a known "Tug"/"Superyacht" back to "Other" on the
            # next position-only tick.
            eff_type = v.get("ship_type") if v.get("ship_type") is not None else vessel.get("ship_type")
            eff_len = v.get("length") or vessel.get("length")
            if eff_type is not None:
                cat = ship_category(eff_type, eff_len)
                if cat != vessel.get("category"):
                    updates["category"] = cat
                rarity = vessel_rarity(eff_type, eff_len)
                if rarity != vessel.get("rarity"):
                    updates["rarity"] = rarity
            ns = v.get("nav_status")
            if ns is not None and ns != vessel.get("nav_status"):
                updates["nav_status"] = ns
            dist = v.get("distance_miles")
            if dist is not None and (vessel.get("min_distance") is None or dist < vessel["min_distance"]):
                updates["min_distance"] = dist

            # Anchored handling: has it moved since we last saw it?
            lat, lon = v.get("lat"), v.get("lon")
            anchored = is_anchored(v.get("nav_status"), v.get("speed"))
            moved = (
                vessel.get("last_lat") is not None and vessel.get("last_lon") is not None
                and lat is not None and lon is not None
                and _haversine(vessel["last_lat"], vessel["last_lon"], lat, lon) > ANCHOR_MOVE_MILES
            )
            if lat is not None and lon is not None:
                updates["last_lat"] = lat
                updates["last_lon"] = lon
            # IMO usually arrives after the first position report — re-arm the
            # photo lookup so the (IMO-based) Commons search runs next time.
            if "imo" in updates and not vessel.get("photo_url"):
                updates["photo_checked"] = 0
            if updates:
                self.db.update_vessel(mmsi, **updates)
                vessel.update(updates)

            # A vessel sitting at anchor in the same spot is ONE sighting — even if
            # its AIS drops out for a while — until it actually moves.
            anchored_hold = anchored and not moved

            dest = v.get("destination")
            sess = self._sessions.get(mmsi)
            if sess is None:
                last = self.db.get_last_vessel_sighting(mmsi)
                if last and last.get("ended_at") is not None and \
                        ((now - last["ended_at"]) <= gap or anchored_hold):
                    sess = {"id": last["id"], "last_seen": last["ended_at"]}
                    self._sessions[mmsi] = sess

            if sess is not None and ((now - sess["last_seen"]) <= gap or anchored_hold):
                sess["last_seen"] = now
                self.db.update_vessel_sighting(sess["id"], now, dest)
            else:
                sid = self.db.start_vessel_sighting(mmsi, now, dest)
                self._sessions[mmsi] = {"id": sid, "last_seen": now}
                self.db.increment_vessel_count(mmsi)
                # Voice: superyachts and rare vessels get called out.
                vname = (vessel.get("name") or "").strip().title() if isinstance(vessel, dict) else ""
                vcat = vessel.get("category") if isinstance(vessel, dict) else None
                vrar = (vessel.get("rarity") or "") if isinstance(vessel, dict) else ""
                if vcat == "Superyacht":
                    announcer.say(f"A superyacht is in the Sound{': ' + vname if vname else ''}.",
                                  "sea", dedup_key=f"sy-{mmsi}", dedup_seconds=3600)
                elif vrar in ("Epic", "Legendary"):
                    announcer.say(f"Rare vessel: {vname or 'unknown contact'}, "
                                  f"{(vcat or 'ship').lower()}, now in range.",
                                  "sea", dedup_key=f"rv-{mmsi}", dedup_seconds=3600)

        for m in [m for m, s in self._sessions.items() if now - s["last_seen"] > gap]:
            del self._sessions[m]


# ── Main ──────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/tmp/skydex.log"),
        ],
    )


def main() -> None:
    config = SkyDexConfig()
    setup_logging(config.log_level)

    # Overlay runtime-tunable values from ~/.skydex/settings.json (admin page).
    config = settings.apply_to_config(config)

    logger.info("=" * 50)
    logger.info("SkyDex starting")
    logger.info("Location: %s (%.4f, %.4f)", config.location.name, config.location.lat, config.location.lon)
    logger.info("Range: %.1f miles", config.range.radius_miles)
    logger.info("=" * 50)

    # Database
    db = Database(config.db_path)

    # Receiver
    receiver = ADSBReceiver(
        home_lat=config.location.lat,
        home_lon=config.location.lon,
        dump1090_url=config.receiver.dump1090_url,
        poll_interval=config.receiver.poll_interval_seconds,
        enable_opensky_fallback=config.receiver.fallback_opensky,
        opensky_client_id=config.receiver.opensky_client_id,
        opensky_client_secret=config.receiver.opensky_client_secret,
        opensky_poll_day=config.receiver.opensky_poll_day_seconds,
        opensky_poll_night=config.receiver.opensky_poll_night_seconds,
        opensky_active_start=config.receiver.opensky_active_start_hour,
        opensky_active_end=config.receiver.opensky_active_end_hour,
    )
    receiver.start()

    # Enrichment pipeline
    pipeline = EnrichmentPipeline(db, receiver, config)
    pipeline.start()

    # ACARS / VDL-2 datalink — plane text messages (fed by acarsdec/dumpvdl2).
    acars = None
    if config.acars.enabled:
        try:
            from acars import AcarsReceiver
            acars = AcarsReceiver(udp_port=config.acars.udp_port,
                                  max_messages=config.acars.max_messages)
            acars.start()
        except Exception as e:
            logger.error("ACARS receiver failed to start: %s", e)
            acars = None

    # SeaDex AIS receiver + marine pipeline (marine traffic), if enabled.
    ais = None
    marine_pipeline = None
    if config.marine.enabled:
        ais = AISReceiver(
            home_lat=config.location.lat,
            home_lon=config.location.lon,
            ais_url=config.marine.ais_json_url,
            poll_interval=config.marine.poll_interval_seconds,
            stale_seconds=config.marine.stale_seconds,
            aishub_enabled=config.marine.aishub_enabled,
            aishub_username=config.marine.aishub_username,
            aishub_url=config.marine.aishub_url,
            aishub_interval=config.marine.aishub_poll_interval_seconds,
            aishub_api_enabled=config.marine.aishub_api_enabled,
            aisstream_enabled=config.marine.aisstream_enabled,
            aisstream_api_key=config.marine.aisstream_api_key,
            aisstream_url=config.marine.aisstream_url,
            cloud_radius_miles=config.marine.radius_miles,
        )
        ais.start()
        marine_pipeline = MarinePipeline(db, ais, config)
        marine_pipeline.start()

    # LandDex — trains (Stratford board + Amtrak pass-through watcher)
    land = None
    if config.land.enabled:
        try:
            from landdex import LandDexService
            land = LandDexService(db, config.location.lat, config.location.lon,
                                  station_name=config.land.station_name,
                                  radius_miles=config.land.radius_miles)
            land.start()
        except Exception as e:
            logger.error("LandDex failed to start: %s", e)

    # EtherDex — the RF neighborhood (repurposed AIS dongle + Bluetooth)
    ether = None
    if settings.get("ether_enabled"):
        try:
            from ether import EtherService
            ether = EtherService(db,
                                 device=str(settings.get("ether_device")),
                                 freqs=str(settings.get("ether_freqs")),
                                 bt_enabled=bool(settings.get("ether_bt")),
                                 audio_device=str(settings.get("ether_audio_device")),
                                 wifi_enabled=bool(settings.get("ether_wifi")))
            ether.start()
        except Exception as e:
            logger.error("EtherDex failed to start: %s", e)

    # Journeys — follow tagged craft worldwide (planes free; boats need a
    # second free aisstream.io key in SKYDEX_AISSTREAM_KEY2).
    journeys = None
    try:
        from journeys import JourneyService
        journeys = JourneyService(
            db, config.location.lat, config.location.lon, announcer=announcer,
            ais_key=os.environ.get("SKYDEX_AISSTREAM_KEY2", "").strip())
    except Exception as e:
        logger.error("Journeys failed to start: %s", e)

    # Voice — announcements honor the /admin toggles + quiet hours.
    announcer.wire_settings(settings)

    # StormDex — logs record-breakers, extreme alerts, and named storms.
    try:
        from weatherlog import WeatherLogWatcher
        from enrichment import WeatherClient as _WC
        WeatherLogWatcher(db, _WC(config.location.lat, config.location.lon),
                          config.marine.nws_marine_zone)
    except Exception as e:
        logger.error("StormDex failed to start: %s", e)

    # Wire globals into API module
    set_globals(db, receiver, config, ais, land, ether, journeys, acars)

    # ISS pass call-outs need the pass predictor that set_globals just created.
    import api as _api_mod
    IssVoiceWatcher(announcer, lambda: _api_mod._sat,
                    lambda: int(settings.get("iss_toast_min_elevation")))

    # With a dedicated audio dongle, the kiosk listens to ISS passes by itself.
    if ether is not None:
        from ether import IssAutoListener
        IssAutoListener(
            ether,
            passes_provider=lambda: ((_api_mod._sat.fetch(config.atmo.iss_norad_id) or {})
                                     .get("passes") if _api_mod._sat else []),
            enabled=lambda: bool(settings.get("iss_auto_listen")),
            announcer=announcer)

    # Nightly DB maintenance (retention pruning + WAL checkpoint) around 03:30
    # local — keeps the SQLite file small and the SD card happy.
    def _maintenance_loop() -> None:
        last_run_day = None
        while True:
            now = time.localtime()
            today = time.strftime("%Y-%m-%d", now)
            if now.tm_hour == 3 and now.tm_min >= 30 and last_run_day != today:
                last_run_day = today
                try:
                    days = int(settings.get("detections_retention_days"))
                    db.run_maintenance(days)
                except Exception as e:
                    logger.error("nightly maintenance failed: %s", e)
            time.sleep(300)

    threading.Thread(target=_maintenance_loop, daemon=True, name="db-maintenance").start()

    # Start FastAPI server (this blocks)
    logger.info("Starting web server on http://%s:%d", config.api_host, config.api_port)
    logger.info("Open your browser to http://localhost:%d", config.api_port)

    import uvicorn
    try:
        uvicorn.run(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level="warning",
            access_log=False,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        pipeline.stop()
        receiver.stop()
        if acars:
            acars.stop()
        if marine_pipeline:
            marine_pipeline.stop()
        if ais:
            ais.stop()
        if land:
            land.stop()
        logger.info("SkyDex stopped")


if __name__ == "__main__":
    main()
