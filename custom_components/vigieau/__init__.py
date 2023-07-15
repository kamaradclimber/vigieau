import os
import re
import json
import urllib.parse
import logging
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional, Tuple
from dateutil import tz
from itertools import dropwhile, takewhile
import aiohttp


from homeassistant.const import Platform, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from .const import BASE_URL, DOMAIN, DEBUG_DATA, SENSOR_DEFINITIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Called async setup entry from __init__.py")

    hass.data.setdefault(DOMAIN, {})

    # here we store the coordinator for future access
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["vigieau_coordinator"] = VigieauAPICoordinator(
        hass, dict(entry.data)
    )

    # will make sure async_setup_entry from sensor.py is called
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    # subscribe to config updates
    entry.async_on_unload(entry.add_update_listener(update_entry))

    return True


async def update_entry(hass, entry):
    """
    This method is called when options are updated
    We trigger the reloading of entry (that will eventually call async_unload_entry)
    """
    _LOGGER.debug("update_entry method called")
    # will make sure async_setup_entry from sensor.py is called
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """This method is called to clean all sensors before re-adding them"""
    _LOGGER.debug("async_unload_entry method called")
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class VigieauAPICoordinator(DataUpdateCoordinator):
    """A coordinator to fetch data from the api only once"""

    def __init__(self, hass, config: ConfigType):
        super().__init__(
            hass,
            _LOGGER,
            name="vigieau api",  # for logging purpose
            update_interval=timedelta(hours=1),
            update_method=self.update_method,
        )
        self.config = config
        self.hass = hass
        self._async_client = None

    # FIXME(kamaradclimber): why so much complexity to get the client? We could simply add it in the constructor
    async def async_client(self):
        if not self._async_client:
            self._async_client = get_async_client(self.hass, verify_ssl=True)
        return self._async_client

    def _timezone(self):
        timezone = self.hass.config.as_dict()["time_zone"]
        return tz.gettz(timezone)

    async def fetch_street_and_insee_code(self) -> Tuple[str, str]:
        client = await self.async_client()
        r = await client.get(
            f"https://api-adresse.data.gouv.fr/reverse/?lat={self.lat}&lon={self.lon}&type=housenumber"
        )
        if not r.is_success:
            raise UpdateFailed(
                "Failed to fetch address from api-adresse.data.gouv.fr api"
            )
        data = r.json()
        _LOGGER.debug(f"Data received from api-adresse.data.gouv.fr: {data}")
        if len(data["features"]) == 0:
            _LOGGER.warn(
                f"Data received from api-adresse.data.gouv.fr is empty for those coordinates: ({self.lat}, {self.lon}). Are you sure they are located in France?"
            )
            raise UpdateFailed(
                "Impossible to find approximate address of the current HA instance"
            )
        properties = data["features"][0]["properties"]
        return (properties["street"], properties["citycode"])

    @property
    def lat(self) -> float:
        if "VIGIEAU_DEBUG" in os.environ:
            return 48.841
        return self.hass.config.as_dict()["latitude"]

    @property
    def lon(self) -> float:
        if "VIGIEAU_DEBUG" in os.environ:
            return 2.3332
        return self.hass.config.as_dict()["longitude"]

    async def update_method(self):
        """Fetch data from API endpoint."""
        try:
            _LOGGER.debug(
                f"Calling update method, {len(self._listeners)} listeners subscribed"
            )
            if "VIGIEAU_APIFAIL" in os.environ:
                raise UpdateFailed(
                    "Failing update on purpose to test state restoration"
                )
            _LOGGER.debug("Starting collecting data")
            client = await self.async_client()

            (street, city_code) = await self.fetch_street_and_insee_code()
            encoded_street = urllib.parse.quote_plus(street)

            # TODO(kamaradclimber): there 4 supported profils: particulier, entreprise, collectivite and exploitation
            url = f"{BASE_URL}/reglementation?lat={self.lat}&lon={self.lon}&commune={city_code}&profil=particulier"
            _LOGGER.debug(f"Requesting restrictions from {url}")
            r = await client.get(url)
            if not r.is_success:
                raise UpdateFailed(f"Failed fetching vigieau data: {r.text}")
            data = r.json()
            if "VIGIEAU_DEBUG" in os.environ:
                data = DEBUG_DATA
            _LOGGER.debug(f"Data fetched from vigieau: {data}")

            for usage in data["usages"]:
                found = False
                for usage_id in SENSOR_DEFINITIONS:
                    if re.search(
                        SENSOR_DEFINITIONS[usage_id]["match"],
                        usage["usage"],
                        re.IGNORECASE,
                    ):
                        found = True
                if not found:
                    _LOGGER.warn(
                        f"The following restriction is unknown from this integration, please report it as an issue: {usage['usage']}"
                    )

            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class AlertLevelEntity(CoordinatorEntity, SensorEntity):
    """Expose the alert level for the location"""

    def __init__(self, coordinator: VigieauAPICoordinator, hass: HomeAssistant):
        super().__init__(coordinator)
        self.hass = hass
        self._attr_name = "Alert level"
        self._attr_native_value = None
        self._attr_state_attributes = None

    @property
    def unique_id(self) -> str:
        return f"sensor-vigieau-{self.coordinator.lat}-{self.coordinator.lon}-{self._attr_name}"

    def enrich_attributes(self, data: dict, key_source: str, key_target: str):
        if key_source in data:
            self._attr_state_attributes = self._attr_state_attributes or {}
            if key_source in data:
                self._attr_state_attributes[key_target] = data[key_source]

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug(f"Receiving an update for {self.unique_id} sensor")
        if not self.coordinator.last_update_success:
            _LOGGER.debug("Last coordinator failed, assuming state has not changed")
            return
        self._attr_native_value = self.coordinator.data["niveauAlerte"]

        self._attr_icon = {
            "vigilance": "mdi:water-check",
            "alerte": "mdi:water-alert",
            "alerte_renforcee": "mdi:water-remove",
            "crise": "mdi:water-off",
        }[self._attr_native_value.lower()]

        self.enrich_attributes(self.coordinator.data, "cheminFichier", "source")
        self.enrich_attributes(
            self.coordinator.data, "cheminFichierArreteCadre", "source2"
        )

        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "Vigieau")}, "name": "Vigieau"}

    @property
    def state_attributes(self):
        return self._attr_state_attributes


