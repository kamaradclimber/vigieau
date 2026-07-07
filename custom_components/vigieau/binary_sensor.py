import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    UsageRestrictionBinaryEntity,
)
from .const import DOMAIN, SENSOR_DEFINITIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    vigieau_coordinator = hass.data[DOMAIN][entry.entry_id]["vigieau_coordinator"]
    sensors = [
        UsageRestrictionBinaryEntity(
            vigieau_coordinator, hass, entry, sensor_description
        )
        for sensor_description in SENSOR_DEFINITIONS
    ]

    async_add_entities(sensors)
