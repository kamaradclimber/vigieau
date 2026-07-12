from os import path
import sys
from unittest.mock import MagicMock, patch
from datetime import time as dt_time, datetime as dt_datetime, timedelta

current_dir = path.dirname(__file__)
parent_dir = path.dirname(current_dir)
sys.path.append(".")
sys.path.append(parent_dir)

from custom_components.vigieau.__init__ import _parse_time_str, UsageRestrictionEntity, UsageRestrictionBinaryEntity
import unittest


class TestParseTimeStr(unittest.TestCase):
    def test_parse_hhmm_colon(self):
        self.assertEqual(_parse_time_str("08:00"), dt_time(8, 0))
        self.assertEqual(_parse_time_str("20:00"), dt_time(20, 0))
        self.assertEqual(_parse_time_str("8:00"), dt_time(8, 0))

    def test_parse_hhmm_h_format(self):
        self.assertEqual(_parse_time_str("8h00"), dt_time(8, 0))
        self.assertEqual(_parse_time_str("20h00"), dt_time(20, 0))

    def test_parse_hh_h_format(self):
        self.assertEqual(_parse_time_str("8h"), dt_time(8, 0))
        self.assertEqual(_parse_time_str("20h"), dt_time(20, 0))

    def test_parse_none_or_empty(self):
        self.assertIsNone(_parse_time_str(None))
        self.assertIsNone(_parse_time_str(""))

    def test_parse_invalid(self):
        self.assertIsNone(_parse_time_str("abc"))


class TestComputeNativeValue(unittest.TestCase):
    def _make_entity(self, restrictions, time_restrictions=None, attributes=None):
        entity = MagicMock(spec=UsageRestrictionEntity)
        entity._restrictions = restrictions
        entity._time_restrictions = time_restrictions or {}
        entity._extracted_time_range = None
        entity._attr_state_attributes = attributes or {}
        entity._native_is_time_based = False
        entity._config_entry = MagicMock()
        entity._config_entry.data = {"INSEE": "99999"}
        entity._attr_native_value = None

        entity.compute_native_value = UsageRestrictionEntity.compute_native_value.__get__(entity, UsageRestrictionEntity)
        entity._is_time_based = UsageRestrictionEntity._is_time_based.__get__(entity, UsageRestrictionEntity)
        entity._extract_time_range_from_descriptions = UsageRestrictionEntity._extract_time_range_from_descriptions.__get__(entity, UsageRestrictionEntity)
        return entity

    def test_no_restrictions(self):
        entity = self._make_entity([])
        self.assertEqual(entity.compute_native_value(), "no_restriction")
        self.assertFalse(entity._is_time_based())

    def test_time_based_sur_plage_horaire(self):
        entity = self._make_entity(["Interdiction sur plage horaire"])
        result = entity.compute_native_value()
        self.assertEqual(result, "time_based_ban")
        self.assertTrue(entity._is_time_based())

    def test_time_based_de_8h_a_20h_stable_native(self):
        """Native value stays 'time_based_ban'; dynamic info is in attributes"""
        entity = self._make_entity(
            ["Interdiction de 8 h à 20 h"],
            {"Arrosage potager": ["8h", "20h"]},
            {"Categorie: Arrosage potager": "Interdiction de 8 h à 20 h"}
        )
        result = entity.compute_native_value()
        self.assertEqual(result, "time_based_ban")
        self.assertTrue(entity._is_time_based())

    def test_time_based_no_time_data_fallback(self):
        entity = self._make_entity(["Interdiction de 8 h à 20 h"])
        result = entity.compute_native_value()
        self.assertEqual(result, "time_based_ban")
        self.assertTrue(entity._is_time_based())

    def test_time_based_interdit_with_time_pattern(self):
        """'Interdit' (not 'Interdiction') with a time pattern should be detected as time-based."""
        entity = self._make_entity(
            ["Interdit sauf plantations (arbres) et îlots de fraîcheur uniquement de 20 h à 8 h"]
        )
        result = entity.compute_native_value()
        self.assertEqual(result, "time_based_ban")
        self.assertTrue(entity._is_time_based())

    def test_total_interdiction(self):
        entity = self._make_entity(["Interdiction"])
        result = entity.compute_native_value()
        self.assertEqual(result, "ban")
        self.assertFalse(entity._is_time_based())

    def test_mixed_time_and_total_interdiction(self):
        entity = self._make_entity(["Interdiction de 8 h à 20 h", "Interdiction"])
        result = entity.compute_native_value()
        self.assertEqual(result, "ban")
        self.assertFalse(entity._is_time_based())

    def test_interdiction_sauf_exception(self):
        entity = self._make_entity(["Interdiction sauf exception"])
        result = entity.compute_native_value()
        self.assertEqual(result, "ban_with_exceptions")
        self.assertFalse(entity._is_time_based())

    def test_autorise_sauf_exception(self):
        entity = self._make_entity(["Pas de restriction sauf arrêté spécifique."])
        result = entity.compute_native_value()
        self.assertEqual(result, "allowed_except_specific_decree")
        self.assertFalse(entity._is_time_based())

    def test_single_restriction_fallback(self):
        entity = self._make_entity(["Réduction de prélèvement"])
        result = entity.compute_native_value()
        self.assertEqual(result, "water_withdrawal_reduction")
        self.assertFalse(entity._is_time_based())

    def test_identical_duplicate_restrictions_fallback(self):
        entity = self._make_entity(
            ["Information via communiqué de presse", "Information via communiqué de presse", "Information via communiqué de presse"]
        )
        result = entity.compute_native_value()
        self.assertEqual(result, "Information via communiqué de presse")
        self.assertFalse(entity._is_time_based())


