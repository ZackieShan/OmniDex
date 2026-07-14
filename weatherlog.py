"""StormDex — logs notable weather as catches, like planes and boats.

Every 30 minutes the watcher:
  1. Reads today's stats from Open-Meteo (running high/low, rain, snow, wind).
  2. Compares the high/low against the ALL-TIME record for this calendar date
     (the climate archive already built for the Forecast view). Broken record ->
     logged. Within 2°F -> "near record" logged.
  3. Scans active NWS alerts: Severe/Extreme events get logged; named storms
     ("Hurricane Lee", "Tropical Storm...", "Winter Storm...") get their own
     kind so the future "on this day" cards read like history.

Events are kept forever — in five years the kiosk says
"On this day in 2026: 98°F broke the 1956 record (96°)".
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

NAMED_STORM = re.compile(
    r"\b(Hurricane|Tropical Storm|Typhoon|Winter Storm|Blizzard|Nor'?easter)\s+([A-Z][a-z]+)")


class WeatherLogWatcher:
    def __init__(self, db, weather_client, marine_zone: str = ""):
        self.db = db
        self.weather = weather_client          # enrichment.WeatherClient
        self.marine_zone = marine_zone
        self._logged_alert_keys = set()
        threading.Thread(target=self._loop, daemon=True, name="stormdex").start()
        logger.info("StormDex watcher started")

    # -- today's observed stats (Open-Meteo, one small call) -------------------
    def _today_stats(self) -> Optional[Dict[str, Any]]:
        try:
            url = ("https://api.open-meteo.com/v1/forecast"
                   f"?latitude={self.weather.lat}&longitude={self.weather.lon}"
                   "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
                   "snowfall_sum,wind_gusts_10m_max"
                   "&temperature_unit=fahrenheit&wind_speed_unit=mph"
                   "&precipitation_unit=inch&forecast_days=1&timezone=auto")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                d = (json.load(resp).get("daily") or {})
            g = lambda k: (d.get(k) or [None])[0]
            return {"high_f": g("temperature_2m_max"), "low_f": g("temperature_2m_min"),
                    "rain_in": g("precipitation_sum"), "snow_in": g("snowfall_sum"),
                    "gust_mph": g("wind_gusts_10m_max")}
        except Exception as e:
            logger.debug("stormdex stats failed: %s", e)
            return None

    def _check_records(self, today: str) -> None:
        rec = self.weather.fetch_climate_record()
        stats = self._today_stats()
        if not rec or not stats or stats["high_f"] is None:
            return
        sj = json.dumps({**stats, "record_high": rec.get("record_high"),
                         "high_year": rec.get("high_year"),
                         "record_low": rec.get("record_low"),
                         "low_year": rec.get("low_year")})
        hi, rh = round(stats["high_f"]), rec.get("record_high")
        lo, rl = (round(stats["low_f"]) if stats["low_f"] is not None else None), rec.get("record_low")
        if rh is not None and hi >= rh:
            day_name = datetime.now().strftime("%B %d").replace(" 0", " ")
            self.db.log_weather_event(today, "record_high",
                f"{hi}°F — broke the {rec.get('high_year')} record of {rh}°F",
                f"Hottest {day_name} since records began (1950).",
                sj, "record")
            try:
                from voice import announcer
                announcer.say(f"Weather record broken. {hi} degrees — the hottest "
                              f"{day_name} since records began.",
                              "storm", dedup_key=f"rec-{today}", dedup_seconds=43200)
            except Exception:
                pass
        elif rh is not None and hi >= rh - 2:
            self.db.log_weather_event(today, "near_record",
                f"{hi}°F — within {rh - hi}° of the {rec.get('high_year')} record ({rh}°F)",
                "So close. The old record survives another year.", sj, "near")
        if lo is not None and rl is not None and lo <= rl:
            self.db.log_weather_event(today, "record_low",
                f"{lo}°F — broke the {rec.get('low_year')} cold record of {rl}°F",
                "Coldest this date has ever been here.", sj, "record")
        # Big snow days are catches in their own right.
        if stats.get("snow_in") and stats["snow_in"] >= 4:
            self.db.log_weather_event(today, "snow",
                f"{round(stats['snow_in'], 1)}\" of snow",
                f"Gusts to {round(stats.get('gust_mph') or 0)} mph.", sj, "snow")

    def _check_alerts(self, today: str) -> None:
        try:
            alerts = self.weather.fetch_alerts(self.marine_zone)
        except Exception:
            return
        for a in alerts:
            event = a.get("event") or ""
            sev = (a.get("severity") or "").lower()
            headline = a.get("headline") or ""
            named = NAMED_STORM.search(f"{event} {headline}")
            if named:
                name = f"{named.group(1)} {named.group(2)}"
                self.db.log_weather_event(today, "named_storm", name,
                                          headline[:200], None, a.get("severity") or "")
                try:
                    from voice import announcer
                    announcer.say(f"{name} is in the forecast area.",
                                  "storm", dedup_key=f"storm-{name}", dedup_seconds=86400)
                except Exception:
                    pass
            elif sev in ("severe", "extreme") or any(
                    s in event for s in ("Hurricane", "Tornado", "Flood", "Blizzard",
                                         "Ice Storm", "High Wind", "Storm Surge")):
                key = f"{today}:{event}"
                if key in self._logged_alert_keys:
                    continue
                self._logged_alert_keys.add(key)
                self.db.log_weather_event(today, "alert", event,
                                          headline[:200], None, a.get("severity") or "")

    def _backfill_history(self) -> None:
        """One-time seed: the climate archive already knows every date's record
        holder since 1950 — write those as historical events so 'On This Day'
        is rich from day one instead of after a year of collecting."""
        import os
        marker = [e for e in self.db.list_weather_events(2000)
                  if e.get("kind") == "seed_marker"]
        if marker:
            return
        path = os.path.expanduser("~/.skydex/climate_records.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, ValueError):
            return          # archive not built yet — retry next startup
        months = ["", "January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"]
        n = 0
        for md, r in records.items():
            try:
                mm, dd = int(md[:2]), int(md[3:])
                day_name = f"{months[mm]} {dd}"
                if r.get("record_high") is not None and r.get("high_year"):
                    self.db.log_weather_event(
                        f"{r['high_year']}-{md}", "record_high",
                        f"{r['record_high']}°F — still the record for {day_name}",
                        "Hottest this date has ever been here (archive, 1950-present).",
                        None, "record")
                    n += 1
                if r.get("record_low") is not None and r.get("low_year"):
                    self.db.log_weather_event(
                        f"{r['low_year']}-{md}", "record_low",
                        f"{r['record_low']}°F — still the cold record for {day_name}",
                        "Coldest this date has ever been here (archive, 1950-present).",
                        None, "record")
                    n += 1
            except (ValueError, KeyError):
                continue
        self.db.log_weather_event("1900-01-01", "seed_marker", "history backfilled")
        logger.info("StormDex: backfilled %d historical record events", n)

    def _loop(self) -> None:
        time.sleep(180)   # let the server warm up (climate archive may build)
        try:
            self._backfill_history()
        except Exception as e:
            logger.debug("stormdex backfill failed: %s", e)
        while True:
            today = datetime.now().strftime("%Y-%m-%d")
            try:
                self._check_records(today)
                self._check_alerts(today)
            except Exception as e:
                logger.debug("stormdex check failed: %s", e)
            time.sleep(1800)
