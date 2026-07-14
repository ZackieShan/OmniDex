"""AtmoDex — astronomy / sky-watching for the kiosk.

The core (moon phase, sun & twilight times, visible planets, meteor showers,
seasonal sky tips, viewing quality) is computed locally with standard formulas —
no API, no rate limits, works offline. Two optional extras (NASA APOD photo and
ISS pass predictions) hit the network and are cached for hours.

Math references: low-precision solar/planetary positions (Paul Schlyter) and the
standard sunrise equation. Accuracy is "good enough to point at the sky," not
arc-second ephemeris.
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from sgp4.api import Satrec, jday  # pip install sgp4 / sudo apt install python3-sgp4
except ImportError:  # pragma: no cover - optional dependency
    Satrec = None
    jday = None

logger = logging.getLogger(__name__)

# --- trig in degrees (Schlyter's formulas are all in degrees) ----------------
def _sin(d): return math.sin(math.radians(d))
def _cos(d): return math.cos(math.radians(d))
def _atan2(y, x): return math.degrees(math.atan2(y, x))
def _rev(x): return x % 360.0
def _rev180(x): return ((x + 180.0) % 360.0) - 180.0


def _jd(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    day = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def _jd_to_epoch(jd: float) -> float:
    return (jd - 2440587.5) * 86400.0


# ===========================================================================
# Moon phase
# ===========================================================================
_SYNODIC = 29.530588853
_KNOWN_NEW_MOON_JD = 2451550.1  # 2000-01-06 18:14 UTC

_MOON_PHASES = [
    ("New Moon", "new"), ("Waxing Crescent", "wax-cres"),
    ("First Quarter", "first-q"), ("Waxing Gibbous", "wax-gib"),
    ("Full Moon", "full"), ("Waning Gibbous", "wan-gib"),
    ("Last Quarter", "last-q"), ("Waning Crescent", "wan-cres"),
]


def moon_phase(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    age = (_jd(now) - _KNOWN_NEW_MOON_JD) % _SYNODIC
    illum = round((1 - math.cos(2 * math.pi * age / _SYNODIC)) / 2 * 100)
    # 8 phases centered on the canonical points
    idx = int((age / _SYNODIC) * 8 + 0.5) % 8
    name, icon = _MOON_PHASES[idx]
    return {
        "phase": name,
        "icon": icon,
        "illumination": illum,
        "age_days": round(age, 1),
    }


# ===========================================================================
# Sun & twilight (sunrise equation)
# ===========================================================================
def _sun_event(lat: float, lon: float, when: datetime, h0: float):
    """Return (rise_epoch, set_epoch, transit_epoch) for altitude h0 degrees.
    rise/set are None during polar day/night."""
    n = round(_jd(when) - 2451545.0 + 0.0008)
    # In the sunrise equation lw is the observer's longitude with EAST negative,
    # i.e. just `lon` (a west longitude like -73.1 stays negative). Using -lon
    # here flipped solar noon by ~2*lon/360 (~9.75h) and made sunrise read ~14h
    # late (e.g. 19:38 instead of 05:23).
    lw = lon
    jstar = n - lw / 360.0
    M = _rev(357.5291 + 0.98560028 * jstar)
    C = 1.9148 * _sin(M) + 0.0200 * _sin(2 * M) + 0.0003 * _sin(3 * M)
    lam = _rev(M + C + 180 + 102.9372)
    jtransit = 2451545.0 + jstar + 0.0053 * _sin(M) - 0.0069 * _sin(2 * lam)
    decl = math.degrees(math.asin(_sin(lam) * _sin(23.44)))
    try:
        cos_w = (_sin(h0) - _sin(lat) * _sin(decl)) / (_cos(lat) * _cos(decl))
    except ZeroDivisionError:
        return (None, None, _jd_to_epoch(jtransit))
    if cos_w < -1 or cos_w > 1:
        return (None, None, _jd_to_epoch(jtransit))
    w0 = math.degrees(math.acos(cos_w))
    return (_jd_to_epoch(jtransit - w0 / 360.0),
            _jd_to_epoch(jtransit + w0 / 360.0),
            _jd_to_epoch(jtransit))


def sun_times(lat: float, lon: float, when: Optional[datetime] = None) -> Dict[str, Any]:
    when = when or datetime.now(timezone.utc)
    rise, sset, transit = _sun_event(lat, lon, when, -0.833)
    dawn, dusk, _ = _sun_event(lat, lon, when, -6.0)   # civil twilight
    now_e = when.timestamp()
    is_dark = False
    if dusk and dawn:
        # dark = after this evening's civil dusk OR before this morning's dawn
        is_dark = now_e >= dusk or now_e <= dawn
    return {
        "sunrise": rise, "sunset": sset, "solar_noon": transit,
        "civil_dawn": dawn, "civil_dusk": dusk, "is_dark": is_dark,
    }


# ===========================================================================
# Visible planets (low-precision; elongation-from-sun based)
# ===========================================================================
def _day_number(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    d = (367 * dt.year
         - 7 * (dt.year + (dt.month + 9) // 12) // 4
         + 275 * dt.month // 9 + dt.day - 730530)
    return d + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24.0


_PLANET_MAG = {"Mercury": -0.4, "Venus": -4.1, "Mars": 0.7,
               "Jupiter": -2.2, "Saturn": 0.6}


def _planet_elements(name: str, d: float):
    """(N, i, w, a, e, M) orbital elements for date d (Schlyter)."""
    el = {
        "Mercury": (48.3313 + 3.24587e-5 * d, 7.0047 + 5.00e-8 * d,
                    29.1241 + 1.01444e-5 * d, 0.387098, 0.205635 + 5.59e-10 * d,
                    168.6562 + 4.0923344368 * d),
        "Venus": (76.6799 + 2.46590e-5 * d, 3.3946 + 2.75e-8 * d,
                  54.8910 + 1.38374e-5 * d, 0.723330, 0.006773 - 1.302e-9 * d,
                  48.0052 + 1.6021302244 * d),
        "Mars": (49.5574 + 2.11081e-5 * d, 1.8497 - 1.78e-8 * d,
                 286.5016 + 2.92961e-5 * d, 1.523688, 0.093405 + 2.516e-9 * d,
                 18.6021 + 0.5240207766 * d),
        "Jupiter": (100.4542 + 2.76854e-5 * d, 1.3030 - 1.557e-7 * d,
                    273.8777 + 1.64505e-5 * d, 5.20256, 0.048498 + 4.469e-9 * d,
                    19.8950 + 0.0830853001 * d),
        "Saturn": (113.6634 + 2.38980e-5 * d, 2.4886 - 1.081e-7 * d,
                   339.3939 + 2.97661e-5 * d, 9.55475, 0.055546 - 9.499e-9 * d,
                   316.9670 + 0.0334442282 * d),
    }
    return el[name]


def _geocentric_lon(name: str, d: float, xs: float, ys: float) -> float:
    """Geocentric ecliptic longitude (deg) of a planet."""
    N, i, w, a, e, M = _planet_elements(name, d)
    N, i, w, M = _rev(N), i, _rev(w), _rev(M)
    E = M + (180 / math.pi) * e * _sin(M) * (1 + e * _cos(M))
    for _ in range(5):  # refine eccentric anomaly
        E = E - (E - (180 / math.pi) * e * _sin(E) - M) / (1 - e * _cos(E))
    xv = a * (_cos(E) - e)
    yv = a * math.sqrt(1 - e * e) * _sin(E)
    v = _atan2(yv, xv)
    r = math.hypot(xv, yv)
    # heliocentric ecliptic rectangular
    xh = r * (_cos(N) * _cos(v + w) - _sin(N) * _sin(v + w) * _cos(i))
    yh = r * (_sin(N) * _cos(v + w) + _cos(N) * _sin(v + w) * _cos(i))
    # geocentric (add sun's rectangular geocentric coords)
    return _rev(_atan2(yh + ys, xh + xs))


def visible_planets(lat: float, lon: float, when: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Naked-eye planets and whether they're an evening or morning object.
    Direction is approximate (low in the W after sunset / E before sunrise)."""
    when = when or datetime.now(timezone.utc)
    d = _day_number(when)
    # Sun
    ws = _rev(282.9404 + 4.70935e-5 * d)
    es = 0.016709 - 1.151e-9 * d
    Ms = _rev(356.0470 + 0.9856002585 * d)
    E = Ms + (180 / math.pi) * es * _sin(Ms) * (1 + es * _cos(Ms))
    xv = _cos(E) - es
    yv = math.sqrt(1 - es * es) * _sin(E)
    lonsun = _rev(_atan2(yv, xv) + ws)
    rs = math.hypot(xv, yv)
    xs = rs * _cos(lonsun)
    ys = rs * _sin(lonsun)

    out = []
    for name in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        try:
            plon = _geocentric_lon(name, d, xs, ys)
        except Exception as e:
            logger.debug("planet %s calc failed: %s", name, e)
            continue
        elong = _rev180(plon - lonsun)   # + = east of sun (evening), - = morning
        if abs(elong) < 12:
            continue                     # lost in the sun's glare
        evening = elong > 0
        out.append({
            "name": name,
            "magnitude": _PLANET_MAG.get(name),
            "when_visible": "Evening" if evening else "Morning",
            "direction": "Western sky after sunset" if evening else "Eastern sky before sunrise",
            "elongation": round(elong),
        })
    # Brightest first
    out.sort(key=lambda p: (p["magnitude"] if p["magnitude"] is not None else 99))
    return out


