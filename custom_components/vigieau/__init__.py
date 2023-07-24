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
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.components.sensor import RestoreSensor, SensorEntity
from .const import BASE_URL, DOMAIN, DEBUG_DATA, SENSOR_DEFINITIONS, CONF_INSEE_CODE, CONF_CITY, NAME, SENSOR_DEFINITIONS, VigieEauSensorEntityDescription

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
        self._insee_city_code = None
        if "VIGIEAU_FORCED_INSEE_CITY_CODE" in os.environ:
            self._insee_city_code = os.environ["VIGIEAU_FORCED_INSEE_CITY_CODE"]

    # FIXME(kamaradclimber): why so much complexity to get the client? We could simply add it in the constructor
    async def async_client(self):
        if not self._async_client:
            self._async_client = get_async_client(self.hass, verify_ssl=True)
        return self._async_client

    def _timezone(self):
        timezone = self.hass.config.as_dict()["time_zone"]
        return tz.gettz(timezone)

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

            city_code= self.config[CONF_INSEE_CODE]

            # TODO(kamaradclimber): there 4 supported profils: particulier, entreprise, collectivite and exploitation
            url = f"{BASE_URL}/reglementation?commune={city_code}&profil=particulier"
            _LOGGER.debug(f"Requesting restrictions from {url}")
            r = await client.get(url)
            if (
                r.status_code == 404
                and "message" in r.json()
                and re.match("Aucune zone.+en vigueur", r.json()["message"])
            ):
                _LOGGER.debug(f"Vigieau replied with no restriction, faking data")
                data = {"usages": [], "niveauAlerte": "vigilance"}
            elif r.is_success:
                data = r.json()
            else:
                raise UpdateFailed(f"Failed fetching vigieau data: {r.text}")
            if "VIGIEAU_DEBUG" in os.environ:
                data = DEBUG_DATA
            _LOGGER.debug(f"Data fetched from vigieau: {data}")

            for usage in data["usages"]:
                found = False
                for sensor  in SENSOR_DEFINITIONS:
                    match=sensor.match.split("#")
                    for matcher in match:
                        if matcher !="" and re.search(
                            matcher,
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

    def __init__(self, coordinator: VigieauAPICoordinator, hass: HomeAssistant, config_entry:ConfigEntry):
        super().__init__(coordinator)
        self.hass = hass
        self._attr_name = f"Alert level-{config_entry.data.get(CONF_CITY)}"
        self._attr_native_value = None
        self._attr_state_attributes = None
        self._attr_unique_id=f"sensor-vigieau-{self._attr_name}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_CITY)}"
        self._attr_device_info = DeviceInfo(
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_CITY)}")
            },
            manufacturer=f"{NAME}-{config_entry.data.get(CONF_CITY)}",
            model=NAME
        )

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
            "alerte_renforcée": "mdi:water-remove",
            "crise": "mdi:water-off",
        }[self._attr_native_value.lower().replace(' ','_')]

        self.enrich_attributes(self.coordinator.data, "cheminFichier", "source")
        self.enrich_attributes(
            self.coordinator.data, "cheminFichierArreteCadre", "source2"
        )

        restrictions = [
            restriction["usage"] for restriction in self.coordinator.data["usages"]
        ]
        self._attr_state_attributes = self._attr_state_attributes or {}
        self._attr_state_attributes["current_restrictions"] = ", ".join(restrictions)

        self.async_write_ha_state()


    @property
    def state_attributes(self):
        return self._attr_state_attributes


class UsageRestrictionEntity(CoordinatorEntity, SensorEntity):
    """Expose a restriction for a given usage"""
    entity_description: VigieEauSensorEntityDescription
    def __init__(
        self, coordinator: VigieauAPICoordinator, hass: HomeAssistant, usage_id: str, config_entry:ConfigEntry, description:VigieEauSensorEntityDescription
    ):
        super().__init__(coordinator)
        self.hass = hass
        self._attr_name = f"{description.name}_restrictions_{config_entry.data.get(CONF_CITY)}"
        self._attr_native_value = None
        self._attr_state_attributes = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._config = description
        self._attr_unique_id=f"sensor-vigieau-{self._attr_name}-{config_entry.data.get(CONF_INSEE_CODE)}"
        self._attr_device_info = DeviceInfo(
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_CITY)}")
            },
            manufacturer=f"{NAME}-{config_entry.data.get(CONF_CITY)}",
            model=NAME
        )

    def enrich_attributes(self, usage: dict, key_source: str, key_target: str):
        if key_source in usage:
            self._attr_state_attributes = self._attr_state_attributes or {}
            self._attr_state_attributes[key_target] = usage[key_source]

    @property
    def icon(self):
        return self._config.icon

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug(f"Receiving an update for {self.unique_id} sensor")
        if not self.coordinator.last_update_success:
            _LOGGER.debug("Last coordinator failed, assuming state has not changed")
            return
        self._restrictions = []
        self._attr_name = self._config.name
        for usage in self.coordinator.data["usages"]:
            match=self._config.match.split("#")
            for matcher in match:
                if matcher!="" and re.search(matcher, usage["usage"], re.IGNORECASE):
                    self._attr_state_attributes = self._attr_state_attributes or {}
                    self._attr_state_attributes[f"Categorie: {usage['usage']}"] = usage[
                        "niveauRestriction"
                    ]
                    self._restrictions.append(usage["niveauRestriction"])

                    self.enrich_attributes(
                        usage, "details", f"{usage['usage']} (details)"
                    )
                    self.enrich_attributes(
                        usage, "heureDebut", f"{usage['usage']} (heureDebut)"
                    )
                    self.enrich_attributes(
                        usage, "heureFin", f"{usage['usage']} (heureFin)"
                    )

        self._attr_native_value = self.compute_native_value()
        self.async_write_ha_state()

    def compute_native_value(self) -> Optional[str]:
        """This method extract the most relevant restriction level to display as aggregate"""
        if len(self._restrictions) == 0:
            return "Aucune restriction"
        if "Interdiction sur plage horaire" in self._restrictions:
            return "Interdiction sur plage horaire"
        if "Interdiction sauf exception" in self._restrictions:
            return "Interdiction sauf exception"
        if "Interdiction" in self._restrictions:
            return "Interdiction"
        return None

    @property
    def state_attributes(self):
        return self._attr_state_attributes
