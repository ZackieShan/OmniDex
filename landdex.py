"""LandDex — trains! Metro-North schedule board for Stratford station plus a
live Amtrak pass-through tracker for the Northeast Corridor.

Data sources (both free, stdlib-only):
  - MTA static GTFS zip (schedule): downloaded weekly, parsed for Stratford's
    stop times. No key, no realtime dependency — the board always works.
  - Amtraker v3 (https://api-v3.amtraker.com/v3/trains): community JSON API of
    live Amtrak positions/speeds. Acelas and NE Regionals blast through
    Stratford without stopping — this catches them in the act.

A background watcher logs every Amtrak train that passes within radius into
the trains table, building a collectible Traindex (Acela = the shiny).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import threading
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from receiver import _haversine, _bearing

logger = logging.getLogger(__name__)

GTFS_URL = "http://web.mta.info/developers/data/mnr/google_transit.zip"
AMTRAKER_URL = "https://api-v3.amtraker.com/v3/trains"


def train_rarity(route: str) -> str:
    r = (route or "").lower()
    if "acela" in r:
        return "Epic"
    if "regional" in r:
        return "Common"
    return "Rare"          # Vermonter specials, deadheads, anything unusual


# ===========================================================================
# Metro-North static GTFS — Stratford departures
# ===========================================================================
class GtfsSchedule:
    """Downloads the MNR GTFS zip (weekly) and answers 'next trains at
    Stratford'. Parses only what's needed; a bad download keeps the last good
    file. All stdlib."""

    def __init__(self, station_name: str = "Stratford",
                 cache_dir: str = "~/.skydex", max_age_days: float = 7.0):
        self.station_name = station_name.lower()
        self.zip_path = os.path.join(os.path.expanduser(cache_dir), "gtfs_mnr.zip")
        self.max_age = max_age_days * 86400
        self._lock = threading.Lock()
        self._day_cache: Dict[str, List[Dict[str, Any]]] = {}   # date -> deps

    # -- data acquisition ----------------------------------------------------
    def _ensure_zip(self) -> bool:
        try:
            if os.path.exists(self.zip_path) and \
                    time.time() - os.path.getmtime(self.zip_path) < self.max_age:
                return True
        except OSError:
            pass
        try:
            logger.info("LandDex: downloading MNR GTFS schedule…")
            req = urllib.request.Request(GTFS_URL, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            zipfile.ZipFile(io.BytesIO(data)).namelist()   # validate before saving
            os.makedirs(os.path.dirname(self.zip_path), exist_ok=True)
            with open(self.zip_path, "wb") as f:
                f.write(data)
            self._day_cache.clear()
            return True
        except Exception as e:
            logger.warning("LandDex: GTFS download failed: %s (using cached copy if any)", e)
            return os.path.exists(self.zip_path)

    def _read_csv(self, zf: zipfile.ZipFile, name: str):
        with zf.open(name) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

    # -- schedule computation --------------------------------------------------
    def _build_day(self, day: datetime) -> List[Dict[str, Any]]:
        """All Stratford departures for a calendar day: [{epoch, headsign,
        nyc_bound, train_num}] sorted by time."""
        if not self._ensure_zip():
            return {"stratford": [], "gct": []}
        date_str = day.strftime("%Y%m%d")
        dow = day.strftime("%A").lower()
        try:
            with zipfile.ZipFile(self.zip_path) as zf:
                # 1. service ids active today
                active = set()
                names = zf.namelist()
                if "calendar.txt" in names:
                    for r in self._read_csv(zf, "calendar.txt"):
                        if r.get(dow) == "1" and r.get("start_date", "0") <= date_str <= r.get("end_date", "9"):
                            active.add(r["service_id"])
                if "calendar_dates.txt" in names:
                    for r in self._read_csv(zf, "calendar_dates.txt"):
                        if r.get("date") != date_str:
                            continue
                        if r.get("exception_type") == "1":
                            active.add(r["service_id"])
                        elif r.get("exception_type") == "2":
                            active.discard(r["service_id"])
                if not active:
                    return {"stratford": [], "gct": []}

                # 2. Stop ids: Stratford, GCT, and the train-vs-car stations
                stop_ids, gct_ids = set(), set()
                extra_ids: Dict[str, set] = {"New Haven": set(), "Westport": set(),
                                             "Greenwich": set()}
                for r in self._read_csv(zf, "stops.txt"):
                    name = (r.get("stop_name") or "").lower()
                    if self.station_name in name:
                        stop_ids.add(r["stop_id"])
                    elif "grand central" in name:
                        gct_ids.add(r["stop_id"])
                    elif name.startswith("new haven"):
                        extra_ids["New Haven"].add(r["stop_id"])
                    elif "westport" in name:
                        extra_ids["Westport"].add(r["stop_id"])
                    elif name == "greenwich":
                        extra_ids["Greenwich"].add(r["stop_id"])
                extra_lookup = {sid: st for st, ids in extra_ids.items() for sid in ids}
                if not stop_ids:
                    logger.warning("LandDex: no GTFS stop matching %r", self.station_name)
                    return {"stratford": [], "gct": []}

                # 3. today's trips (id -> headsign)
                trips: Dict[str, Dict[str, str]] = {}
                for r in self._read_csv(zf, "trips.txt"):
                    if r.get("service_id") in active:
                        trips[r["trip_id"]] = {
                            "headsign": r.get("trip_headsign") or "",
                            "short": r.get("trip_short_name") or "",
                        }

                # 4. stop_times rows at Stratford + GCT for those trips
                out = []
                gct_times: Dict[str, float] = {}       # trip_id -> time at GCT
                gct_outbound: List[Dict[str, Any]] = []  # trips LEAVING GCT (all lines)
                midnight = datetime(day.year, day.month, day.day)

                def _epoch(tstr: str) -> Optional[float]:
                    try:
                        hh, mm, ss = (int(x) for x in tstr.split(":"))
                        return (midnight + timedelta(hours=hh, minutes=mm, seconds=ss)).timestamp()
                    except (ValueError, AttributeError):
                        return None

                trip_extra: Dict[str, Dict[str, float]] = {}
                for r in self._read_csv(zf, "stop_times.txt"):
                    sid = r.get("stop_id")
                    tid = r.get("trip_id")
                    if tid not in trips:
                        continue
                    st = extra_lookup.get(sid)
                    if st:
                        e = _epoch(r.get("departure_time") or r.get("arrival_time") or "")
                        if e is not None:
                            trip_extra.setdefault(tid, {})[st] = e
                    if sid in stop_ids:
                        epoch = _epoch(r.get("departure_time") or r.get("arrival_time") or "")
                        if epoch is None:
                            continue
                        head = trips[tid]["headsign"]
                        out.append({
                            "epoch": epoch,
                            "headsign": head,
                            "nyc_bound": "grand central" in head.lower(),
                            "train_num": trips[tid]["short"],
                            "trip_id": tid,
                        })
                    elif sid in gct_ids:
                        e = _epoch(r.get("departure_time") or r.get("arrival_time") or "")
                        if e is None:
                            continue
                        gct_times[tid] = e
                        # stop_sequence <= 1 => the trip STARTS at GCT (outbound)
                        try:
                            seq = int(r.get("stop_sequence") or 99)
                        except ValueError:
                            seq = 99
                        if seq <= 1:
                            gct_outbound.append({
                                "epoch": e,
                                "headsign": trips[tid]["headsign"],
                                "train_num": trips[tid]["short"],
                                "trip_id": tid,
                            })

                # Attach GCT times to Stratford departures (both directions):
                # NYC-bound -> ride time TO GCT; NH-bound -> the GCT departure
                # this train made before reaching Stratford (= train FROM GCT).
                for dep in out:
                    t_gct = gct_times.get(dep["trip_id"])
                    if t_gct is not None:
                        mins = abs(dep["epoch"] - t_gct) / 60
                        if 30 < mins < 240:
                            if dep["nyc_bound"]:
                                dep["gct_minutes"] = round(mins)
                            else:
                                dep["gct_depart"] = t_gct
                                dep["gct_minutes"] = round(mins)
                    # Ride times to the train-vs-car stations this trip serves
                    # AFTER Stratford (only count stops in the travel direction).
                    ex = trip_extra.get(dep["trip_id"])
                    if ex:
                        rides = {st: round((t - dep["epoch"]) / 60)
                                 for st, t in ex.items()
                                 if 3 < (t - dep["epoch"]) / 60 < 240}
                        if rides:
                            dep["rides"] = rides
                    dep.pop("trip_id", None)
                out.sort(key=lambda x: x["epoch"])
                gct_outbound.sort(key=lambda x: x["epoch"])
                return {"stratford": out, "gct": gct_outbound}
        except Exception as e:
            logger.warning("LandDex: GTFS parse failed: %s", e)
            return {"stratford": [], "gct": []}

    def departures(self, per_direction: int = 6) -> Dict[str, Any]:
        """Next departures each way from now (spills into tomorrow if needed)."""
        now = time.time()
        nyc: List[Dict[str, Any]] = []
        nh: List[Dict[str, Any]] = []
        with self._lock:
            for offset in (0, 1):     # today, then tomorrow
                day = datetime.now() + timedelta(days=offset)
                key = day.strftime("%Y-%m-%d")
                if key not in self._day_cache:
                    self._day_cache[key] = self._build_day(day)
                    # keep the cache tiny
                    for k in list(self._day_cache):
                        if k not in (key, datetime.now().strftime("%Y-%m-%d")):
                            pass
                for dep in self._day_cache[key]["stratford"]:
                    if dep["epoch"] < now - 60:
                        continue
                    bucket = nyc if dep["nyc_bound"] else nh
                    if len(bucket) < per_direction:
                        bucket.append(dep)
                if len(nyc) >= per_direction and len(nh) >= per_direction:
                    break
        return {"station": "Stratford", "to_nyc": nyc, "to_new_haven": nh,
                "have_schedule": bool(nyc or nh)}

    def next_rides(self) -> Dict[str, Dict[str, Any]]:
        """Next train from Stratford to each train-vs-car station:
        {station: {depart, minutes}}. GCT comes from gct_minutes."""
        out: Dict[str, Dict[str, Any]] = {}
        now = time.time()
        deps = self.departures(per_direction=10)
        for dep in deps["to_nyc"] + deps["to_new_haven"]:
            if dep["epoch"] < now:
                continue
            if dep.get("nyc_bound") and dep.get("gct_minutes") and "Grand Central" not in out:
                out["Grand Central"] = {"depart": dep["epoch"], "minutes": dep["gct_minutes"]}
            for st, mins in (dep.get("rides") or {}).items():
                if st not in out:
                    out[st] = {"depart": dep["epoch"], "minutes": mins}
        return out

    # ---- Interactive network: every station + a real trip planner ---------

    def _stops_meta(self) -> Dict[str, Dict[str, Any]]:
        """stop_id -> {name, lat, lon} from stops.txt (cached)."""
        if getattr(self, "_stops_cache", None) is not None:
            return self._stops_cache
        meta: Dict[str, Dict[str, Any]] = {}
        try:
            if self._ensure_zip():
                with zipfile.ZipFile(self.zip_path) as zf:
                    for r in self._read_csv(zf, "stops.txt"):
                        try:
                            meta[r["stop_id"]] = {
                                "name": r.get("stop_name") or r["stop_id"],
                                "lat": float(r.get("stop_lat") or 0),
                                "lon": float(r.get("stop_lon") or 0),
                            }
                        except (ValueError, KeyError):
                            continue
        except Exception as e:
            logger.debug("stops meta failed: %s", e)
        self._stops_cache = meta
        return meta

    def _network(self) -> Dict[str, Any]:
        """Today's flattened timetable: connections sorted by departure, plus
        which line serves each stop. Cached per calendar day."""
        day = datetime.now()
        key = day.strftime("%Y-%m-%d")
        cached = getattr(self, "_net_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        net = {"conns": [], "stop_line": {}}
        try:
            if not self._ensure_zip():
                raise RuntimeError("no gtfs zip")
            date_str = day.strftime("%Y%m%d")
            dow = day.strftime("%A").lower()
            midnight = datetime(day.year, day.month, day.day)
            with zipfile.ZipFile(self.zip_path) as zf:
                active = set()
                names = zf.namelist()
                if "calendar.txt" in names:
                    for r in self._read_csv(zf, "calendar.txt"):
                        if r.get(dow) == "1" and r.get("start_date", "0") <= date_str <= r.get("end_date", "9"):
                            active.add(r["service_id"])
                if "calendar_dates.txt" in names:
                    for r in self._read_csv(zf, "calendar_dates.txt"):
                        if r.get("date") == date_str:
                            (active.add if r.get("exception_type") == "1" else active.discard)(r["service_id"])
                routes = {}
                for r in self._read_csv(zf, "routes.txt"):
                    low = (r.get("route_long_name") or r.get("route_short_name") or "").lower()
                    routes[r.get("route_id") or ""] = ("Hudson" if "hudson" in low else
                                                       "Harlem" if "harlem" in low else "New Haven")
                trips = {}
                for r in self._read_csv(zf, "trips.txt"):
                    if r.get("service_id") in active:
                        trips[r["trip_id"]] = routes.get(r.get("route_id") or "", "New Haven")
                # Per-trip ordered stop events -> consecutive-pair connections.
                by_trip: Dict[str, List] = {}
                for r in self._read_csv(zf, "stop_times.txt"):
                    tid = r.get("trip_id")
                    if tid not in trips:
                        continue
                    t = r.get("departure_time") or r.get("arrival_time") or ""
                    try:
                        hh, mm, ss = (int(x) for x in t.split(":"))
                        epoch = (midnight + timedelta(hours=hh, minutes=mm, seconds=ss)).timestamp()
                        seq = int(r.get("stop_sequence") or 0)
                    except (ValueError, AttributeError):
                        continue
                    by_trip.setdefault(tid, []).append((seq, epoch, r.get("stop_id")))
                for tid, evs in by_trip.items():
                    evs.sort()
                    line = trips[tid]
                    for i in range(len(evs) - 1):
                        _, dep_t, dep_s = evs[i]
                        _, arr_t, arr_s = evs[i + 1]
                        net["conns"].append((dep_t, arr_t, dep_s, arr_s, tid, line))
                        net["stop_line"].setdefault(dep_s, line)
                        net["stop_line"].setdefault(arr_s, line)
                net["conns"].sort()
        except Exception as e:
            logger.warning("network build failed: %s", e)
        self._net_cache = (key, net)
        return net

    def stations(self) -> List[Dict[str, Any]]:
        """Every station with coords + line color key (for the tappable map)."""
        meta = self._stops_meta()
        net = self._network()
        out, seen = [], set()
        for sid, line in net["stop_line"].items():
            m = meta.get(sid)
            if not m or not m["lat"] or m["name"] in seen:
                continue
            seen.add(m["name"])
            out.append({"id": sid, "name": m["name"], "lat": m["lat"],
                        "lon": m["lon"], "line": line})
        return out

    def journey(self, target_id: str) -> Dict[str, Any]:
        """Earliest trip from Stratford to target, leaving now — Connection
        Scan over today's timetable, transfers included (4-min buffer)."""
        meta = self._stops_meta()
        net = self._network()
        target = meta.get(target_id)
        if not target:
            return {"error": "unknown station"}
        origin_ids = {sid for sid, m in meta.items()
                      if self.station_name in m["name"].lower()}
        # Also treat same-named stops as the target (platform variants).
        target_ids = {sid for sid, m in meta.items() if m["name"] == target["name"]}

        now = time.time()
        INF = float("inf")
        arr: Dict[str, float] = {sid: now for sid in origin_ids}
        back: Dict[str, tuple] = {}
        boarded = set()
        for c in net["conns"]:
            dep_t, arr_t, dep_s, arr_s, tid, line = c
            if dep_t < now:
                continue
            ok = (tid in boarded or
                  (dep_s in origin_ids and arr.get(dep_s, INF) <= dep_t) or
                  arr.get(dep_s, INF) + 240 <= dep_t)
            if not ok:
                continue
            boarded.add(tid)
            if arr_t < arr.get(arr_s, INF):
                arr[arr_s] = arr_t
                back[arr_s] = c

        best = min((sid for sid in target_ids if sid in back),
                   key=lambda s: arr[s], default=None)
        if best is None:
            return {"name": target["name"], "no_service": True}

        # Walk back, merging consecutive connections on the same trip into legs.
        chain = []
        cur = best
        while cur in back:
            chain.append(back[cur])
            cur = back[cur][2]
        chain.reverse()
        legs = []
        for c in chain:
            dep_t, arr_t, dep_s, arr_s, tid, line = c
            if legs and legs[-1]["trip"] == tid:
                legs[-1]["arr"], legs[-1]["to"] = arr_t, meta.get(arr_s, {}).get("name", "?")
            else:
                legs.append({"trip": tid, "line": line,
                             "from": meta.get(dep_s, {}).get("name", "?"), "dep": dep_t,
                             "to": meta.get(arr_s, {}).get("name", "?"), "arr": arr_t})
        for l in legs:
            l.pop("trip", None)
        return {"name": target["name"], "depart": legs[0]["dep"] if legs else None,
                "arrive": arr[best], "minutes": round((arr[best] - (legs[0]["dep"] if legs else now)) / 60),
                "transfers": max(0, len(legs) - 1), "legs": legs}

    @staticmethod
    def _line_for_headsign(headsign: str) -> str:
        """Which Metro-North line a GCT departure belongs to, by destination."""
        h = (headsign or "").lower()
        if any(s in h for s in ("poughkeepsie", "croton", "peekskill", "ossining",
                                "tarrytown", "yonkers", "hudson")):
            return "Hudson"
        if any(s in h for s in ("wassaic", "southeast", "brewster", "chappaqua",
                                "white plains", "mount kisco", "katonah", "harlem")):
            return "Harlem"
        return "New Haven"   # Stamford / Bridgeport / New Haven / branches

    def gct_snapshot(self, limit: int = 10) -> Dict[str, Any]:
        """The Grand Central view: next outbound departures on ALL lines, plus
        the next trains between GCT and Stratford in both directions."""
        now = time.time()
        board: List[Dict[str, Any]] = []
        with self._lock:
            for offset in (0, 1):
                day = datetime.now() + timedelta(days=offset)
                key = day.strftime("%Y-%m-%d")
                if key not in self._day_cache:
                    self._day_cache[key] = self._build_day(day)
                for dep in self._day_cache[key]["gct"]:
                    if dep["epoch"] < now - 60:
                        continue
                    board.append({"epoch": dep["epoch"], "headsign": dep["headsign"],
                                  "train_num": dep["train_num"],
                                  "line": self._line_for_headsign(dep["headsign"])})
                    if len(board) >= limit:
                        break
                if len(board) >= limit:
                    break

        deps = self.departures(per_direction=10)
        to_gct = next((d for d in deps["to_nyc"] if d.get("gct_minutes")), None)
        # Next train home: scan the FULL day (not the size-limited buckets) for
        # the first NH-bound Stratford arrival whose GCT departure is still in
        # the future. The catchable-now train arrives Stratford ~90 min from
        # now, so it often sits beyond the next-N list — that was the
        # "no more trains at 3PM" bug.
        from_gct = None
        with self._lock:
            for offset in (0, 1):
                key = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")
                if key not in self._day_cache:
                    self._day_cache[key] = self._build_day(datetime.now() + timedelta(days=offset))
                for dep in self._day_cache[key]["stratford"]:
                    if not dep["nyc_bound"] and dep.get("gct_depart") and dep["gct_depart"] > now:
                        from_gct = dep
                        break
                if from_gct:
                    break
        return {"board": board, "to_gct": to_gct, "from_gct": from_gct}


