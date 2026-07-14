"""SkyDex aircraft classification engine.

Assigns behavioral types based on observed data, not just looked-up specs.
Runs quick classification on each detection and full pattern mining nightly.

Type taxonomy (from the spec):
  Commuter, Trainer, Hopper, Bizjet, Hauler, Rotor,
  Voyager, Sentinel, Medevac, Heavy
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Military ICAO hex allocation ranges
# ---------------------------------------------------------------------------

_MILITARY_RANGES = [
    # United States
    ("ADF7C1", "AFFFFF"),  # USAF
    ("AE0000", "AEFFFF"),  # US military
    # United Kingdom
    ("43C000", "43CFFF"),  # RAF
    # France
    ("3B0000", "3B3FFF"),  # French military
    # Germany
    ("3E0000", "3EFFFF"),  # German military
    # Australia
    ("7CF800", "7CFFFF"),  # RAAF
    # Canada
    ("C20000", "C2FFFF"),  # RCAF
    # NATO / Other
    ("010000", "010FFF"),  # NATO
    ("444000", "446FFF"),  # NATO E-3A
]


def _hex_in_range(hex_code: str) -> bool:
    """Check if hex falls in a military allocation range."""
    try:
        h = int(hex_code, 16)
        for start, end in _MILITARY_RANGES:
            if int(start, 16) <= h <= int(end, 16):
                return True
    except ValueError:
        pass
    return False


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

class Classifier:
    """Assign behavioral types to aircraft based on observed data.

    Usage::

        clf = Classifier()
        types = clf.classify(aircraft_dict, detection_history)
        # returns [{"type": "Rotor", "confidence": 0.95}, ...]
    """

    # Type codes that are definitely certain things
    _ROTOR_TYPES = {"R44", "R66", "B407", "EC35", "EC55", "H135", "H145",
                    "AS50", "B429", "S76", "S92", "UH1", "UH60", "AH64",
                    "CH47", "CH53", "V22", "EC45", "B47G", "EN48", "W3",
                    "B505", "B206", "B222", "B230", "B407", "B412", "B427"}
    _BIZJET_TYPES = {"C25A", "C25B", "C25C", "C56X", "C680", "C68A", "C700",
                     "CL30", "CL35", "CL60", "E135", "E55P", "F2TH", "F900",
                     "FA10", "FA20", "FA50", "FA7X", "G280", "GA5C", "GALX",
                     "GL5T", "GL6T", "GL7T", "GLEX", "GLF4", "GLF5", "GLF6",
                     "HA4T", "LJ25", "LJ35", "LJ45", "LJ60", "LR40", "LR60"}
    _HEAVY_TYPES = {"A332", "A333", "A338", "A339", "A359", "A35K", "A388",
                    "B741", "B742", "B743", "B744", "B748", "B762", "B763",
                    "B764", "B772", "B773", "B77L", "B77W", "B788", "B789",
                    "B78X", "MD11", "IL96", "DC10"}
    _CARGO_OPS = {"FDX", "UPS", "ABX", "ATN", "GTI", "CKS", "DHL", "SWN",
                  "CLX", "NCR", "AWE", "PAC", "BDA", "MRA"}
    # Medevac is matched on airline-style callsign PREFIXES (not N-numbers) and
    # explicit operator keywords — never loose substrings (which tagged
    # training Cessnas as Medevac because e.g. "MED"/"CAL"/"SPR" appear inside
    # ordinary owner names).
    _MEDEVAC_CALLSIGN_PREFIXES = {"LIF", "MET", "STAT", "ANGEL", "MERCY", "HAA",
                                  "HEE", "NTE", "MDF", "MDT"}
    _MIL_CALLSIGN_PATTERNS = {"RCH", "USAF", "NAVY", "ARMY", "MARINE", "TOPCAT",
                              "SNIPR", "VIPR", "COBRA", "CONVOY", "VIP", "SAM",
                              # RAF / NATO / allied air-arm callsigns
                              "ASCOT", "RRR", "COMET", "REACH", "CFC", "CTM",
                              "GAF", "IAM", "NATO", "PAT", "SPAR", "HERKY",
                              "DUKE", "TARTAN", "NOBLE", "VULCAN"}
    # Operator-name keywords that mark an aircraft as military (case-insensitive).
    # "AIR FORCE" / "NAVY" already catch "Royal Air Force", "US Navy", etc.
    _MIL_OPERATOR_KEYWORDS = ("MILITARY", "MILITARE", "AIR FORCE", "AIRFORCE",
                              "FORCE AERIENNE", "ROYAL AIR", "ROYAL NAVY",
                              "NAVY", "NAVAL AIR", "ARMY", "MARINE CORPS",
                              "COAST GUARD", "LUFTWAFFE", "AERONAUTICA",
                              "FUERZA AEREA", "ARMEE DE L", "AIRTANKER",
                              "DRAKEN")

    def classify(
        self,
        aircraft: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Classify a single aircraft. Returns list of {type, confidence} dicts.

        *aircraft* is the enriched aircraft dict with fields like:
          hex, callsign, type_code, operator, altitude, ground_speed,
          distance_miles, category
        *history* is optional list of past detections for pattern analysis.
        """
        types_found: List[Dict[str, Any]] = []

        hex_code = (aircraft.get("hex") or "").upper().strip()
        type_code = (aircraft.get("type_code") or "").upper().strip()
        callsign = (aircraft.get("callsign") or "").upper().strip()
        operator = (aircraft.get("operator") or "").upper().strip()
        altitude = aircraft.get("altitude")
        speed = aircraft.get("ground_speed")
        category = (aircraft.get("category") or "").upper().strip()

        # ---- Rotor ----
        if self._is_rotor(type_code, category):
            types_found.append({"type": "Rotor", "confidence": 0.95})

        # ---- Sentinel (military) ----
        # >= 0.5 so a single strong signal (e.g. operator "Royal Air Force")
        # is enough. Sentinel is appended before Heavy/Hauler/etc. so a military
        # widebody (RAF Voyager, C-17) reads as Military, not "Heavy".
        mil_conf = self._military_confidence(hex_code, callsign, operator, type_code)
        is_military = mil_conf >= 0.5
        if is_military:
            types_found.append({"type": "Sentinel", "confidence": max(mil_conf, 0.92)})

        # ---- Medevac ----
        med_conf = self._medevac_confidence(operator, callsign, type_code)
        if med_conf > 0.5:
            types_found.append({"type": "Medevac", "confidence": med_conf})

        # ---- Heavy ---- (a military widebody stays Sentinel, not Heavy)
        if type_code in self._HEAVY_TYPES and not is_military:
            types_found.append({"type": "Heavy", "confidence": 0.90})

        # ---- Hauler ----
        if self._is_hauler(operator, callsign):
            types_found.append({"type": "Hauler", "confidence": 0.80})

        # ---- Bizjet ----
        if type_code in self._BIZJET_TYPES and not types_found:
            # Only if not already classified as something more specific
            types_found.append({"type": "Bizjet", "confidence": 0.85})

        # ---- Voyager (high altitude overflight) ----
        if altitude and altitude > 28000:
            # Check if we have route info showing it's not landing near us
            origin = aircraft.get("origin_icao", "")
            dest = aircraft.get("dest_icao", "")
            if origin and dest:
                types_found.append({"type": "Voyager", "confidence": 0.70})

        # ---- Trainer (pattern work near airport) ----
        if history and len(history) >= 2:
            trainer_conf = self._trainer_confidence(history)
            if trainer_conf > 0.6:
                types_found.append({"type": "Trainer", "confidence": trainer_conf})

        # ---- Hopper (short GA flight) ----
        if self._is_hopper(type_code, speed, altitude, types_found):
            types_found.append({"type": "Hopper", "confidence": 0.60})

        # Default: if nothing else matched, it's just a plane
        if not types_found:
            types_found.append({"type": "Aircraft", "confidence": 0.50})

        return types_found

    # -- individual checks --------------------------------------------------

    def _is_rotor(self, type_code: str, category: str) -> bool:
        if type_code in self._ROTOR_TYPES:
            return True
        if category in ("A7", "B7"):  # Mode S category for rotorcraft
            return True
        return False

    def _military_confidence(
        self, hex_code: str, callsign: str, operator: str, type_code: str
    ) -> float:
        score = 0.0
        if _hex_in_range(hex_code):
            score += 0.7
        if type_code in {"C130", "C17", "C5M", "B52", "F16", "F18", "F22",
                          "F35", "P8", "E3TF", "E8", "K35R", "V22", "A10",
                          "B1", "B2", "RC135", "U2", "SR71", "A400", "C295",
                          "C27J", "KC46", "A330 MRTT", "VC10", "TYPH", "EUFI"}:
            score += 0.5
        for pat in self._MIL_CALLSIGN_PATTERNS:
            if callsign.startswith(pat):
                score += 0.5
                break
        if any(k in operator for k in self._MIL_OPERATOR_KEYWORDS):
            score += 0.6
        return min(score, 1.0)

    @staticmethod
    def _callsign_prefix(callsign: str) -> str:
        """Leading alpha prefix of an airline-style callsign, or '' for an
        N-number registration (which is not a callsign)."""
        cs = (callsign or "").strip().upper()
        if not cs or re.match(r"^N\d", cs):
            return ""
        prefix = ""
        for ch in cs:
            if ch.isalpha():
                prefix += ch
            else:
                break
        return prefix

    def _medevac_confidence(self, operator: str, callsign: str, type_code: str) -> float:
        score = 0.0
        prefix = self._callsign_prefix(callsign)
        if len(prefix) >= 3 and prefix in self._MEDEVAC_CALLSIGN_PREFIXES:
            score += 0.7
        if any(k in operator for k in (
            "MEDEVAC", "AIR AMBULANCE", "LIFE FLIGHT", "AIR METHODS",
            "MEDFLIGHT", "MED-TRANS", "MED TRANS", "MERCY FLIGHT", "MEDSTAR",
        )):
            score += 0.7
        if type_code in {"EC35", "EC45", "H135", "H145", "B407", "B429", "A119", "A109"}:
            score += 0.2  # supportive only — never decisive on its own
        return min(score, 1.0)

    def _is_hauler(self, operator: str, callsign: str) -> bool:
        prefix = self._callsign_prefix(callsign)
        if len(prefix) >= 3 and prefix in self._CARGO_OPS:
            return True
        return any(k in operator for k in (
            "FEDEX", "FEDERAL EXPRESS", "UPS ", "UNITED PARCEL",
            "DHL", "ATLAS AIR", "CARGO", "FREIGHT",
        ))

    def _is_hopper(self, type_code: str, speed: Optional[float],
                   altitude: Optional[float], existing_types: List[Dict]) -> bool:
        # Light GA types not already classified
        ga_types = {"C172", "C152", "C182", "C210", "PA28", "PA32", "PA46",
                    "SR22", "SR20", "DA40", "DA42", "M20P", "BE36", "BE33",
                    "BE35", "BE20", "P46T", "S22T"}
        if type_code not in ga_types:
            return False
        # Not a trainer (already checked), not high/fast
        if speed and speed > 250:
            return False
        if altitude and altitude > 15000:
            return False
        # Make sure it's not already typed as something else
        existing = {t["type"] for t in existing_types}
        return len(existing.intersection({"Rotor", "Sentinel", "Medevac"})) == 0

    def _trainer_confidence(self, history: List[Dict[str, Any]]) -> float:
        """Detect pattern work: repeated low-altitude detections with reversing headings."""
        if len(history) < 3:
            return 0.0

        # Check for low altitude pattern
        low_alt_count = sum(1 for d in history
                           if d.get("altitude") and d["altitude"] < 3000)
        if low_alt_count < len(history) * 0.5:
            return 0.0

        # Check for speed changes (slow approach, climb)
        speeds = [d.get("ground_speed") for d in history if d.get("ground_speed")]
        if not speeds:
            return 0.0
        avg_speed = sum(speeds) / len(speeds)
        if avg_speed > 120:  # Too fast for pattern work
            return 0.0

        # Check for heading changes (circuit pattern)
        tracks = [d.get("track") for d in history if d.get("track") is not None]
        if len(tracks) >= 3:
            track_variance = max(tracks) - min(tracks)
            if 90 < track_variance < 360:  # Significant turning
                return min(0.50 + (len(history) * 0.02), 0.90)

        return 0.0

    # -- contrail detection -------------------------------------------------

    @staticmethod
    def contrail_likely(altitude_ft: Optional[float]) -> bool:
        """Quick v1 contrail check: altitude > 26,000 ft."""
        return altitude_ft is not None and altitude_ft > 26000


