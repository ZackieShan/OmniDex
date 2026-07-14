"""iSpy — Where in the World? A random live webcam, three guesses.

Cameras come from Windy's public webcams directory (~60k geo-tagged cams).
Free key: https://api.windy.com/keys  ->  .env: SKYDEX_WINDY_KEY=...

One round = one API call: six random webcams from a random category. The
first one with a usable image becomes the answer; the rest (different
countries only) become the decoy locations.
"""

from __future__ import annotations

import json
import logging
import random
import time
import urllib.request
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

BASE = "https://api.windy.com/webcams/api/v3/webcams"
CATEGORIES = ["beach", "city", "harbor", "mountain", "square", "lake", "traffic", "airport"]


class WindyPoint:
    """Windy point-forecast API — the same question asked of DIFFERENT weather
    models. Powers the 'Robot Forecast-Off' in the Weather Guess game.
    (ICON-EU only covers Europe, so the trio is global/US/NASA.)"""

    MODELS = [("gfs", "American robot (GFS)"),
              ("namConus", "Storm robot (NAM)"),
              ("geos5", "NASA robot (GEOS-5)")]

    def __init__(self, api_key: str, lat: float, lon: float):
        self.key = (api_key or "").strip()
        self.lat, self.lon = lat, lon
        self._cache: List[Dict[str, Any]] = []
        self._at = 0.0

    def tomorrow_highs(self) -> List[Dict[str, Any]]:
        if not self.key:
            return []
        if self._cache and time.time() - self._at < 10800:   # 3h cache
            return self._cache
        from datetime import datetime, timedelta
        target = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        out = []
        for model, label in self.MODELS:
            try:
                body = json.dumps({"lat": self.lat, "lon": self.lon, "model": model,
                                   "parameters": ["temp"], "levels": ["surface"],
                                   "key": self.key}).encode()
                req = urllib.request.Request(
                    "https://api.windy.com/api/point-forecast/v2", data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "SkyDex/1.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    d = json.load(r)
                ts = d.get("ts") or []
                temps = d.get("temp-surface") or []
                vals = [temps[i] for i in range(min(len(ts), len(temps)))
                        if datetime.fromtimestamp(ts[i] / 1000).strftime("%Y-%m-%d") == target
                        and temps[i] is not None]
                if vals:
                    out.append({"model": model, "label": label,
                                "high": round(max(vals) * 9 / 5 - 459.67)})  # K -> °F
            except Exception as e:
                logger.debug("windy point (%s) failed: %s", model, e)
        if out:
            self._cache, self._at = out, time.time()
        return out


class WindyCams:
    def __init__(self, api_key: str):
        self.key = (api_key or "").strip()
        self._totals: Dict[str, int] = {}
        self._totals_at = 0.0

    def _get(self, url: str) -> Dict[str, Any]:
        req = urllib.request.Request(url, headers={"x-windy-api-key": self.key,
                                                   "User-Agent": "SkyDex/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.load(r)

    def _total(self, cat: str) -> int:
        if time.time() - self._totals_at > 21600:      # re-count every 6h
            self._totals = {}
            self._totals_at = time.time()
        if cat not in self._totals:
            try:
                d = self._get(f"{BASE}?limit=1&offset=0&categories={cat}")
                self._totals[cat] = int(d.get("total") or 0)
            except Exception as e:
                logger.debug("windy total (%s) failed: %s", cat, e)
                self._totals[cat] = 0
        return self._totals[cat]

    @staticmethod
    def _find_url(obj: Any) -> str:
        """First http URL anywhere in a nested player/urls structure —
        Windy has shuffled this shape between API versions."""
        if isinstance(obj, str):
            return obj if obj.startswith("http") else ""
        if isinstance(obj, dict):
            for v in obj.values():
                u = WindyCams._find_url(v)
                if u:
                    return u
        if isinstance(obj, list):
            for v in obj:
                u = WindyCams._find_url(v)
                if u:
                    return u
        return ""

    def round(self) -> Dict[str, Any]:
        if not self.key:
            return {"error": "iSpy needs a (free) Windy webcams key — grab one at "
                             "api.windy.com/keys and put SKYDEX_WINDY_KEY=... in .env"}
        cats = CATEGORIES[:]
        random.shuffle(cats)
        for cat in cats[:3]:
            total = self._total(cat)
            if total < 12:
                continue
            offset = random.randint(0, max(0, min(total - 6, 1500)))
            try:
                d = self._get(f"{BASE}?limit=6&offset={offset}&categories={cat}"
                              "&include=images,location,player,urls")
            except Exception as e:
                logger.debug("windy fetch (%s@%s) failed: %s", cat, offset, e)
                continue
            entries: List[Dict[str, Any]] = []
            for w in d.get("webcams") or []:
                loc = w.get("location") or {}
                entries.append({
                    "title": w.get("title") or "",
                    "city": loc.get("city") or "",
                    "country": loc.get("country") or "",
                    "continent": loc.get("continent") or "",
                    "lat": loc.get("latitude"), "lon": loc.get("longitude"),
                    "image": ((w.get("images") or {}).get("current") or {}).get("preview") or "",
                    "player": self._find_url(w.get("player")),
                })
            answer = next((e for e in entries
                           if e["image"] and e["city"] and e["country"]), None)
            if not answer:
                continue
            decoys = [e for e in entries
                      if e is not answer and e["city"] and e["country"]
                      and e["country"] != answer["country"]]
            answer["category"] = cat
            return {"answer": answer, "decoys": decoys[:5]}
        return {"error": "No camera answered the call — spin again!"}
