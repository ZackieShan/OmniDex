"""Map an aircraft's ICAO 24-bit address to its country of registration.

This is offline (no API needed): ICAO allocates blocks of the 24-bit Mode-S
address space to each country. We return the ISO 3166-1 alpha-2 code (for flag
images) and the country name.

Coverage favors what's seen around the US Northeast (US/Canada heavy) plus all
the major world aviation nations. Unlisted blocks return None (no flag shown).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# (start, end, iso2, name) — inclusive hex ranges as integers.
_RANGES: List[Tuple[int, int, str, str]] = [
    (0x004000, 0x0043FF, "ZW", "Zimbabwe"),
    (0x006000, 0x006FFF, "MZ", "Mozambique"),
    (0x008000, 0x00FFFF, "ZA", "South Africa"),
    (0x010000, 0x017FFF, "EG", "Egypt"),
    (0x018000, 0x01FFFF, "LY", "Libya"),
    (0x020000, 0x027FFF, "MA", "Morocco"),
    (0x028000, 0x02FFFF, "TN", "Tunisia"),
    (0x034000, 0x034FFF, "CM", "Cameroon"),
    (0x03E000, 0x03EFFF, "GA", "Gabon"),
    (0x040000, 0x040FFF, "ET", "Ethiopia"),
    (0x044000, 0x044FFF, "GH", "Ghana"),
    (0x04C000, 0x04CFFF, "KE", "Kenya"),
    (0x064000, 0x064FFF, "NG", "Nigeria"),
    (0x068000, 0x068FFF, "UG", "Uganda"),
    (0x06A000, 0x06AFFF, "QA", "Qatar"),
    (0x070000, 0x070FFF, "DZ", "Algeria"),
    (0x078000, 0x078FFF, "AO", "Angola"),
    (0x0A0000, 0x0A7FFF, "MX", "Mexico"),  # partial; see also 0D
    (0x0D0000, 0x0D7FFF, "MX", "Mexico"),
    (0x100000, 0x1FFFFF, "RU", "Russia"),
    (0x201000, 0x2013FF, "NA", "Namibia"),
    (0x300000, 0x33FFFF, "IT", "Italy"),
    (0x340000, 0x37FFFF, "ES", "Spain"),
    (0x380000, 0x3BFFFF, "FR", "France"),
    (0x3C0000, 0x3FFFFF, "DE", "Germany"),
    (0x400000, 0x43FFFF, "GB", "United Kingdom"),
    (0x440000, 0x447FFF, "AT", "Austria"),
    (0x448000, 0x44FFFF, "BE", "Belgium"),
    (0x450000, 0x457FFF, "BG", "Bulgaria"),
    (0x458000, 0x45FFFF, "DK", "Denmark"),
    (0x460000, 0x467FFF, "FI", "Finland"),
    (0x468000, 0x46FFFF, "GR", "Greece"),
    (0x470000, 0x477FFF, "HU", "Hungary"),
    (0x478000, 0x47FFFF, "NO", "Norway"),
    (0x480000, 0x487FFF, "NL", "Netherlands"),
    (0x488000, 0x48FFFF, "PL", "Poland"),
    (0x490000, 0x497FFF, "PT", "Portugal"),
    (0x498000, 0x49FFFF, "CZ", "Czechia"),
    (0x4A0000, 0x4A7FFF, "SE", "Sweden"),
    (0x4A8000, 0x4AFFFF, "CH", "Switzerland"),  # see also 4B0
    (0x4B0000, 0x4B7FFF, "CH", "Switzerland"),
    (0x4B8000, 0x4BFFFF, "TR", "Turkey"),
    (0x4C0000, 0x4C7FFF, "RS", "Serbia"),
    (0x4CA000, 0x4CAFFF, "IE", "Ireland"),
    (0x4CC000, 0x4CCFFF, "IS", "Iceland"),
    (0x500000, 0x5003FF, "SM", "San Marino"),
    (0x501000, 0x5013FF, "EE", "Estonia"),
    (0x508000, 0x50FFFF, "UA", "Ukraine"),
    (0x510000, 0x5103FF, "LV", "Latvia"),
    (0x511000, 0x5113FF, "LT", "Lithuania"),
    (0x512000, 0x5123FF, "LU", "Luxembourg"),
    (0x516000, 0x5163FF, "SK", "Slovakia"),
    (0x518000, 0x5183FF, "SI", "Slovenia"),
    (0x51C000, 0x51CFFF, "HR", "Croatia"),
    (0x680000, 0x6803FF, "TH", "Thailand"),  # rough
    (0x700000, 0x700FFF, "AF", "Afghanistan"),
    (0x710000, 0x717FFF, "SA", "Saudi Arabia"),
    (0x718000, 0x71FFFF, "KR", "South Korea"),
    (0x720000, 0x727FFF, "KP", "North Korea"),
    (0x728000, 0x72FFFF, "IQ", "Iraq"),
    (0x730000, 0x737FFF, "IR", "Iran"),
    (0x738000, 0x73FFFF, "IL", "Israel"),
    (0x740000, 0x747FFF, "JO", "Jordan"),
    (0x760000, 0x767FFF, "PK", "Pakistan"),
    (0x768000, 0x76FFFF, "SG", "Singapore"),  # rough
    (0x770000, 0x777FFF, "LK", "Sri Lanka"),
    (0x780000, 0x7BFFFF, "CN", "China"),
    (0x7C0000, 0x7FFFFF, "AU", "Australia"),
    (0x800000, 0x83FFFF, "IN", "India"),
    (0x840000, 0x87FFFF, "JP", "Japan"),
    (0x880000, 0x887FFF, "TH", "Thailand"),
    (0x888000, 0x88FFFF, "VN", "Vietnam"),
    (0x894000, 0x894FFF, "HK", "Hong Kong"),
    (0x896000, 0x896FFF, "AE", "United Arab Emirates"),
    (0x898000, 0x898FFF, "TW", "Taiwan"),
    (0x8A0000, 0x8A7FFF, "ID", "Indonesia"),
    (0x900000, 0x9003FF, "MH", "Marshall Islands"),
    (0xA00000, 0xAFFFFF, "US", "United States"),
    (0xC00000, 0xC3FFFF, "CA", "Canada"),
    (0xC80000, 0xC87FFF, "NZ", "New Zealand"),
    (0xE00000, 0xE3FFFF, "AR", "Argentina"),
    (0xE40000, 0xE7FFFF, "BR", "Brazil"),
    (0xE80000, 0xE80FFF, "CL", "Chile"),
    (0xE84000, 0xE84FFF, "CO", "Colombia"),
    (0xE94000, 0xE94FFF, "PE", "Peru"),
]

_cache: Dict[str, Optional[Dict[str, str]]] = {}


def country_for_hex(hex_code: Optional[str]) -> Optional[Dict[str, str]]:
    """Return {'iso2': 'US', 'name': 'United States'} for an ICAO hex, or None."""
    if not hex_code:
        return None
    key = hex_code.upper().strip()
    if key in _cache:
        return _cache[key]
    try:
        n = int(key, 16)
    except ValueError:
        _cache[key] = None
        return None
    result = None
    for start, end, iso2, name in _RANGES:
        if start <= n <= end:
            result = {"iso2": iso2, "name": name}
            break
    _cache[key] = result
    return result


# ISO-2 -> country name, built from the allocation table above plus a few
# maritime flag states that don't appear in the aircraft ranges.
_ISO2_NAME = {iso2: name for (_s, _e, iso2, name) in _RANGES}
_ISO2_NAME.update({
    "MH": "Marshall Islands", "PA": "Panama", "LR": "Liberia", "BS": "Bahamas",
    "MT": "Malta", "CY": "Cyprus", "SG": "Singapore", "HK": "Hong Kong",
    "VC": "St Vincent & Grenadines", "AG": "Antigua & Barbuda", "KY": "Cayman Islands",
    "BM": "Bermuda", "VG": "British Virgin Islands", "GI": "Gibraltar", "CW": "Curaçao",
    "TC": "Turks & Caicos", "KN": "St Kitts & Nevis", "FO": "Faroe Islands",
    "CK": "Cook Islands", "PT": "Portugal", "GB": "United Kingdom", "US": "United States",
})


def country_name(iso2: Optional[str]) -> Optional[str]:
    """Full country name for an ISO-2 code (e.g. 'MH' -> 'Marshall Islands')."""
    if not iso2:
        return None
    return _ISO2_NAME.get(str(iso2).upper())