# ===========================================================================
# Amtrak live positions (Amtraker v3) + pass-through watcher
# ===========================================================================
class AmtrakClient:
    def __init__(self, home_lat: float, home_lon: float, radius_miles: float = 15.0):
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.radius = radius_miles
        self._cache: List[Dict[str, Any]] = []
        self._cache_at = 0.0

    def region(self, max_miles: float = 120.0) -> List[Dict[str, Any]]:
        """Amtrak trains across the whole map region (for the live map)."""
        self.nearby()   # refresh the shared cache if stale
        return [t for t in getattr(self, "_all", []) if t["distance_miles"] <= max_miles]

    def nearby(self) -> List[Dict[str, Any]]:
        """Amtrak trains within radius of home, nearest first (60s cache)."""
        if time.time() - self._cache_at < 60:
            return self._cache
        self._cache_at = time.time()
        try:
            req = urllib.request.Request(AMTRAKER_URL, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except Exception as e:
            logger.debug("Amtraker fetch failed: %s", e)
            return self._cache      # keep last good on a blip

        all_out = []
        try:
            groups = data.values() if isinstance(data, dict) else []
            for group in groups:
                items = group if isinstance(group, list) else [group]
                for t in items:
                    if not isinstance(t, dict):
                        continue
                    lat, lon = t.get("lat"), t.get("lon")
                    if lat is None or lon is None:
                        continue
                    dist = _haversine(self.home_lat, self.home_lon, lat, lon)
                    if dist > 250:            # keep the whole Northeast, skip the rest
                        continue
                    heading = t.get("heading")
                    try:
                        heading = float(heading)
                    except (TypeError, ValueError):
                        heading = None
                    # The corridor runs roughly SW<->NE here.
                    toward = None
                    if heading is not None:
                        toward = "New Haven / Boston" if 0 < heading < 180 else "New York"
                    route = t.get("routeName") or "Amtrak"
                    all_out.append({
                        "train_num": str(t.get("trainNum") or ""),
                        "route": route,
                        "lat": lat, "lon": lon,
                        "speed_mph": round(float(t.get("velocity") or 0)),
                        "heading": heading,
                        "toward": toward,
                        "distance_miles": round(dist, 1),
                        "origin": t.get("origName") or t.get("origCode"),
                        "dest": t.get("destName") or t.get("destCode"),
                        "state": t.get("trainState"),
                        "rarity": train_rarity(route),
                    })
        except Exception as e:
            logger.debug("Amtraker parse failed: %s", e)
        all_out.sort(key=lambda x: x["distance_miles"])
        self._all = all_out
        self._cache = [t for t in all_out if t["distance_miles"] <= self.radius]
        return self._cache


class LandDexService:
    """Facade main.py wires up: schedule + live Amtrak + Traindex logging."""

    LOG_RADIUS = 10.0    # a train inside this range counts as "seen"

    def __init__(self, db, home_lat: float, home_lon: float,
                 station_name: str = "Stratford", radius_miles: float = 15.0):
        self.db = db
        self.gtfs = GtfsSchedule(station_name)
        self.amtrak = AmtrakClient(home_lat, home_lon, radius_miles)
        self.road = RoadClient(home_lat, home_lon)
        self.news = RailNewsClient()
        self.waze = WazeClient(os.environ.get("SKYDEX_RAPIDAPI_KEY", ""))
        self.nycdot = NycDotClient(os.environ.get("SKYDEX_NYCDOT_KEY", ""))
        self.live = MnrLiveClient(self.gtfs)
        self.road_news = RailNewsClient(url=(
            "https://news.google.com/rss/search"
            "?q=%22I-95%22+Connecticut+traffic+OR+construction&hl=en-US&gl=US&ceid=US:en"))
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._watch, daemon=True, name="landdex-watch")
        self._thread.start()
        logger.info("LandDex started (station=%s)", self.gtfs.station_name.title())

    def stop(self) -> None:
        self._running = False

    def _watch(self) -> None:
        """Log passing Amtrak trains into the Traindex — even when nobody is
        looking at the Land view. Also pre-warms the GTFS cache at startup."""
        try:
            self.gtfs.departures()
        except Exception as e:
            logger.debug("LandDex gtfs warmup failed: %s", e)
        while self._running:
            try:
                for t in self.amtrak.nearby():
                    if t["distance_miles"] <= self.LOG_RADIUS and t["train_num"]:
                        self.db.log_train(t["train_num"], t["route"],
                                          t.get("speed_mph"), t["rarity"])
                        if "acela" in (t["route"] or "").lower() and t["distance_miles"] <= 6:
                            try:
                                from voice import announcer
                                announcer.say(
                                    f"Acela {t['train_num']} passing Stratford at "
                                    f"{t.get('speed_mph') or 'speed'} miles per hour.",
                                    "rail", dedup_key=f"acela-{t['train_num']}",
                                    dedup_seconds=1800)
                            except Exception:
                                pass
            except Exception as e:
                logger.debug("LandDex watcher error: %s", e)
            time.sleep(90)

    def snapshot(self) -> Dict[str, Any]:
        board = self.gtfs.departures()
        return {
            "board": board,
            "passing": self.amtrak.nearby(),
            "collection_count": self.db.get_train_count() if self.db else 0,
        }