class UsageRestrictionEntity(CoordinatorEntity, SensorEntity):
    """Expose a restriction for a given usage"""

    def __init__(
        self, coordinator: VigieauAPICoordinator, hass: HomeAssistant, usage_id: str
    ):
        super().__init__(coordinator)
        self.hass = hass
        self._usage_id = usage_id
        self._attr_name = f"{usage_id}_restrictions"  # temporary
        self._attr_native_value = None
        self._attr_state_attributes = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._config = SENSOR_DEFINITIONS[usage_id]

    @property
    def unique_id(self) -> str:
        return f"sensor-vigieau-{self.coordinator.lat}-{self.coordinator.lon}-{self._usage_id}"

    def enrich_attributes(self, usage: dict, key_source: str, key_target: str):
        if key_source in usage:
            self._attr_state_attributes = self._attr_state_attributes or {}
            self._attr_state_attributes[key_target] = usage[key_source]

    @property
    def icon(self):
        return self._config.get("icon", None)

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug(f"Receiving an update for {self.unique_id} sensor")
        if not self.coordinator.last_update_success:
            _LOGGER.debug("Last coordinator failed, assuming state has not changed")
            return
        for usage in self.coordinator.data["usages"]:
            if re.search(self._config["match"], usage["usage"], re.IGNORECASE):
                self._attr_name = usage["usage"]
                if self._attr_native_value != usage["niveauRestriction"]:
                    _LOGGER.debug(
                        f"Setting native value to {usage['niveauRestriction']}"
                    )
                self._attr_native_value = usage["niveauRestriction"]
                self.enrich_attributes(usage, "details", "details")
                self.enrich_attributes(usage, "thematique", "thematique")
                self.enrich_attributes(usage, "heureDebut", "heureDebut")
                self.enrich_attributes(usage, "heureFin", "heureFin")

        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "Vigieau")}, "name": "Vigieau"}

    @property
    def state_attributes(self):
        return self._attr_state_attributes
