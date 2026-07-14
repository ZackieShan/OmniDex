"""Regression tests for the astronomy math — locks down the exact class of bug
we shipped once (sunrise sign flip). Reference values are from NOAA/USNO for
Stratford CT (41.1635, -73.1262). The low-precision formulas get ±10 min slack.

Run on the Pi:  cd ~/skydex && python3 -m pytest -q tests
"""

from datetime import datetime, timezone

import atmo

LAT, LON = 41.1635, -73.1262


def _utc(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


class TestSunTimes:
    def test_summer_solstice_daylight_length(self):
        """June 21 at 41.15°N has ~15h07m of daylight."""
        st = atmo.sun_times(LAT, LON, _utc(2026, 6, 21, 16))
        assert st["sunrise"] and st["sunset"]
        daylight_h = (st["sunset"] - st["sunrise"]) / 3600
        assert 14.8 <= daylight_h <= 15.4, f"daylight {daylight_h:.2f}h"

    def test_winter_solstice_daylight_length(self):
        """Dec 21 at 41.15°N has ~9h13m of daylight."""
        st = atmo.sun_times(LAT, LON, _utc(2026, 12, 21, 17))
        daylight_h = (st["sunset"] - st["sunrise"]) / 3600
        assert 9.0 <= daylight_h <= 9.5, f"daylight {daylight_h:.2f}h"

    def test_solar_noon_matches_longitude(self):
        """THE sunrise-bug test: at -73.1° the sun transits ~16:52 UTC, NOT
        ~07:08 UTC (which is what the flipped-sign bug produced)."""
        st = atmo.sun_times(LAT, LON, _utc(2026, 6, 21, 16))
        noon = datetime.fromtimestamp(st["solar_noon"], tz=timezone.utc)
        noon_h = noon.hour + noon.minute / 60
        assert 16.5 <= noon_h <= 17.3, f"solar noon at {noon_h:.2f}h UTC — longitude sign bug?"

    def test_june_sunrise_is_early_morning_local(self):
        """June sunrise here is ~05:20 EDT (09:20 UTC) — never evening."""
        st = atmo.sun_times(LAT, LON, _utc(2026, 6, 21, 16))
        rise = datetime.fromtimestamp(st["sunrise"], tz=timezone.utc)
        rise_h = rise.hour + rise.minute / 60
        assert 9.0 <= rise_h <= 9.7, f"sunrise at {rise_h:.2f}h UTC (expect ~9.3)"

    def test_civil_dusk_after_sunset(self):
        st = atmo.sun_times(LAT, LON, _utc(2026, 6, 21, 16))
        assert st["civil_dusk"] > st["sunset"]
        assert st["civil_dawn"] < st["sunrise"]
        # Civil twilight at this latitude is ~30 min around the solstice.
        assert 15 * 60 <= (st["civil_dusk"] - st["sunset"]) <= 55 * 60


class TestMoonPhase:
    def test_known_full_moon(self):
        """2015-07-31 (the 'blue moon') was a full moon."""
        mp = atmo.moon_phase(_utc(2015, 7, 31, 11))
        assert mp["illumination"] >= 96, mp
        assert mp["phase"] == "Full Moon", mp

    def test_known_new_moon(self):
        """2015-08-14 was a new moon."""
        mp = atmo.moon_phase(_utc(2015, 8, 14, 15))
        assert mp["illumination"] <= 4, mp
        assert mp["phase"] == "New Moon", mp

    def test_age_in_range(self):
        mp = atmo.moon_phase(_utc(2026, 7, 1))
        assert 0 <= mp["age_days"] <= 29.6


class TestZodiac:
    def test_sun_sign_early_july_is_cancer(self):
        z = atmo.zodiac(_utc(2026, 7, 5, 12))
        assert z["sun_sign"] == "Cancer", z

    def test_sun_sign_mid_january_is_capricorn(self):
        z = atmo.zodiac(_utc(2026, 1, 10, 12))
        assert z["sun_sign"] == "Capricorn", z

    def test_moon_sign_is_a_real_sign(self):
        signs = {"Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
                 "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"}
        z = atmo.zodiac(_utc(2026, 7, 1, 12))
        assert z["moon_sign"] in signs


class TestPlanets:
    def test_visible_planets_shape(self):
        planets = atmo.visible_planets(LAT, LON, _utc(2026, 7, 1))
        for p in planets:
            assert p["name"] in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
            assert p["when_visible"] in ("Evening", "Morning")
            assert 12 <= abs(p["elongation"]) <= 180
