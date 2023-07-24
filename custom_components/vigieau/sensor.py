import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from . import (
    UsageRestrictionEntity,
    AlertLevelEntity,
)
from .const import (
    DOMAIN,
    SENSOR_DEFINITIONS,
    SENSOR_DEFINITIONS
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    _LOGGER.info("Called async setup entry")
    vigieau_coordinator = hass.data[DOMAIN][entry.entry_id]["vigieau_coordinator"]
    sensors = [
               UsageRestrictionEntity(vigieau_coordinator,hass,"mydi",entry,sensor_description)
               for sensor_description in SENSOR_DEFINITIONS
              ]
    sensors.append(AlertLevelEntity(vigieau_coordinator, hass, entry))

    async_add_entities(sensors)
    _LOGGER.info("We finished the setup of vigieau *sensors*")
    await vigieau_coordinator.async_config_entry_first_refresh()