# ===========================================================================
# Road — commute times (OSRM free baseline, TomTom live if key set)
# ===========================================================================
# Drive board destinations, in display order (user-specified).
COMMUTE_TARGETS = [
    ("Rochester NY", 43.1566, -77.6088),
    ("Catskill NY", 42.2176, -73.8646),
    ("Brooklyn NY", 40.6782, -73.9442),
    ("Norwalk CT", 41.1177, -73.4082),
    ("Westport CT", 41.1415, -73.3579),
    ("Bridgeport CT", 41.1792, -73.1894),
    ("New Haven CT", 41.3083, -72.9279),
    ("Mystic CT", 41.3543, -71.9665),
]

# Train-vs-car matchups (car destination = the station, apples to apples).
TVC_TARGETS = [
    ("New Haven", 41.29565, -72.92651),
    ("Westport", 41.11858, -73.37162),
    ("Greenwich", 41.02620, -73.62820),
    ("Grand Central", 40.75270, -73.97720),
]


class RoadClient:
    """Drive times from home, both directions, fetched in parallel.
    Provider order per leg: TomTom (live traffic, if key set) ->
    openrouteservice (your heigit key, 2000/day) -> OSRM demo (keyless).
    Each leg is cached 30 min, so the ~20 legs cost a couple of bursts a day."""

    def __init__(self, home_lat: float, home_lon: float):
        self.home_lat = home_lat
        self.home_lon = home_lon
        self._legs: Dict[str, Dict[str, Any]] = {}   # cache key -> {at, data}

    def drive(self, lat: float, lon: float, reverse: bool = False,
              tomtom_key: str = "") -> Dict[str, Any]:
        """One leg: home->dest (or dest->home when reverse). Cached 30 min."""
        key = f"{lat:.4f},{lon:.4f},{int(reverse)},{bool(tomtom_key)}"
        hit = self._legs.get(key)
        if hit and time.time() - hit["at"] < 1800:
            return hit["data"]
        a = (lat, lon) if reverse else (self.home_lat, self.home_lon)
        b = (self.home_lat, self.home_lon) if reverse else (lat, lon)
        ors_key = os.environ.get("SKYDEX_ORS_KEY", "")
        entry: Dict[str, Any] = {"minutes": None, "miles": None, "live": False}
        try:
            if tomtom_key:
                url = (f"https://api.tomtom.com/routing/1/calculateRoute/"
                       f"{a[0]},{a[1]}:{b[0]},{b[1]}/json?key={tomtom_key}&traffic=true")
                req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
                with urllib.request.urlopen(req, timeout=14) as resp:
                    summ = ((json.load(resp).get("routes") or [{}])[0].get("summary") or {})
                entry["minutes"] = round((summ.get("travelTimeInSeconds") or 0) / 60)
                entry["delay_min"] = round((summ.get("trafficDelayInSeconds") or 0) / 60)
                entry["miles"] = round((summ.get("lengthInMeters") or 0) / 1609.34)
                entry["live"] = True
            elif ors_key:
                url = ("https://api.openrouteservice.org/v2/directions/driving-car"
                       f"?api_key={ors_key}&start={a[1]},{a[0]}&end={b[1]},{b[0]}")
                req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
                with urllib.request.urlopen(req, timeout=14) as resp:
                    feats = (json.load(resp).get("features") or [{}])
                summ = ((feats[0].get("properties") or {}).get("summary") or {})
                entry["minutes"] = round((summ.get("duration") or 0) / 60)
                entry["miles"] = round((summ.get("distance") or 0) / 1609.34)
            else:
                url = (f"https://router.project-osrm.org/route/v1/driving/"
                       f"{a[1]},{a[0]};{b[1]},{b[0]}?overview=false")
                req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
                with urllib.request.urlopen(req, timeout=14) as resp:
                    route = ((json.load(resp).get("routes") or [{}])[0])
                entry["minutes"] = round((route.get("duration") or 0) / 60)
                entry["miles"] = round((route.get("distance") or 0) / 1609.34)
        except Exception as e:
            logger.debug("drive leg %s failed: %s", key, e)
        self._legs[key] = {"at": time.time(), "data": entry}
        return entry

    def commutes(self, tomtom_key: str = "") -> Dict[str, List[Dict[str, Any]]]:
        """The drive board: TO each destination and FROM each, in parallel."""
        from concurrent.futures import ThreadPoolExecutor
        jobs = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for name, lat, lon in COMMUTE_TARGETS:
                jobs.append((name, False, pool.submit(self.drive, lat, lon, False, tomtom_key)))
                jobs.append((name, True, pool.submit(self.drive, lat, lon, True, tomtom_key)))
        to_list, from_list = [], []
        for name, rev, fut in jobs:
            try:
                d = fut.result(timeout=20)
            except Exception:
                d = {"minutes": None}
            (from_list if rev else to_list).append({"name": name, **d})
        return {"to": to_list, "from": from_list}

    def tvc_drives(self, tomtom_key: str = "") -> Dict[str, Dict[str, Any]]:
        """Car legs for the train-vs-car matchups (to the stations), parallel."""
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {name: pool.submit(self.drive, lat, lon, False, tomtom_key)
                    for name, lat, lon in TVC_TARGETS}
            out = {}
            for name, fut in futs.items():
                try:
                    out[name] = fut.result(timeout=20)
                except Exception:
                    out[name] = {"minutes": None}
        return out


