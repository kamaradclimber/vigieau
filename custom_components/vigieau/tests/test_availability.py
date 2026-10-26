import unittest
from unittest.mock import MagicMock

from custom_components.vigieau import (
    AlertLevelEntity,
    RestrictionMixin,
    UsageRestrictionBinaryEntity,
    UsageRestrictionEntity,
)


class TestAvailabilityPolicy(unittest.TestCase):
    def _assert_available(self, entity_class, has_data):
        entity = MagicMock()
        entity.coordinator.data = {"usages": []} if has_data else None
        return entity_class.available.fget(entity)

    def test_alert_stays_available_with_last_known_data(self):
        self.assertTrue(self._assert_available(AlertLevelEntity, True))

    def test_alert_unavailable_without_data(self):
        self.assertFalse(self._assert_available(AlertLevelEntity, False))

    def test_restriction_sensors_stay_available_with_last_known_data(self):
        for entity_class in (
            RestrictionMixin,
            UsageRestrictionEntity,
            UsageRestrictionBinaryEntity,
        ):
            with self.subTest(entity_class=entity_class):
                self.assertTrue(self._assert_available(entity_class, True))

    def test_restriction_sensors_unavailable_without_data(self):
        for entity_class in (
            RestrictionMixin,
            UsageRestrictionEntity,
            UsageRestrictionBinaryEntity,
        ):
            with self.subTest(entity_class=entity_class):
                self.assertFalse(self._assert_available(entity_class, False))
