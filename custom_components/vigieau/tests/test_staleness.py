import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.util import dt as dt_util

from custom_components.vigieau import (
    DOMAIN,
    LAST_SUCCESS_KEY,
    VigieauAPICoordinator,
    _stale_issue_id,
)


class FakeStore:
    def __init__(self, data=None):
        self.data = data
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data
        self.saved.append(data)


def make_coordinator(last_success_at=None, store=None, entry_id="entry-id"):
    coordinator = VigieauAPICoordinator.__new__(VigieauAPICoordinator)
    coordinator.hass = MagicMock()
    coordinator.config = {"city": "Paris"}
    coordinator.config_entry_id = entry_id
    coordinator._location = None
    coordinator._last_success_at = last_success_at
    coordinator._last_success_store = store or FakeStore()
    return coordinator


class TestLastSuccessPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_timestamp_when_nothing_is_stored(self):
        store = FakeStore()
        coordinator = make_coordinator(store=store)

        await coordinator._async_load_last_success()

        self.assertIsNotNone(coordinator._last_success_at)
        self.assertEqual(
            store.saved[-1][LAST_SUCCESS_KEY],
            coordinator._last_success_at.isoformat(),
        )

    async def test_load_persisted_timestamp(self):
        previous = dt_util.utcnow() - timedelta(hours=30)
        store = FakeStore({LAST_SUCCESS_KEY: previous.isoformat()})
        coordinator = make_coordinator(store=store)

        await coordinator._async_load_last_success()

        self.assertEqual(coordinator._last_success_at, previous)
        self.assertEqual(store.saved, [])

    async def test_record_success_updates_and_saves_timestamp(self):
        previous = dt_util.utcnow() - timedelta(hours=30)
        store = FakeStore({LAST_SUCCESS_KEY: previous.isoformat()})
        coordinator = make_coordinator(previous, store)

        await coordinator._async_record_success()

        self.assertGreater(coordinator._last_success_at, previous)
        self.assertEqual(
            store.saved[-1][LAST_SUCCESS_KEY],
            coordinator._last_success_at.isoformat(),
        )


class TestStaleDataRepair(unittest.TestCase):
    def test_issue_id_is_per_config_entry(self):
        self.assertEqual(_stale_issue_id("abc"), "stale_data_abc")
        self.assertNotEqual(_stale_issue_id("abc"), _stale_issue_id("def"))

    def test_creates_non_persistent_repair_after_24h(self):
        coordinator = make_coordinator(
            dt_util.utcnow() - timedelta(hours=25), entry_id="abc"
        )

        with patch("custom_components.vigieau.ir.async_create_issue") as create, patch(
            "custom_components.vigieau.ir.async_delete_issue"
        ) as delete:
            coordinator._async_check_stale_data()

        delete.assert_not_called()
        create.assert_called_once()
        args, kwargs = create.call_args
        self.assertEqual(args[:3], (coordinator.hass, DOMAIN, "stale_data_abc"))
        self.assertFalse(kwargs["is_fixable"])
        self.assertFalse(kwargs["is_persistent"])
        self.assertEqual(kwargs["translation_key"], "stale_data")
        self.assertEqual(kwargs["translation_placeholders"]["city"], "Paris")
        self.assertEqual(kwargs["translation_placeholders"]["hours"], "25")

    def test_deletes_repair_when_data_is_fresh(self):
        coordinator = make_coordinator(
            dt_util.utcnow() - timedelta(hours=1), entry_id="abc"
        )

        with patch("custom_components.vigieau.ir.async_create_issue") as create, patch(
            "custom_components.vigieau.ir.async_delete_issue"
        ) as delete:
            coordinator._async_check_stale_data()

        create.assert_not_called()
        delete.assert_called_once_with(
            coordinator.hass, DOMAIN, "stale_data_abc"
        )

    def test_does_nothing_without_timestamp(self):
        coordinator = make_coordinator()

        with patch("custom_components.vigieau.ir.async_create_issue") as create, patch(
            "custom_components.vigieau.ir.async_delete_issue"
        ) as delete:
            coordinator._async_check_stale_data()

        create.assert_not_called()
        delete.assert_not_called()