class WazeClient:
    """Waze incidents on the I-95 corridor via RapidAPI. The plan is only 100
    requests/MONTH, so this is disk-cached for 8 hours (~3 calls/day) and the
    stamp survives restarts — a deploy can't burn the quota."""

    CACHE_PATH = os.path.expanduser("~/.skydex/waze_cache.json")
    TTL = 8 * 3600
    # Corridor box: Westport -> New Haven along I-95
    BOX = {"bl": "41.05,-73.40", "tr": "41.35,-72.85"}

    def __init__(self, rapidapi_key: str):
        self.key = rapidapi_key

    def incidents(self) -> List[Dict[str, Any]]:
        try:
            with open(self.CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("ts", 0) < self.TTL:
                return cached.get("incidents", [])
        except (OSError, ValueError):
            cached = None

        if not self.key:
            return []
        out: List[Dict[str, Any]] = []
        try:
            url = ("https://waze-api.p.rapidapi.com/alerts-and-jams"
                   f"?bottom_left={self.BOX['bl']}&top_right={self.BOX['tr']}"
                   "&max_alerts=12&max_jams=8")
            req = urllib.request.Request(url, headers={
                "x-rapidapi-host": "waze-api.p.rapidapi.com",
                "x-rapidapi-key": self.key,
                "User-Agent": "SkyDex/1.0",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
            for a in (data.get("alerts") or [])[:12]:
                if not isinstance(a, dict):
                    continue
                loc = a.get("location") if isinstance(a.get("location"), dict) else {}
                out.append({
                    "kind": (a.get("type") or "ALERT").replace("_", " ").title(),
                    "detail": (a.get("subtype") or "").replace("_", " ").title(),
                    "where": ", ".join(x for x in (a.get("street"), a.get("city")) if x),
                    "lat": loc.get("y") or a.get("latitude") or a.get("lat"),
                    "lon": loc.get("x") or a.get("longitude") or a.get("lng"),
                    "src": "Waze",
                })
            for j in (data.get("jams") or [])[:8]:
                if not isinstance(j, dict):
                    continue
                delay = j.get("delay_seconds") or j.get("delay") or 0
                out.append({
                    "kind": "Traffic Jam",
                    "detail": f"+{round(delay / 60)} min" if delay else "slow",
                    "where": ", ".join(x for x in (j.get("street"), j.get("city")) if x),
                    "src": "Waze",
                })
        except Exception as e:
            logger.debug("waze fetch failed: %s", e)
            return (cached or {}).get("incidents", []) if cached else []

        try:
            os.makedirs(os.path.dirname(self.CACHE_PATH), exist_ok=True)
            with open(self.CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "incidents": out}, f)
        except OSError:
            pass
        return out


class NycDotClient:
    """NYC DOT trafficSpeed feed (api.nyc.gov/dot) — live speed detectors on
    the city's highways. We keep only the corridors a Stratford->Manhattan
    drive actually uses: I-95/Cross Bronx, Hutchinson Pkwy, Bruckner, RFK.
    Auth: Ocp-Apim-Subscription-Key header. Cached 10 min."""

    URL = "https://api.nyc.gov/dot/trafficSpeed"
    CORRIDORS = ("95", "CROSS BRONX", "CBE", "HUTCH", "BRUCKNER", "RFK", "TRIBORO")

    def __init__(self, key: str):
        self.key = key
        self._cache: List[Dict[str, Any]] = []
        self._cache_at = 0.0

    @staticmethod
    def _val(d: Dict[str, Any], *names) -> Any:
        low = {k.lower().replace("_", ""): v for k, v in d.items()}
        for n in names:
            if n in low and low[n] not in (None, ""):
                return low[n]
        return None

    def speeds(self) -> List[Dict[str, Any]]:
        if time.time() - self._cache_at < 600:
            return self._cache
        self._cache_at = time.time()
        if not self.key:
            return self._cache
        try:
            req = urllib.request.Request(self.URL, headers={
                "Ocp-Apim-Subscription-Key": self.key,
                "Accept": "application/json",
                "User-Agent": "SkyDex/1.0",
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.load(resp)
            rows = data if isinstance(data, list) else \
                next((v for v in data.values() if isinstance(v, list)), []) if isinstance(data, dict) else []
            out, seen = [], set()
            for r in rows:
                if not isinstance(r, dict):
                    continue
                name = str(self._val(r, "linkname", "link", "name") or "").upper()
                if not name or not any(c in name for c in self.CORRIDORS):
                    continue
                if name in seen:
                    continue
                seen.add(name)
                try:
                    mph = round(float(self._val(r, "speed", "speedmph") or 0))
                except (TypeError, ValueError):
                    continue
                if mph <= 0:
                    continue
                out.append({"name": name.title()[:52], "mph": mph})
                if len(out) >= 8:
                    break
            if out:
                self._cache = out
        except Exception as e:
            logger.debug("NYC DOT speeds failed: %s", e)
        return self._cache


# ===========================================================================
# Live Metro-North positions — MTA GTFS-Realtime, decoded with a minimal
# pure-stdlib protobuf reader (no dependencies). This is exactly what
# traintracker.live does; we just draw it on our own Leaflet map.
# ===========================================================================
import struct


def _pb_varint(buf: bytes, i: int):
    val, shift = 0, 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, i
        shift += 7


def _pb_fields(buf: bytes, start: int, end: int):
    """Yield (field_number, wire_type, raw_value) for one protobuf message."""
    i = start
    while i < end:
        tag, i = _pb_varint(buf, i)
        fno, wt = tag >> 3, tag & 7
        if wt == 0:
            val, i = _pb_varint(buf, i)
        elif wt == 1:
            val = buf[i:i + 8]; i += 8
        elif wt == 2:
            ln, i = _pb_varint(buf, i)
            val = buf[i:i + ln]; i += ln
        elif wt == 5:
            val = buf[i:i + 4]; i += 4
        else:
            return
        yield fno, wt, val


def _decode_gtfs_rt_vehicles(buf: bytes) -> List[Dict[str, Any]]:
    """FeedMessage -> entities -> VehiclePosition {trip, position, label}.
    Field numbers per the official gtfs-realtime.proto."""
    out = []
    for fno, wt, ent in _pb_fields(buf, 0, len(buf)):
        if fno != 2 or wt != 2:            # FeedMessage.entity
            continue
        vehicle = None
        for f2, w2, v2 in _pb_fields(ent, 0, len(ent)):
            if f2 == 4 and w2 == 2:        # FeedEntity.vehicle
                vehicle = v2
        if vehicle is None:
            continue
        train: Dict[str, Any] = {}
        for f3, w3, v3 in _pb_fields(vehicle, 0, len(vehicle)):
            if f3 == 1 and w3 == 2:        # trip: TripDescriptor
                for f4, w4, v4 in _pb_fields(v3, 0, len(v3)):
                    if f4 == 1 and w4 == 2:
                        train["trip_id"] = v4.decode("utf-8", "ignore")
                    elif f4 == 5 and w4 == 2:
                        train["route_id"] = v4.decode("utf-8", "ignore")
            elif f3 == 2 and w3 == 2:      # position
                for f4, w4, v4 in _pb_fields(v3, 0, len(v3)):
                    if w4 == 5:
                        fv = struct.unpack("<f", v4)[0]
                        if f4 == 1:
                            train["lat"] = round(fv, 5)
                        elif f4 == 2:
                            train["lon"] = round(fv, 5)
                        elif f4 == 3:
                            train["bearing"] = round(fv)
            elif f3 == 8 and w3 == 2:      # vehicle: VehicleDescriptor
                for f4, w4, v4 in _pb_fields(v3, 0, len(v3)):
                    if f4 == 2 and w4 == 2:
                        train["label"] = v4.decode("utf-8", "ignore")
        if train.get("lat") and train.get("lon"):
            out.append(train)
    return out


class MnrLiveClient:
    """Live Metro-North train positions. 25s cache; optional x-api-key."""

    def __init__(self, gtfs: "GtfsSchedule"):
        self.gtfs = gtfs
        self._routes: Optional[Dict[str, str]] = None   # route_id -> line name
        self._cache: List[Dict[str, Any]] = []
        self._cache_at = 0.0

    def _route_lines(self) -> Dict[str, str]:
        if self._routes is not None:
            return self._routes
        routes: Dict[str, str] = {}
        try:
            if self.gtfs._ensure_zip():
                with zipfile.ZipFile(self.gtfs.zip_path) as zf:
                    for r in self.gtfs._read_csv(zf, "routes.txt"):
                        name = (r.get("route_long_name") or r.get("route_short_name") or "")
                        low = name.lower()
                        line = ("Hudson" if "hudson" in low else
                                "Harlem" if "harlem" in low else "New Haven")
                        routes[r.get("route_id") or ""] = line
        except Exception as e:
            logger.debug("routes.txt parse failed: %s", e)
        self._routes = routes
        return routes

    def trains(self, url: str, api_key: str = "") -> List[Dict[str, Any]]:
        if time.time() - self._cache_at < 25:
            return self._cache
        self._cache_at = time.time()
        if not url:
            return self._cache
        try:
            headers = {"User-Agent": "SkyDex/1.0"}
            if api_key:
                headers["x-api-key"] = api_key
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                buf = resp.read()
            trains = _decode_gtfs_rt_vehicles(buf)
            lines = self._route_lines()
            for t in trains:
                t["line"] = lines.get(t.get("route_id", ""), "New Haven")
            self._cache = trains
        except Exception as e:
            logger.warning("MNR live feed failed: %s", e)
        return self._cache


# ===========================================================================
# Metro-North news (Google News RSS — keyless)
# ===========================================================================
class RailNewsClient:
    URL = ("https://news.google.com/rss/search"
           "?q=%22Metro-North%22+OR+%22New+Haven+Line%22&hl=en-US&gl=US&ceid=US:en")

    def __init__(self, ttl: int = 21600, url: Optional[str] = None):
        self.ttl = ttl
        self.url = url or self.URL
        self._cache: List[Dict[str, str]] = []
        self._cache_at = 0.0

    def headlines(self, n: int = 6) -> List[Dict[str, str]]:
        if self._cache and time.time() - self._cache_at < self.ttl:
            return self._cache[:n]
        try:
            import xml.etree.ElementTree as ET
            req = urllib.request.Request(self.url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                root = ET.fromstring(resp.read())
            items = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                pub = (item.findtext("pubDate") or "")[:16]
                src = item.find("source")
                source = (src.text if src is not None else "") or ""
                if title:
                    items.append({"title": title, "date": pub, "source": source})
                if len(items) >= 12:
                    break
            if items:
                self._cache, self._cache_at = items, time.time()
        except Exception as e:
            logger.debug("rail news failed: %s", e)
        return self._cache[:n]
