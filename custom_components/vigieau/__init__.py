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

    async def fetch_insee_code(self) -> str:
        if self._insee_city_code is not None:
            return self._insee_city_code
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
                f"Data received from api-adresse.data.gouv.fr is empty for those coordinates: ({self.lat}, {self.lon}). Either coordinates are not located in France or the governement geocoding database has no record for them."
            )
            raise UpdateFailed(
                "Impossible to find approximate address of the current HA instance. API returned no result."
            )
        properties = data["features"][0]["properties"]
        return properties["citycode"]

    @property
    def lat(self) -> float:
        if "VIGIEAU_DEBUG_LOC_LAT" in os.environ:
            return float(os.environ["VIGIEAU_DEBUG_LOC_LAT"])
        return self.hass.config.as_dict()["latitude"]

    @property
    def lon(self) -> float:
        if "VIGIEAU_DEBUG_LOC_LONG" in os.environ:
            return float(os.environ["VIGIEAU_DEBUG_LOC_LONG"])
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

            city_code = await self.fetch_insee_code()

            # TODO(kamaradclimber): there 4 supported profils: particulier, entreprise, collectivite and exploitation
            url = f"{BASE_URL}/reglementation?lat={self.lat}&lon={self.lon}&commune={city_code}&profil=particulier"
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
                for usage_id in SENSOR_DEFINITIONS:
                    for i in range(10):
                        if f"match{i}" in SENSOR_DEFINITIONS[usage_id] and re.search(
                            SENSOR_DEFINITIONS[usage_id][f"match{i}"],
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
        return f"sensor-vigieau-{self._attr_name}"

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
        }[self._attr_native_value.lower().replace(" ", "_")]

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
        return f"sensor-vigieau-{self._usage_id}"

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

        self._attr_state_attributes = self._attr_state_attributes or {}
        self._restrictions = []
        self._attr_name = self._config["name"]
        self._time_restrictions = {}
        for usage in self.coordinator.data["usages"]:
            for i in range(10):
                if f"match{i}" in self._config and re.search(
                    self._config[f"match{i}"], usage["usage"], re.IGNORECASE
                ):
                    self._attr_state_attributes = self._attr_state_attributes or {}
                    restriction = usage.get("niveauRestriction", usage.get("erreur"))
                    if restriction is None:
                        raise UpdateFailed(
                            "Restriction level is not specified and API does not give any error ('erreur' field)"
                        )
                    self._attr_state_attributes[
                        f"Categorie: {usage['usage']}"
                    ] = restriction
                    self._restrictions.append(restriction)
                    if "niveauRestriction" not in usage:
                        _LOGGER.warn(
                            f"{usage['usage']} misses 'niveauRestriction' key, using 'erreur' key as a fallback"
                        )

                    self.enrich_attributes(
                        usage, "details", f"{usage['usage']} (details)"
                    )
                    if "heureFin" in usage and "heureDebut" in usage:
                        self._time_restrictions[usage["usage"]] = [
                            usage["heureDebut"],
                            usage["heureFin"],
                        ]

        # we only want to add those attributes if they are not ambiguous
        if len(set([repr(r) for r in self._time_restrictions.values()])) == 1:
            restrictions = list(self._time_restrictions.values())[0]
            self._attr_state_attributes["heureDebut"] = restrictions[0]
            self._attr_state_attributes["heureFin"] = restrictions[1]
        elif len(self._time_restrictions) > 0:
            _LOGGER.debug(
                f"There are {len(self._time_restrictions)} usage with time restrictions for this sensor, exposing info per usage"
            )
            for name in self._time_restrictions:
                self._attr_state_attributes[
                    f"{name} (heureDebut)"
                ] = self._time_restrictions[name][0]
                self._attr_state_attributes[
                    f"{name} (heureFin)"
                ] = self._time_restrictions[name][1]

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
        if "Consulter l’arrêté" in self._restrictions:
            return "Erreur: consulter l'arreté"
        return None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "Vigieau")}, "name": "Vigieau"}

    @property
    def state_attributes(self):
        return self._attr_state_attributes
