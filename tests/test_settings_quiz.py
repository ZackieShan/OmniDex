"""Tests for the runtime settings overlay, quiz bank, and achievements."""

import json

import settings as settings_mod
from achievements import compute_achievements, ACHIEVEMENTS
from quiz import get_quiz, QUESTIONS


class TestSettings:
    def _fresh(self, tmp_path):
        return settings_mod.Settings(path=tmp_path / "settings.json")

    def test_defaults(self, tmp_path):
        s = self._fresh(tmp_path)
        assert s.get("air_radius_miles") == 5.0
        assert s.get("night_dim_enabled") is True

    def test_set_and_persist(self, tmp_path):
        s = self._fresh(tmp_path)
        result = s.set_many({"air_radius_miles": "7.5", "night_dim_enabled": "false"})
        assert result["applied"]["air_radius_miles"] == 7.5
        assert result["applied"]["night_dim_enabled"] is False
        assert result["restart_required"] is True   # radius is restart-class
        # Survives a reload
        s2 = self._fresh(tmp_path)
        assert s2.get("air_radius_miles") == 7.5

    def test_unknown_and_bad_values_rejected(self, tmp_path):
        s = self._fresh(tmp_path)
        result = s.set_many({"nope": 1, "attract_idle_minutes": "banana"})
        assert "nope" in result["errors"]
        assert "attract_idle_minutes" in result["errors"]
        assert result["applied"] == {}

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        p = tmp_path / "settings.json"
        p.write_text("{not json!!", encoding="utf-8")
        s = settings_mod.Settings(path=p)
        assert s.get("sea_radius_miles") == 10.0

    def test_apply_to_config(self, tmp_path):
        from config import SkyDexConfig
        s = self._fresh(tmp_path)
        s.set_many({"air_radius_miles": 8.0, "sea_radius_miles": 12.0})
        cfg = s.apply_to_config(SkyDexConfig())
        assert cfg.range.radius_miles == 8.0
        assert cfg.marine.radius_miles == 12.0


class TestQuiz:
    def test_shape_and_answer_index(self):
        qs = get_quiz(5)
        assert len(qs) == 5
        for q in qs:
            assert len(q["options"]) == 4
            assert 0 <= q["answer"] < 4

    def test_domain_filter(self):
        for q in get_quiz(5, domain="sea"):
            assert q["domain"] == "sea"

    def test_bank_sanity(self):
        for question, correct, wrong, dom in QUESTIONS:
            assert len(wrong) == 3, question
            assert dom in ("air", "sea", "atmo")


class TestAchievements:
    def test_thresholds(self):
        stats = {"airframes": 100, "vessels": 0}
        result = {a["id"]: a for a in compute_achievements(stats)}
        assert result["century"]["unlocked"] is True
        assert result["first_vessel"]["unlocked"] is False
        assert result["first_vessel"]["progress"] == 0

    def test_all_defined_stats_exist_in_db_keys(self):
        # Every achievement points at a stat key produced by get_achievement_stats.
        known = {"airframes", "vessels", "air_types", "heavies", "rotors", "military",
                 "emergencies", "night_catches", "legendaries", "bonded", "sea_flags",
                 "superyachts", "sailing", "sea_categories", "best_day_air",
                 "best_day_sea", "iss_passes", "trains", "acelas", "train_passes"}
        for _, _, _, key, _, _, _ in ACHIEVEMENTS:
            assert key in known, key