def contrail_likely(altitude_ft: Optional[float]) -> bool:
    """Module-level convenience wrapper for Classifier.contrail_likely."""
    return Classifier.contrail_likely(altitude_ft)


# ---------------------------------------------------------------------------
# Rarity — how special is this sighting? (type/role based, not random)
# ---------------------------------------------------------------------------
# Common      everyday airliners + GA trainers/singles
# Uncommon    regional jets/turboprops, less-common narrowbodies
# Rare        business jets, helicopters, larger turboprops, 757s
# Epic        widebodies, large-cabin bizjets, most military
# Legendary   superheavies, classics/warbirds, exotic military

_RARITY_LEGENDARY = {
    "A388", "A124", "A225", "CONC", "SR71", "B2", "B52", "B741", "B742", "B743",
    "SPIT", "P51", "B17", "DC3", "JU52", "LANC", "BLCF",
}
_RARITY_EPIC = {
    "A332", "A333", "A338", "A339", "A359", "A35K", "A342", "A343", "A345", "A346",
    "B744", "B748", "B762", "B763", "B764", "B772", "B773", "B77L", "B77W",
    "B788", "B789", "B78X", "MD11", "IL96", "DC10",
    "GLEX", "GLF5", "GLF6", "GL5T", "GL7T", "G650", "GL7T",
    "C17", "C5M", "C130", "K35R", "E3TF", "E8", "P8", "B1", "RC135", "U2",
}
_RARITY_RARE = {
    "B752", "B753",
    "C25A", "C25B", "C25C", "C525", "C510", "C56X", "C680", "C68A", "C700",
    "CL30", "CL35", "CL60", "E50P", "E55P", "F2TH", "F900", "FA50", "FA7X",
    "LJ31", "LJ35", "LJ45", "LJ60", "HA4T", "PC24",
    "BE20", "B350", "PC12", "TBM9", "C208", "PA46",
    "R44", "R66", "B06", "B407", "B429", "EC35", "EC45", "H135", "H145",
    "AS50", "S76", "S92", "A109", "A119", "UH60", "H60",
}
_RARITY_UNCOMMON = {
    "E170", "E75L", "E75S", "E190", "E195", "E135", "E145",
    "CRJ2", "CRJ7", "CRJ9", "CRJX",
    "AT43", "AT45", "AT72", "AT76", "DH8A", "DH8B", "DH8C", "DH8D", "SF34", "SW4", "BE99",
    "B739", "A319", "A21N", "A20N", "B38M", "B39M", "BCS1", "BCS3",
}


