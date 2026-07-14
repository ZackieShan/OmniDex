"""Tests for SeaDex vessel classification and geo helpers."""

from vessels import ship_category, vessel_rarity, mmsi_country, is_anchored, nav_status_text
from ais_receiver import _radius_to_box


class TestShipCategory:
    def test_cargo(self):
        assert ship_category(70) == "Cargo"

    def test_tanker(self):
        assert ship_category(80) == "Tanker"

    def test_superyacht_by_length(self):
        """A big 'pleasure craft' (type 37) is a Superyacht — the Zenji fix."""
        assert ship_category(37, 55.0) == "Superyacht"

    def test_small_pleasure_stays_pleasure(self):
        assert ship_category(37, 12.0) == "Pleasure"

    def test_unknown_is_other(self):
        assert ship_category(None) == "Other"


class TestMmsiCountry:
    def test_us_mid(self):
        assert mmsi_country("367123456") == "US"

    def test_uk_mid(self):
        assert mmsi_country("232001234") == "GB"

    def test_garbage(self):
        assert mmsi_country("xx") is None


class TestAnchored:
    def test_at_anchor_status(self):
        assert is_anchored(1) is True       # AIS: at anchor

    def test_moored_status(self):
        assert is_anchored(5) is True       # AIS: moored

    def test_underway(self):
        assert is_anchored(0, speed=8.0) is False

    def test_nav_status_text(self):
        assert "anchor" in (nav_status_text(1) or "").lower()


class TestRadiusBox:
    def test_box_is_centered_and_sized(self):
        lat_min, lon_min, lat_max, lon_max = _radius_to_box(41.1635, -73.1262, 10.0)
        assert lat_min < 41.1635 < lat_max
        assert lon_min < -73.1262 < lon_max
        # 10 miles ≈ 0.145° latitude each way.
        assert 0.25 <= (lat_max - lat_min) <= 0.35
        # Longitude degrees are shorter at 41°N, so the lon span is wider.
        assert (lon_max - lon_min) > (lat_max - lat_min)