# ===========================================================================
# Moon position, conjunctions, solunar (fishing), light pollution
# ===========================================================================
def _sun_lon(d: float) -> Dict[str, float]:
    w = _rev(282.9404 + 4.70935e-5 * d)
    e = 0.016709 - 1.151e-9 * d
    M = _rev(356.0470 + 0.9856002585 * d)
    E = M + (180 / math.pi) * e * _sin(M) * (1 + e * _cos(M))
    xv = _cos(E) - e
    yv = math.sqrt(1 - e * e) * _sin(E)
    lon = _rev(_atan2(yv, xv) + w)
    r = math.hypot(xv, yv)
    return {"lon": lon, "M": M, "Ls": _rev(w + M), "xs": r * _cos(lon), "ys": r * _sin(lon)}


def _moon_position(d: float) -> Dict[str, float]:
    """Geocentric Moon: ecliptic lon/lat + equatorial RA/Dec (deg), Schlyter with
    the main perturbation terms (good to ~0.5°)."""
    N = _rev(125.1228 - 0.0529538083 * d)
    i, a, e = 5.1454, 60.2666, 0.054900
    w = _rev(318.0634 + 0.1643573223 * d)
    M = _rev(115.3654 + 13.0649929509 * d)
    E = M + (180 / math.pi) * e * _sin(M) * (1 + e * _cos(M))
    for _ in range(5):
        E = E - (E - (180 / math.pi) * e * _sin(E) - M) / (1 - e * _cos(E))
    xv = a * (_cos(E) - e)
    yv = a * math.sqrt(1 - e * e) * _sin(E)
    v = _atan2(yv, xv)
    r = math.hypot(xv, yv)
    xh = r * (_cos(N) * _cos(v + w) - _sin(N) * _sin(v + w) * _cos(i))
    yh = r * (_sin(N) * _cos(v + w) + _cos(N) * _sin(v + w) * _cos(i))
    zh = r * (_sin(v + w) * _sin(i))
    lon = _rev(_atan2(yh, xh))
    lat = _atan2(zh, math.hypot(xh, yh))
    # perturbations (need sun + moon mean elements)
    sun = _sun_lon(d)
    Ls, Ms = sun["Ls"], sun["M"]
    Lm = _rev(N + w + M)
    D = _rev(Lm - Ls)
    F = _rev(Lm - N)
    lon += (-1.274 * _sin(M - 2 * D) + 0.658 * _sin(2 * D) - 0.186 * _sin(Ms)
            - 0.059 * _sin(2 * M - 2 * D) - 0.057 * _sin(M - 2 * D + Ms)
            + 0.053 * _sin(M + 2 * D) + 0.046 * _sin(2 * D - Ms)
            + 0.041 * _sin(M - Ms) - 0.035 * _sin(D) - 0.031 * _sin(M + Ms)
            - 0.015 * _sin(2 * F - 2 * D) + 0.011 * _sin(M - 4 * D))
    lat += (-0.173 * _sin(F - 2 * D) - 0.055 * _sin(M - F - 2 * D)
            - 0.046 * _sin(M + F - 2 * D) + 0.033 * _sin(F + 2 * D)
            + 0.017 * _sin(2 * M + F))
    lon = _rev(lon)
    ecl = 23.4393 - 3.563e-7 * d
    yg, zg = _sin(lon) * _cos(lat), _sin(lat)
    ye = yg * _cos(ecl) - zg * _sin(ecl)
    ze = yg * _sin(ecl) + zg * _cos(ecl)
    return {"lon": lon, "lat": lat,
            "ra": _rev(_atan2(ye, _cos(lon) * _cos(lat))),
            "dec": _atan2(ze, math.hypot(_cos(lon) * _cos(lat), ye))}