def rarity_for(aircraft: Dict[str, Any]) -> str:
    """Classify how rare/special an airframe is, by type and military status."""
    tc = (aircraft.get("type_code") or "").upper().strip()
    hex_code = (aircraft.get("hex") or "").upper().strip()

    is_military = _hex_in_range(hex_code) or tc in {
        "C130", "C17", "C5M", "B52", "F16", "F18", "F22", "F35", "P8", "E3TF",
        "E8", "K35R", "V22", "A10", "B1", "B2", "RC135", "U2", "H60", "UH60",
    }

    if tc in _RARITY_LEGENDARY:
        return "Legendary"
    if is_military or tc in _RARITY_EPIC:
        return "Epic"
    if tc in _RARITY_RARE:
        return "Rare"
    if tc in _RARITY_UNCOMMON:
        return "Uncommon"
    return "Common"


def flight_phase(
    altitude_ft: Optional[float],
    vertical_rate_fpm: Optional[float],
    ground_speed_kt: Optional[float] = None,
) -> str:
    """Human-readable flight phase from telemetry.

    Returns one of: "On Ground", "Climbing", "Descending", "Cruising", "Level".
    vertical_rate is feet/minute (positive = climbing).
    """
    if altitude_ft is not None and altitude_ft < 100 and (
        ground_speed_kt is None or ground_speed_kt < 60
    ):
        return "On Ground"
    vr = vertical_rate_fpm or 0
    if vr > 300:
        return "Climbing"
    if vr < -300:
        return "Descending"
    if altitude_ft is not None and altitude_ft >= 18000:
        return "Cruising"
    return "Level"


