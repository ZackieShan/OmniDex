"""AtmoDex — notable satellites catalog (owner / purpose / type).

AIS/ADS-B style: we keep a small curated catalog of well-known satellites that
pass overhead, with who owns them and what they do. Live pass predictions
for the bright, naked-eye ones come from a pass API; the rest are informational.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# NORAD id -> metadata. naked_eye = realistically spottable by eye from a suburb.
SATELLITE_CATALOG: Dict[int, Dict[str, Any]] = {
    25544: {"name": "ISS (Zarya)", "owner": "NASA · Roscosmos · ESA · JAXA · CSA",
            "country": "International", "purpose": "Crewed research station",
            "type": "Space station", "naked_eye": True,
            "note": "Brightest thing in the night sky after the Moon & Venus — a steady, fast white point."},
    48274: {"name": "Tiangong (CSS)", "owner": "CMSA", "country": "China",
            "purpose": "Crewed space station", "type": "Space station", "naked_eye": True,
            "note": "China's space station — bright and fast, like a dimmer ISS."},
    20580: {"name": "Hubble Space Telescope", "owner": "NASA · ESA", "country": "USA · Europe",
            "purpose": "Optical / UV space telescope", "type": "Telescope", "naked_eye": False,
            "note": "Orbits low (~540 km); faint, occasionally glimpsed from dark sites."},
    25338: {"name": "NOAA-15", "owner": "NOAA", "country": "USA",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False,
            "note": "Beams APT weather imagery you can receive on 137 MHz."},
    28654: {"name": "NOAA-18", "owner": "NOAA", "country": "USA",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    33591: {"name": "NOAA-19", "owner": "NOAA", "country": "USA",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    43013: {"name": "NOAA-20 (JPSS-1)", "owner": "NOAA", "country": "USA",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    25994: {"name": "Terra", "owner": "NASA", "country": "USA",
            "purpose": "Earth-observation (climate/land)", "type": "Earth science", "naked_eye": False, "note": ""},
    27424: {"name": "Aqua", "owner": "NASA", "country": "USA",
            "purpose": "Earth-observation (water cycle)", "type": "Earth science", "naked_eye": False, "note": ""},
    39084: {"name": "Landsat 8", "owner": "NASA · USGS", "country": "USA",
            "purpose": "Land imaging", "type": "Earth imaging", "naked_eye": False, "note": ""},
    49260: {"name": "Landsat 9", "owner": "NASA · USGS", "country": "USA",
            "purpose": "Land imaging", "type": "Earth imaging", "naked_eye": False, "note": ""},
    29499: {"name": "MetOp-A", "owner": "EUMETSAT", "country": "Europe",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    38771: {"name": "MetOp-B", "owner": "EUMETSAT", "country": "Europe",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    43689: {"name": "MetOp-C", "owner": "EUMETSAT", "country": "Europe",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    40069: {"name": "Meteor-M2", "owner": "Roscosmos", "country": "Russia",
            "purpose": "Polar weather satellite", "type": "Weather", "naked_eye": False, "note": ""},
    27386: {"name": "Envisat", "owner": "ESA", "country": "Europe",
            "purpose": "Earth-observation (defunct since 2012)", "type": "Earth science", "naked_eye": False,
            "note": "A bus-sized dead satellite — one of the largest pieces of space junk in orbit."},
    36508: {"name": "CryoSat-2", "owner": "ESA", "country": "Europe",
            "purpose": "Ice-thickness radar altimetry", "type": "Earth science", "naked_eye": False, "note": ""},
    43641: {"name": "ICESat-2", "owner": "NASA", "country": "USA",
            "purpose": "Polar ice / elevation laser altimetry", "type": "Earth science", "naked_eye": False, "note": ""},
}

# Bright ones worth fetching live passes for (limits API calls).
DEFAULT_TRACKED: List[int] = [25544, 48274, 20580]


def get_satellite(norad: int) -> Optional[Dict[str, Any]]:
    return SATELLITE_CATALOG.get(int(norad))


def catalog_list() -> List[Dict[str, Any]]:
    """All catalog entries with their NORAD id, naked-eye ones first."""
    out = []
    for norad, meta in SATELLITE_CATALOG.items():
        out.append({"norad": norad, **meta})
    out.sort(key=lambda s: (not s.get("naked_eye"), s.get("name", "")))
    return out