def conjunctions(when: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Close pairings (within ~6° of ecliptic longitude) of the Moon and naked-eye
    planets — 'the Moon meets Jupiter tonight'. Longitude-only, so approximate."""
    when = when or datetime.now(timezone.utc)
    d = _day_number(when)
    sun = _sun_lon(d)
    bodies = {"Moon": _moon_position(d)["lon"]}
    for name in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        try:
            bodies[name] = _geocentric_lon(name, d, sun["xs"], sun["ys"])
        except Exception:
            pass
    names = list(bodies)
    out = []
    for x in range(len(names)):
        for y in range(x + 1, len(names)):
            a, b = names[x], names[y]
            sep = abs(_rev180(bodies[a] - bodies[b]))
            if sep <= 6:
                out.append({"a": a, "b": b, "separation": round(sep, 1)})
    out.sort(key=lambda c: c["separation"])
    return out


def solunar(lat: float, lon: float, when: Optional[datetime] = None) -> Dict[str, Any]:
    """Major solunar feeding/fishing periods (Moon overhead & underfoot) plus a
    phase-based quality. Times are approximate."""
    when = when or datetime.now(timezone.utc)
    d = _day_number(when)
    ra = _moon_position(d)["ra"]
    gmst = _rev(280.46061837 + 360.98564736629 * (_jd(when) - 2451545.0))
    ha = _rev180(_rev(gmst + lon) - ra)        # 0 = Moon on the meridian (overhead)
    rate = 14.492                               # deg/hr the Moon's hour angle advances
    now_e = when.timestamp()

    def _next(target_ha):
        return now_e + (((target_ha - ha) % 360) / rate) * 3600

    majors = sorted([
        {"type": "Moon overhead", "time": _next(0)},
        {"type": "Moon underfoot", "time": _next(180)},
    ], key=lambda m: m["time"])

    illum = moon_phase(when).get("illumination", 0)
    closeness = min(illum, 100 - illum)         # 0 at new/full (best), 50 at quarter
    quality = ("Excellent" if illum >= 95 or illum <= 5 else
               "Good" if closeness <= 20 else "Fair" if closeness <= 35 else "Poor")
    return {"quality": quality, "major": majors,
            "note": "Major feeding periods (~2 h windows). Fishing is best around new & full moon."}


def light_pollution() -> Dict[str, Any]:
    """Static light-pollution context for the home shoreline (suburban)."""
    return {
        "bortle": 6,
        "label": "Bright suburban (Bortle ~6)",
        "tip": "Face south & east over Long Island Sound — away from Bridgeport's glow to the "
               "northwest. Give your eyes 15–20 minutes in the dark to adapt.",
    }


# --- Zodiac (computed locally from Sun/Moon ecliptic longitude — for fun) -----
_ZODIAC = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
           "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
_ZODIAC_BLURB = {
    "Aries": "Bold energy in the air — start something.",
    "Taurus": "A grounded, steady stretch — enjoy the simple things.",
    "Gemini": "Curious and chatty — good for ideas and connections.",
    "Cancer": "Feelings run close to the surface — be kind to yourself.",
    "Leo": "Time to shine — confidence and warmth abound.",
    "Virgo": "Details click into place — tidy up and refine.",
    "Libra": "Seek balance and a little beauty today.",
    "Scorpio": "Intense and focused — trust your gut.",
    "Sagittarius": "Adventure calls — aim high and explore.",
    "Capricorn": "Heads-down and ambitious — the long game pays.",
    "Aquarius": "Think different — original ideas spark.",
    "Pisces": "Dreamy and intuitive — let imagination wander.",
}


def _sign(lon: float) -> str:
    return _ZODIAC[int(lon // 30) % 12]


def zodiac(when: Optional[datetime] = None) -> Dict[str, Any]:
    """The zodiac sign the Sun and Moon are currently in (tropical)."""
    when = when or datetime.now(timezone.utc)
    d = _day_number(when)
    try:
        ss = _sign(_sun_lon(d)["lon"])
        ms = _sign(_moon_position(d)["lon"])
    except Exception:
        return {}
    return {"sun_sign": ss, "moon_sign": ms, "blurb": _ZODIAC_BLURB.get(ss, "")}


# ===========================================================================
# Meteor showers (annual calendar)
# ===========================================================================
# (name, start "mm-dd", peak "mm-dd", end "mm-dd", ZHR, parent body)
_METEOR_SHOWERS = [
    ("Quadrantids", "12-28", "01-04", "01-12", 120, "asteroid 2003 EH1"),
    ("Lyrids", "04-16", "04-22", "04-25", 18, "Comet Thatcher"),
    ("Eta Aquariids", "04-19", "05-06", "05-28", 50, "Halley's Comet"),
    ("Delta Aquariids", "07-12", "07-30", "08-23", 25, "Comet 96P/Machholz"),
    ("Perseids", "07-17", "08-12", "08-24", 100, "Comet Swift-Tuttle"),
    ("Draconids", "10-06", "10-08", "10-10", 10, "Comet Giacobini-Zinner"),
    ("Orionids", "10-02", "10-21", "11-07", 20, "Halley's Comet"),
    ("Southern Taurids", "09-23", "11-05", "12-08", 7, "Comet Encke"),
    ("Leonids", "11-06", "11-17", "11-30", 15, "Comet Tempel-Tuttle"),
    ("Geminids", "12-04", "12-14", "12-17", 120, "asteroid 3200 Phaethon"),
    ("Ursids", "12-17", "12-22", "12-26", 10, "Comet Tuttle"),
]


def _md_to_doy(mmdd: str, year: int) -> int:
    m, d = int(mmdd[:2]), int(mmdd[3:])
    return datetime(year, m, d).timetuple().tm_yday


def meteor_showers(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    doy = now.timetuple().tm_yday
    year = now.year
    active, upcoming = [], []
    for name, start, peak, end, zhr, parent in _METEOR_SHOWERS:
        s, p, e = (_md_to_doy(start, year), _md_to_doy(peak, year), _md_to_doy(end, year))
        wraps = s > e            # crosses new year (Quadrantids)
        in_window = (doy >= s or doy <= e) if wraps else (s <= doy <= e)
        rec = {"name": name, "peak": peak, "zhr": zhr, "parent": parent}
        if in_window:
            peaking = abs(doy - p) <= 1 or (wraps and abs(doy - p) >= 363)
            rec["peaking"] = peaking
            active.append(rec)
        else:
            days = p - doy
            if 0 < days <= 30:
                rec["days_away"] = days
                upcoming.append(rec)
    upcoming.sort(key=lambda r: r.get("days_away", 999))
    return {"active": active, "next": upcoming[0] if upcoming else None}


# ===========================================================================
# Seasonal "look up tonight" tips (~41 N evening sky)
# ===========================================================================
_SKY_TIPS = {
    1: ["Orion blazes in the south — find the three stars of his Belt.",
        "Follow Orion's Belt down-left to Sirius, the brightest star.",
        "The Big Dipper is climbing in the northeast."],
    2: ["Orion and his bright winter companions dominate the evening south.",
        "Spot the Pleiades (Seven Sisters) high in the west.",
        "Gemini's twins Castor and Pollux ride high overhead."],
    3: ["Leo the Lion rises in the east after dark — look for the 'Sickle'.",
        "The Big Dipper is high in the northeast; use it to find Polaris.",
        "Winter's Orion is sinking into the western evening sky."],
    4: ["The Big Dipper rides high overhead — follow its handle to Arcturus.",
        "Leo is well-placed in the south.",
        "Look east late for the rising Summer Triangle."],
    5: ["Arc to Arcturus and 'speed on to Spica' from the Dipper's handle.",
        "Leo and Virgo fill the southern sky.",
        "The Big Dipper is overhead — it's circumpolar from Connecticut, always up."],
    6: ["The Summer Triangle (Vega, Deneb, Altair) climbs the eastern sky.",
        "Hercules is overhead — hunt for the M13 globular cluster with binoculars.",
        "Scorpius and red Antares hug the southern horizon."],
    7: ["The Milky Way arches overhead on dark nights — get away from lights.",
        "Scorpius and Sagittarius (the 'Teapot') sit low in the south.",
        "The Summer Triangle dominates the eastern evening sky."],
    8: ["Peak Perseid season — watch the northeast after midnight.",
        "The Summer Triangle is nearly overhead.",
        "The Milky Way runs from Cassiopeia down to Sagittarius."],
    9: ["The Summer Triangle is high overhead at dusk.",
        "Cassiopeia's 'W' climbs in the northeast.",
        "Look east late for the Great Square of Pegasus."],
    10: ["The Great Square of Pegasus rides high in the south.",
         "Find the Andromeda Galaxy (M31) — the farthest thing visible to the naked eye.",
         "Cassiopeia is high in the northeast."],
    11: ["Andromeda and Pegasus dominate the evening sky.",
         "Watch for Leonid meteors mid-month.",
         "The Pleiades rise in the east — winter is coming back."],
    12: ["Orion returns to the eastern evening sky.",
         "Peak Geminid meteors around the 13th-14th — the year's best shower.",
         "The Pleiades and Taurus ride high in the east."],
}


def sky_tonight(now: Optional[datetime] = None) -> List[str]:
    now = now or datetime.now()
    tips = list(_SKY_TIPS.get(now.month, []))
    tips.append("The Big Dipper never sets from Connecticut — look north any clear night.")
    return tips


# Notable comets (reference / periodic returns) for the Sky Guide.
NOTABLE_COMETS = [
    {"name": "1P/Halley", "note": "The most famous comet — returns about every 76 years; next perihelion 2061."},
    {"name": "109P/Swift-Tuttle", "note": "Parent of the Perseid meteors; ~133-year orbit, returns 2126."},
    {"name": "55P/Tempel-Tuttle", "note": "Parent of the Leonids; returns about every 33 years."},
    {"name": "C/1995 O1 (Hale-Bopp)", "note": "The 'Great Comet of 1997' — naked-eye for a record 18 months."},
    {"name": "C/2020 F3 (NEOWISE)", "note": "Stunning naked-eye comet of July 2020; won't return for ~6,800 years."},
    {"name": "12P/Pons-Brooks", "note": "The 'Devil Comet' — periodic, reached naked-eye brightness in 2024."},
    {"name": "C/2023 A3 (Tsuchinshan-ATLAS)", "note": "A bright naked-eye comet that graced skies in autumn 2024."},
]


def notable_comets() -> List[Dict[str, Any]]:
    return list(NOTABLE_COMETS)


# ===========================================================================
# Viewing quality (cloud cover + moonlight)
# ===========================================================================
def viewing_quality(cloud_pct: Optional[float], moon_illum: Optional[float]) -> Dict[str, Any]:
    reasons = []
    score = 100
    if cloud_pct is not None:
        score -= cloud_pct * 0.8
        if cloud_pct >= 70:
            reasons.append("mostly cloudy")
        elif cloud_pct >= 30:
            reasons.append("some clouds")
        else:
            reasons.append("clear skies")
    if moon_illum is not None and moon_illum >= 60:
        score -= (moon_illum - 60) * 0.4
        reasons.append("bright moonlight")
    score = max(0, min(100, round(score)))
    label = ("Excellent" if score >= 80 else "Good" if score >= 60
             else "Fair" if score >= 40 else "Poor")
    return {"score": score, "label": label, "reasons": reasons}


# ===========================================================================
# Optional network extras (cached for hours)
# ===========================================================================
class _TimedCache:
    def __init__(self, ttl):
        self.ttl = ttl
        self._v = None
        self._t = 0.0

    def get(self):
        if self._v is not None and (time.time() - self._t) < self.ttl:
            return self._v
        return None

    def set(self, v):
        self._v, self._t = v, time.time()


class ApodClient:
    """NASA Astronomy Picture of the Day (api.nasa.gov, free key)."""

    def __init__(self, api_key: str, ttl: int = 21600):
        self.api_key = api_key
        self._cache = _TimedCache(ttl)

    def fetch(self) -> Optional[Dict[str, Any]]:
        cached = self._cache.get()
        if cached is not None:
            return cached or None
        result = {}
        try:
            url = "https://api.nasa.gov/planetary/apod?api_key=" + urllib.parse.quote(self.api_key)
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            result = {
                "title": data.get("title"),
                "url": data.get("url"),
                "hdurl": data.get("hdurl"),
                "media_type": data.get("media_type"),
                "explanation": data.get("explanation"),
                "date": data.get("date"),
                "copyright": data.get("copyright"),
            }
        except Exception as e:
            logger.debug("APOD fetch failed: %s", e)
        self._cache.set(result)
        return result or None


def _gmst_rad(jd_ut1: float) -> float:
    """Greenwich Mean Sidereal Time (radians) from a Julian date."""
    t = (jd_ut1 - 2451545.0) / 36525.0
    g = (280.46061837 + 360.98564736629 * (jd_ut1 - 2451545.0)
         + 0.000387933 * t * t - t * t * t / 38710000.0)
    return math.radians(g % 360.0)


def _observer_ecef_km(lat: float, lon: float, alt_m: float = 0.0):
    """WGS84 geodetic -> ECEF, in km."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    la, lo = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
    x = (n + alt_m) * math.cos(la) * math.cos(lo)
    y = (n + alt_m) * math.cos(la) * math.sin(lo)
    z = (n * (1 - e2) + alt_m) * math.sin(la)
    return (x / 1000.0, y / 1000.0, z / 1000.0)


class TlePassPredictor:
    """Local satellite pass prediction via SGP4 + free CelesTrak TLEs.

    No paid API: TLEs are fetched from CelesTrak (cached 12h) and propagated on
    the Pi to find when a satellite climbs above `min_elevation`. Returns passes
    as {start, peak, end, max_elevation}. Gracefully returns nothing if the sgp4
    package isn't installed.
    """

    def __init__(self, lat: float, lon: float, alt_m: float = 30.0,
                 min_elevation: int = 15):
        self.lat, self.lon, self.alt_m = lat, lon, alt_m
        self.min_elevation = min_elevation
        self._obs = _observer_ecef_km(lat, lon, alt_m)
        self._tle: Dict[int, _TimedCache] = {}
        self._passes: Dict[int, _TimedCache] = {}

    def _get_tle(self, norad: int):
        cache = self._tle.setdefault(int(norad), _TimedCache(43200))  # 12h
        cached = cache.get()
        if cached is not None:
            return cached or None
        tle = None
        try:
            url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={int(norad)}&FORMAT=TLE"
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                lines = [ln.strip() for ln in resp.read().decode().splitlines() if ln.strip()]
            l1 = next((ln for ln in lines if ln.startswith("1 ")), None)
            l2 = next((ln for ln in lines if ln.startswith("2 ")), None)
            if l1 and l2:
                tle = (l1, l2)
        except Exception as e:
            logger.debug("TLE fetch failed for %s: %s", norad, e)
        cache.set(tle or ())
        return tle

    def _ecef(self, sat, when: datetime):
        """SGP4 -> ECEF position (km) + velocity magnitude (km/s)."""
        jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                      when.second + when.microsecond / 1e6)
        err, r, v = sat.sgp4(jd, fr)   # km, TEME frame
        if err != 0:
            return None
        g = _gmst_rad(jd + fr)
        ex = r[0] * math.cos(g) + r[1] * math.sin(g)
        ey = -r[0] * math.sin(g) + r[1] * math.cos(g)
        ez = r[2]
        speed = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (ex, ey, ez, speed)

    def _look(self, sat, when: datetime):
        """(elevation, azimuth) degrees of the satellite from the observer."""
        ec = self._ecef(sat, when)
        if ec is None:
            return (None, None)
        ex, ey, ez, _ = ec
        dx, dy, dz = ex - self._obs[0], ey - self._obs[1], ez - self._obs[2]
        la, lo = math.radians(self.lat), math.radians(self.lon)
        east = -math.sin(lo) * dx + math.cos(lo) * dy
        north = (-math.sin(la) * math.cos(lo) * dx - math.sin(la) * math.sin(lo) * dy
                 + math.cos(la) * dz)
        up = (math.cos(la) * math.cos(lo) * dx + math.cos(la) * math.sin(lo) * dy
              + math.sin(la) * dz)
        rng = math.sqrt(dx * dx + dy * dy + dz * dz)
        if rng == 0:
            return (None, None)
        el = math.degrees(math.asin(max(-1.0, min(1.0, up / rng))))
        az = math.degrees(math.atan2(east, north)) % 360
        return (el, az)

    def _subpoint(self, sat, when: datetime):
        """Sub-satellite point: (lat, lon, altitude_km, speed_kms)."""
        ec = self._ecef(sat, when)
        if ec is None:
            return None
        ex, ey, ez, speed = ec
        rmag = math.sqrt(ex * ex + ey * ey + ez * ez)
        lat = math.degrees(math.atan2(ez, math.hypot(ex, ey)))   # geocentric (~0.2°)
        lon = math.degrees(math.atan2(ey, ex))
        return (lat, lon, rmag - 6371.0, speed)

    def position(self, norad_id: int) -> Optional[Dict[str, Any]]:
        """Where the satellite is *right now*: sub-point, altitude, your local
        look angles, whether it's above your horizon, and a ~90-min ground track."""
        if Satrec is None:
            return None
        tle = self._get_tle(norad_id)
        if not tle:
            return None
        try:
            sat = Satrec.twoline2rv(tle[0], tle[1])
            now = datetime.now(timezone.utc)
            sub = self._subpoint(sat, now)
            if not sub:
                return None
            lat, lon, alt, speed = sub
            el, az = self._look(sat, now)
            track = []
            for i in range(0, 95, 3):
                s = self._subpoint(sat, now + timedelta(minutes=i))
                if s:
                    track.append([round(s[0], 2), round(s[1], 2)])
            return {
                "lat": round(lat, 2), "lon": round(lon, 2), "alt_km": round(alt),
                "velocity_kms": round(speed, 2),
                "elevation": round(el) if el is not None else None,
                "azimuth": round(az) if az is not None else None,
                "overhead": bool(el is not None and el > 0),
                "track": track,
            }
        except Exception as e:
            logger.debug("position calc failed for %s: %s", norad_id, e)
            return None

    def fetch(self, norad_id: int) -> Optional[Dict[str, Any]]:
        """{'norad_id', 'passes': [{start, peak, end, max_elevation}]} for ~24h."""
        if Satrec is None:
            return {"norad_id": int(norad_id), "passes": [], "engine": "sgp4-missing"}
        cache = self._passes.setdefault(int(norad_id), _TimedCache(3600))  # 1h
        cached = cache.get()
        if cached is not None:
            return cached or None
        result = {"norad_id": int(norad_id), "passes": []}
        tle = self._get_tle(norad_id)
        if tle:
            try:
                sat = Satrec.twoline2rv(tle[0], tle[1])
                now = datetime.now(timezone.utc)
                passes, rise, peak_el, peak_t = [], None, -90.0, None
                for i in range(0, 24 * 60, 1):       # 1-minute steps over 24h
                    t = now + timedelta(minutes=i)
                    el = self._look(sat, t)[0]
                    if el is None:
                        continue
                    if el >= self.min_elevation:
                        if rise is None:
                            rise, peak_el, peak_t = t, el, t
                        elif el > peak_el:
                            peak_el, peak_t = el, t
                    elif rise is not None:
                        passes.append({"start": rise.timestamp(), "peak": peak_t.timestamp(),
                                       "end": t.timestamp(), "max_elevation": round(peak_el)})
                        rise, peak_el = None, -90.0
                        if len(passes) >= 4:
                            break
                result["passes"] = passes
            except Exception as e:
                logger.debug("pass calc failed for %s: %s", norad_id, e)
        cache.set(result)
        return result