class TestExtractTimeRange(unittest.TestCase):
    def _make_entity(self, restrictions):
        entity = MagicMock(spec=UsageRestrictionEntity)
        entity._restrictions = restrictions
        entity._extract_time_range_from_descriptions = UsageRestrictionEntity._extract_time_range_from_descriptions.__get__(entity, UsageRestrictionEntity)
        return entity

    def test_extract_simple(self):
        entity = self._make_entity(["Interdiction de 11h à 18h."])
        result = entity._extract_time_range_from_descriptions()
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start, dt_time(11, 0))
        self.assertEqual(end, dt_time(18, 0))

    def test_extract_with_spaces(self):
        entity = self._make_entity(["Interdiction de 8 h à 20 h"])
        result = entity._extract_time_range_from_descriptions()
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start, dt_time(8, 0))
        self.assertEqual(end, dt_time(20, 0))

    def test_extract_no_match(self):
        entity = self._make_entity(["Interdiction"])
        self.assertIsNone(entity._extract_time_range_from_descriptions())

    def test_extract_interdit_sauf_uniquement_de_inverts_range(self):
        """'uniquement de X h à Y h' describes the allowed window, so the
        extracted restricted window should be the complement (Y-X)."""
        entity = self._make_entity(
            ["Interdit sauf plantations (arbres) et îlots de fraîcheur uniquement de 20 h à 8 h"]
        )
        result = entity._extract_time_range_from_descriptions()
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start, dt_time(8, 0))
        self.assertEqual(end, dt_time(20, 0))

    def test_extract_interdit_sauf_uniquement_de_does_not_affect_normal(self):
        """Normal patterns like 'de X h à Y h' are not affected by the uniquement fix."""
        entity = self._make_entity(["Interdiction de 11h à 18h."])
        result = entity._extract_time_range_from_descriptions()
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start, dt_time(11, 0))
        self.assertEqual(end, dt_time(18, 0))


