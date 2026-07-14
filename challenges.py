"""Daily & weekly challenges — achievements that reset themselves.

Progress is computed live from TIME-WINDOWED counters (today / since Sunday),
so nothing needs "resetting": at midnight the window slides and everyone starts
fresh. Each day/week deterministically draws a rotating trio from its pool
(seeded by the date), so the whole family sees the same challenges and
tomorrow brings different ones.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

# (id, title, description, stat_key, threshold, domain)
DAILY_POOL = [
    ("d_air5",    "Busy Skies",        "Catch 5 aircraft today",               "air_today",       5,  "air"),
    ("d_air15",   "Air Traffic Day",   "15 aircraft sightings today",          "air_today",       15, "air"),
    ("d_new_air", "Fresh Catch",       "Log a brand-new aircraft today",       "new_air_today",   1,  "air"),
    ("d_heavy",   "Heavy Day",         "Catch a heavy widebody today",         "heavy_today",     1,  "air"),
    ("d_sea3",    "Harbor Watch",      "3 vessel sightings today",             "sea_today",       3,  "sea"),
    ("d_sea_new", "New Sail",          "Log a brand-new vessel today",         "new_sea_today",   1,  "sea"),
    ("d_ether",   "New Whisper",       "Hear a brand-new device today",        "new_ether_today", 1,  "ether"),
    ("d_game1",   "Game On",           "Play any arcade game today",           "games_today",     1,  "fam"),
    ("d_game3",   "Triple Play",       "Play 3 arcade games today",            "games_today",     3,  "fam"),
    ("d_wx",      "Weather Prophet",   "Lock in tomorrow's temperature guess", "wx_locked_today", 1,  "storm"),
    ("d_spot",    "Called It!",        "Claim a spotter credit today",         "spotter_today",   1,  "fam"),
]

WEEKLY_POOL = [
    ("w_air50",   "Week of Wings",     "50 aircraft sightings this week",      "air_week",        50, "air"),
    ("w_new5",    "Five Fresh Frames", "5 brand-new aircraft this week",       "new_air_week",    5,  "air"),
    ("w_sea15",   "Fleet Week",        "15 vessel sightings this week",        "sea_week",        15, "sea"),
    ("w_games10", "Arcade Champion",   "10 games played this week",            "games_week",      10, "fam"),
    ("w_ether3",  "Ether Explorer",    "3 new devices heard this week",        "new_ether_week",  3,  "ether"),
    ("w_wx3",     "Forecast Faithful", "3 weather guesses this week",          "wx_week",         3,  "storm"),
    ("w_days5",   "Daily Visitor",     "Catches on 5 different days this week", "days_week",      5,  "air"),
]


def _pick(pool: List, seed: str, n: int) -> List:
    rng = random.Random(seed)
    return rng.sample(pool, min(n, len(pool)))


def compute_challenges(stats: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    day_key = now.strftime("%Y-%m-%d")
    # Week starts on the most recent Sunday (or today, if it's Sunday).
    week_start = now - timedelta(days=(now.weekday() + 1) % 7)
    week_key = week_start.strftime("%Y-%m-%d")

    def build(pool, seed, n, period_key):
        out = []
        for cid, title, desc, key, threshold, domain in _pick(pool, seed, n):
            have = int(stats.get(key, 0) or 0)
            out.append({"id": f"{period_key}:{cid}", "title": title,
                        "description": desc, "domain": domain,
                        "unlocked": have >= threshold,
                        "progress": min(have, threshold), "threshold": threshold})
        # Done ones sink to the bottom so the next goal is always on top.
        out.sort(key=lambda c: (c["unlocked"], -(c["progress"] / c["threshold"])))
        return out

    return {"day": day_key, "week_start": week_key,
            "daily": build(DAILY_POOL, "daily:" + day_key, 3, day_key),
            "weekly": build(WEEKLY_POOL, "weekly:" + week_key, 3, "wk" + week_key)}