class NearMissClient:
    """Recent/estimated satellite conjunctions ('near misses') by NORAD id, via
    RapidAPI. Schema is parsed defensively; returns a best-effort list."""

    HOST = "satellite-estimated-daily-near-misses.p.rapidapi.com"

    def __init__(self, rapidapi_key: str, ttl: int = 43200):
        self.key = rapidapi_key
        self.ttl = ttl
        self._caches: Dict[int, _TimedCache] = {}

    def fetch(self, norad_id: int) -> List[Dict[str, Any]]:
        cache = self._caches.setdefault(int(norad_id), _TimedCache(self.ttl))
        cached = cache.get()
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        try:
            url = f"https://{self.HOST}/norad-id/{int(norad_id)}"
            req = urllib.request.Request(url, headers={
                "x-rapidapi-host": self.HOST, "x-rapidapi-key": self.key,
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
            items = data if isinstance(data, list) else (
                data.get("data") or data.get("results") or data.get("conjunctions") or [])
            if isinstance(items, list):
                for it in items[:5]:
                    if not isinstance(it, dict):
                        continue
                    out.append({
                        "object": (it.get("secondaryObject") or it.get("object") or it.get("name")
                                   or it.get("secondary") or "another object"),
                        "distance": (it.get("missDistance") or it.get("distance")
                                     or it.get("minRange") or it.get("range")),
                        "time": (it.get("tca") or it.get("time") or it.get("date") or it.get("timestamp")),
                    })
        except Exception as e:
            logger.debug("near-miss fetch failed for %s: %s", norad_id, e)
        cache.set(out)
        return out


_AURORA_CACHE = _TimedCache(1800)  # 30 min


def aurora_kp() -> Optional[Dict[str, Any]]:
    """Current planetary K-index (geomagnetic activity) from NOAA SWPC (free).
    Higher Kp = aurora reaches lower latitudes. ~Kp 7+ to see it from CT."""
    cached = _AURORA_CACHE.get()
    if cached is not None:
        return cached or None
    result = {}
    try:
        url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
        req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.load(resp)
        # rows[0] is a header; last row is the latest reading.
        if isinstance(rows, list) and len(rows) > 1:
            kp = float(rows[-1][1])
            if kp >= 7:
                outlook = "Aurora possible even from Connecticut tonight — look north!"
            elif kp >= 5:
                outlook = "Geomagnetic storm — aurora possible far to the north."
            else:
                outlook = "Quiet — no aurora expected at this latitude."
            result = {"kp": round(kp, 1), "outlook": outlook,
                      "storm": kp >= 5, "time": rows[-1][0]}
    except Exception as e:
        logger.debug("aurora Kp fetch failed: %s", e)
    _AURORA_CACHE.set(result)
    return result or None


class LaunchClient:
    """Upcoming rocket launches from The Space Devs Launch Library 2 (free, no key).
    Flags East-coast pads (Wallops) that can sometimes be seen from Connecticut."""

    URL = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=12"

    def __init__(self, ttl: int = 21600):
        self._cache = _TimedCache(ttl)

    def fetch(self) -> List[Dict[str, Any]]:
        cached = self._cache.get()
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        try:
            req = urllib.request.Request(self.URL, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
            for r in (data.get("results") or [])[:12]:
                loc = ((r.get("pad") or {}).get("location") or {}).get("name") or ""
                out.append({
                    "name": r.get("name"),
                    "net": r.get("net"),  # ISO 8601 UTC
                    "provider": (r.get("launch_service_provider") or {}).get("name") or "",
                    "location": loc,
                    "visible_from_ct": any(k in loc for k in ("Wallops", "Mid-Atlantic", "Virginia")),
                })
        except Exception as e:
            logger.debug("launches fetch failed: %s", e)
        self._cache.set(out)
        return out


class AsteroidClient:
    """Near-Earth asteroids this week from NASA NeoWs (free, uses the NASA key)."""

    def __init__(self, nasa_key: str, ttl: int = 21600):
        self.key = nasa_key
        self._cache = _TimedCache(ttl)

    def fetch(self) -> List[Dict[str, Any]]:
        cached = self._cache.get()
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        try:
            today = datetime.now(timezone.utc).date()
            start = today.isoformat()
            end = (today + timedelta(days=6)).isoformat()   # NeoWs max 7-day window
            url = (f"https://api.nasa.gov/neo/rest/v1/feed?start_date={start}"
                   f"&end_date={end}&api_key={urllib.parse.quote(self.key)}")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
            for _day, lst in (data.get("near_earth_objects") or {}).items():
                for n in lst:
                    cad = n.get("close_approach_data") or []
                    ca = cad[0] if cad else {}
                    miss = ca.get("miss_distance") or {}
                    vel = ca.get("relative_velocity") or {}
                    dia = ((n.get("estimated_diameter") or {}).get("meters") or {})
                    out.append({
                        "name": n.get("name", "").replace("(", "").replace(")", ""),
                        "hazardous": n.get("is_potentially_hazardous_asteroid"),
                        "diameter_m": round(dia.get("estimated_diameter_max") or 0),
                        "miss_lunar": round(float(miss.get("lunar")), 1) if miss.get("lunar") else None,
                        "velocity_kms": round(float(vel.get("kilometers_per_second")), 1) if vel.get("kilometers_per_second") else None,
                        "date": ca.get("close_approach_date"),
                    })
            out.sort(key=lambda a: a["miss_lunar"] if a.get("miss_lunar") is not None else 9999)
            out = out[:10]
        except Exception as e:
            logger.debug("NeoWs asteroid fetch failed: %s", e)
        self._cache.set(out)
        return out


def sky_report(lat: float, lon: float, cloud_pct: Optional[float] = None) -> Dict[str, Any]:
    """The whole locally-computed sky snapshot for AtmoDex."""
    now = datetime.now(timezone.utc)
    moon = moon_phase(now)
    return {
        "moon": moon,
        "sun": sun_times(lat, lon, now),
        "planets": visible_planets(lat, lon, now),
        "conjunctions": conjunctions(now),
        "meteor_showers": meteor_showers(),
        "sky_tips": sky_tonight(),
        "viewing": viewing_quality(cloud_pct, moon.get("illumination")),
        "aurora": aurora_kp(),
        "solunar": solunar(lat, lon, now),
        "light_pollution": light_pollution(),
        "comets": notable_comets(),
        "zodiac": zodiac(now),
        "generated": now.timestamp(),
    }
