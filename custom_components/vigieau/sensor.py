import voluptuous as vol
from datetime import timedelta, datetime
from typing import Optional
import logging
import asyncio

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityPlatformState
from homeassistant.config_entries import ConfigEntry

from . import (
    UsageRestrictionEntity,
    AlertLevelEntity,
    VigieauAPICoordinator,
)
from .const import (
    DOMAIN,
    SENSOR_DEFINITIONS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    _LOGGER.info("Called async setup entry")
    vigieau_coordinator = hass.data[DOMAIN][entry.entry_id]["vigieau_coordinator"]
    sensors = []
    sensors.append(AlertLevelEntity(vigieau_coordinator, hass))
    for sensor_id in SENSOR_DEFINITIONS:
        sensors.append(UsageRestrictionEntity(vigieau_coordinator, hass, sensor_id))

    async_add_entities(sensors)
    _LOGGER.info("We finished the setup of vigieau *sensors*")
    await vigieau_coordinator.async_config_entry_first_refresh()