class TestTimeAttributes(unittest.TestCase):
    def _make_entity(self, restrictions, time_restrictions=None, extracted_range=None):
        entity = MagicMock(spec=UsageRestrictionEntity)
        entity._restrictions = restrictions
        entity._time_restrictions = time_restrictions or {}
        entity._extracted_time_range = extracted_range
        entity._attr_state_attributes = {}

        entity._get_effective_time_ranges = UsageRestrictionEntity._get_effective_time_ranges.__get__(entity, UsageRestrictionEntity)
        entity._is_currently_restricted = UsageRestrictionEntity._is_currently_restricted.__get__(entity, UsageRestrictionEntity)
        entity._update_dynamic_attributes = UsageRestrictionEntity._update_dynamic_attributes.__get__(entity, UsageRestrictionEntity)
        entity._native_is_time_based = False
        entity._attr_native_value = None
        return entity

    def test_get_ranges_from_api(self):
        entity = self._make_entity([], {"u1": ["8h", "20h"]})
        ranges = entity._get_effective_time_ranges()
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0], (dt_time(8, 0), dt_time(20, 0)))

    def test_get_ranges_from_extracted(self):
        entity = self._make_entity([], extracted_range=(dt_time(11, 0), dt_time(18, 0)))
        ranges = entity._get_effective_time_ranges()
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0], (dt_time(11, 0), dt_time(18, 0)))

    def test_get_ranges_empty(self):
        entity = self._make_entity([])
        self.assertEqual(entity._get_effective_time_ranges(), [])

    def test_currently_restricted_inside(self):
        entity = self._make_entity([], extracted_range=(dt_time(8, 0), dt_time(20, 0)))
        self.assertTrue(entity._is_currently_restricted(dt_time(10, 0)))

    def test_currently_restricted_outside(self):
        entity = self._make_entity([], extracted_range=(dt_time(8, 0), dt_time(20, 0)))
        self.assertFalse(entity._is_currently_restricted(dt_time(22, 0)))

    def test_currently_restricted_overnight_inside(self):
        entity = self._make_entity([], extracted_range=(dt_time(20, 0), dt_time(8, 0)))
        self.assertTrue(entity._is_currently_restricted(dt_time(22, 0)))

    def test_currently_restricted_overnight_outside(self):
        entity = self._make_entity([], extracted_range=(dt_time(20, 0), dt_time(8, 0)))
        self.assertFalse(entity._is_currently_restricted(dt_time(12, 0)))

    def test_dynamic_attributes_total_interdiction(self):
        """Total ban should have currently_restricted=True, no time attributes"""
        entity = self._make_entity(["Interdiction"])
        entity._native_is_time_based = False
        entity._attr_state_attributes = {"restriction": "ban"}
        entity._update_dynamic_attributes()
        self.assertTrue(entity._attr_state_attributes["currently_restricted"])
        self.assertNotIn("next_restriction_start", entity._attr_state_attributes)
        self.assertNotIn("next_restriction_end", entity._attr_state_attributes)

    def test_dynamic_attributes_aucune_restriction(self):
        entity = self._make_entity([])
        entity._native_is_time_based = False
        entity._attr_state_attributes = {"restriction": "no_restriction"}
        entity._update_dynamic_attributes()
        self.assertFalse(entity._attr_state_attributes["currently_restricted"])
        self.assertNotIn("next_restriction_start", entity._attr_state_attributes)

    def test_dynamic_attributes_autorise_sauf_exception(self):
        entity = self._make_entity(["Pas de restriction sauf arrêté spécifique."])
        entity._native_is_time_based = False
        entity._attr_state_attributes = {"restriction": "allowed_except_specific_decree"}
        entity._update_dynamic_attributes()
        self.assertFalse(entity._attr_state_attributes["currently_restricted"])

    def test_dynamic_attributes_time_based_restricted(self):
        """Time-based at 14h for 11h-18h: currently_restricted=True, with time attributes"""
        entity = self._make_entity(
            ["Interdiction de 11h à 18h"],
            extracted_range=(dt_time(11, 0), dt_time(18, 0))
        )
        entity._native_is_time_based = True
        entity._attr_state_attributes = {"restriction": "time_based_ban"}
        fake_now = dt_datetime(2026, 7, 6, 14, 0, 0)
        with patch('custom_components.vigieau.__init__.dt_util') as mock_dt:
            mock_dt.now.return_value = fake_now
            entity._update_dynamic_attributes()
        self.assertTrue(entity._attr_state_attributes["currently_restricted"])
        self.assertIn("next_restriction_start", entity._attr_state_attributes)
        self.assertIn("next_restriction_end", entity._attr_state_attributes)

    def test_dynamic_attributes_time_based_not_restricted(self):
        """Time-based at 22h for 11h-18h: currently_restricted=False, with time attributes"""
        entity = self._make_entity(
            ["Interdiction de 11h à 18h"],
            extracted_range=(dt_time(11, 0), dt_time(18, 0))
        )
        entity._native_is_time_based = True
        entity._attr_state_attributes = {"restriction": "time_based_ban"}
        fake_now = dt_datetime(2026, 7, 6, 22, 0, 0)
        with patch('custom_components.vigieau.__init__.dt_util') as mock_dt:
            mock_dt.now.return_value = fake_now
            entity._update_dynamic_attributes()
        self.assertFalse(entity._attr_state_attributes["currently_restricted"])
        self.assertIn("next_restriction_start", entity._attr_state_attributes)
        self.assertIn("next_restriction_end", entity._attr_state_attributes)


class TestBinarySensorEntity(unittest.TestCase):
    def _make_binary_entity(self, state_attributes=None):
        entity = MagicMock(spec=UsageRestrictionBinaryEntity)
        entity._attr_state_attributes = state_attributes or {}
        entity._config = MagicMock()
        entity._config.commonly_used = False
        entity.is_on = UsageRestrictionBinaryEntity.is_on.__get__(entity, UsageRestrictionBinaryEntity)
        entity.icon = UsageRestrictionBinaryEntity.icon.__get__(entity, UsageRestrictionBinaryEntity)
        return entity

    def test_is_on_when_restricted(self):
        entity = self._make_binary_entity({"currently_restricted": True})
        self.assertFalse(entity.is_on)

    def test_is_on_when_not_restricted(self):
        entity = self._make_binary_entity({"currently_restricted": False})
        self.assertTrue(entity.is_on)

    def test_is_on_when_no_attrs(self):
        entity = self._make_binary_entity(None)
        self.assertTrue(entity.is_on)

    def test_icon_restricted(self):
        entity = self._make_binary_entity({"currently_restricted": True})
        self.assertEqual(entity.icon, "mdi:water-off")

    def test_icon_not_restricted(self):
        entity = self._make_binary_entity({"currently_restricted": False})
        self.assertEqual(entity.icon, "mdi:water-check")


if __name__ == "__main__":
    unittest.main()
