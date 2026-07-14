"""Tests for aircraft classification — especially the military detection that
once tagged an RAF Voyager as 'Heavy' (threshold was > 0.5, operator match
scored exactly 0.5)."""

from classifier import Classifier, _hex_in_range, rarity_for


clf = Classifier()


def primary(aircraft, history=None):
    types = clf.classify(aircraft, history)
    return types[0]["type"] if types else None


class TestMilitary:
    def test_raf_hex_range(self):
        assert _hex_in_range("43C123") is True       # RAF allocation
        assert _hex_in_range("A18B13") is False      # ordinary US civil

    def test_us_military_hex_is_sentinel(self):
        assert primary({"hex": "AE1234", "type_code": "", "callsign": ""}) == "Sentinel"

    def test_operator_royal_air_force_is_enough(self):
        """The exact bug: 'Royal Air Force' operator alone must classify military."""
        ac = {"hex": "400123", "type_code": "", "operator": "Royal Air Force"}
        assert primary(ac) == "Sentinel"

    def test_military_widebody_is_sentinel_not_heavy(self):
        """RAF Voyager (A330 tanker): military beats Heavy."""
        ac = {"hex": "43C777", "type_code": "A332", "operator": "Royal Air Force"}
        types = [t["type"] for t in clf.classify(ac)]
        assert types[0] == "Sentinel"
        assert "Heavy" not in types

    def test_civil_widebody_is_heavy(self):
        ac = {"hex": "A18B13", "type_code": "B77W", "operator": "United Airlines"}
        assert primary(ac) == "Heavy"

    def test_rch_callsign(self):
        ac = {"hex": "A00001", "type_code": "", "callsign": "RCH421"}
        assert primary(ac) == "Sentinel"

    def test_c17_type_code(self):
        ac = {"hex": "AE0001", "type_code": "C17"}
        assert primary(ac) == "Sentinel"


class TestOtherTypes:
    def test_rotor(self):
        assert primary({"hex": "A00002", "type_code": "S76"}) == "Rotor"

    def test_medevac_not_triggered_by_owner_substring(self):
        """'MED'/'CAL' inside ordinary owner names must NOT flag medevac."""
        ac = {"hex": "A00003", "type_code": "C172", "callsign": "N123AB",
              "operator": "CALSPAN MEDIA HOLDINGS"}
        types = [t["type"] for t in clf.classify(ac)]
        assert "Medevac" not in types

    def test_cargo_callsign_is_hauler(self):
        ac = {"hex": "A00004", "type_code": "B763", "callsign": "FDX1234"}
        types = [t["type"] for t in clf.classify(ac)]
        assert "Hauler" in types

    def test_default_is_aircraft(self):
        types = clf.classify({"hex": "A00005", "type_code": ""})
        assert types[0]["type"] in ("Aircraft", "Hopper")


class TestRarity:
    def test_military_hex_is_epic_or_better(self):
        r = rarity_for({"hex": "AE1234", "type_code": "C130"})
        assert r in ("Epic", "Legendary")