# ---------------------------------------------------------------------------
# Commuter / schedule predictor
# ---------------------------------------------------------------------------

class SchedulePredictor:
    """Detects commuter patterns and predicts next appearance.

    For each callsign, keeps a running list of detection timestamps.
    Nightly (or on-demand), computes day-of-week and hour-of-day histograms.
    If a callsign recurs on a regular cadence, tags it Commuter.
    """

    def analyze(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Analyze detection history for a single callsign.
        Returns prediction dict or None.
        """
        if len(detections) < 3:
            return None

        # Build day-of-week and hour histograms
        dow_counts = Counter()  # 0=Mon, 6=Sun
        hour_counts = Counter()

        for d in detections:
            ts = d.get("timestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(float(ts))
                dow_counts[dt.weekday()] += 1
                hour_counts[dt.hour] += 1
            except (TypeError, ValueError, OSError):
                continue

        if not dow_counts or not hour_counts:
            return None

        # Find dominant day(s)
        max_dow_count = max(dow_counts.values())
        dominant_days = [d for d, c in dow_counts.items() if c >= max_dow_count * 0.7]

        # Find dominant hour
        peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0]

        # If we see clustering on specific days, it's a commuter
        if max_dow_count >= 2 and len(dominant_days) <= 3:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            day_str = " and ".join(day_names[d] for d in sorted(dominant_days))

            confidence = min(max_dow_count / len(detections) * 1.5, 0.95)

            # Predict next expected
            next_expected = f"Expected {day_str} near {peak_hour}:00"

            return {
                "type": "Commuter",
                "confidence": round(confidence, 2),
                "schedule": {
                    "dominant_days": dominant_days,
                    "peak_hour": peak_hour,
                    "dow_histogram": dict(dow_counts),
                    "hour_histogram": dict(hour_counts),
                },
                "next_expected": next_expected,
            }

        return None


from datetime import datetime  # noqa: E402 — needed for schedule predictor
