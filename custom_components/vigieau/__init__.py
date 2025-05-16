import os
import re
import json
import urllib.parse
import logging
from datetime import timedelta, datetime
from dateutil import tz
from itertools import dropwhile, takewhile
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo
import aiohttp

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE, 
    CONF_LONGITUDE, 
    Platform, 
    STATE_ON
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory, DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.storage import Store

from .api import VigieauAPI, VigieauAPIError
from .config_flow import get_insee_code_fromcoord, SetupConfigFlow
from .const import (
    CONF_CITY,
    CONF_INSEE_CODE,
    CONF_LOCATION_MODE,
    CONF_ZONE_TYPE,
    CONF_FOLLOW_HA_COORDS,
    DEVICE_ID_KEY,
    DOMAIN,
    HA_COORD,
    LOCATION_MODES,
    NAME,
    SENSOR_DEFINITIONS,
    VigieEauSensorEntityDescription,
)


_LOGGER = logging.getLogger(__name__)

MIGRATED_FROM_VERSION_1 = "migrated_from_version_1"
MIGRATED_FROM_VERSION_3 = "migrated_from_version_3"
MIGRATED_FROM_VERSION_5 = "migrated_from_version_5"
MIGRATED_FROM_VERSION_6 = "migrated_from_version_6"


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    if config_entry.version == 1:
        _LOGGER.warn("config entry version is 1, migrating to version 2")
        new = {**config_entry.data}
        insee_code, city_name, lat, lon = await get_insee_code_fromcoord(hass)
        new[CONF_INSEE_CODE] = insee_code
        new[CONF_CITY] = city_name
        new[CONF_LOCATION_MODE] = HA_COORD
        new[
            DEVICE_ID_KEY
        ] = "Vigieau"  # hardcoded to match hardcoded id from version 0.3.9
        new[CONF_LATITUDE] = lat
        new[CONF_LONGITUDE] = lon
        new[MIGRATED_FROM_VERSION_1] = True
        _LOGGER.warn(
            f"Migration detected INSEE code for current HA instance is {insee_code} in {city_name}"
        )

        hass.config_entries.async_update_entry(config_entry, data=new, version=3)
    if config_entry.version == 2:
        _LOGGER.warn("config entry version is 2, migrating to version 3")
        new = {**config_entry.data}
        insee_code, city_name, lat, lon = await get_insee_code_fromcoord(hass)
        new[CONF_LATITUDE] = lat
        new[CONF_LONGITUDE] = lon
        hass.config_entries.async_update_entry(config_entry, data=new, version=3)

    if config_entry.version == 3:
        _LOGGER.warn("config entry version is 3, migrating to version 4")
        new = {**config_entry.data}
        insee_code, city_name, lat, lon = await get_insee_code_fromcoord(hass)
        new[MIGRATED_FROM_VERSION_3] = True
        hass.config_entries.async_update_entry(config_entry, data=new, version=4)
    if config_entry.version == 4:
        _LOGGER.warn("config entry version is 4, migrating to version 5")
        new = {**config_entry.data}
        new[CONF_ZONE_TYPE] = "SUP"
        hass.config_entries.async_update_entry(config_entry, data=new, version=5)
    if config_entry.version == 5:
        _LOGGER.warn("config entry version is 5, migrating to version 6")
        new = {**config_entry.data}
        new[MIGRATED_FROM_VERSION_5] = True
        hass.config_entries.async_update_entry(config_entry, data=new, version=6)
    if config_entry.version == 6:
        _LOGGER.warn("config entry version is 6, migrating to version 7")
        new = {**config_entry.data}
        new[CONF_FOLLOW_HA_COORDS] = new[CONF_LOCATION_MODE] == HA_COORD
        new[MIGRATED_FROM_VERSION_6] = True
        hass.config_entries.async_update_entry(config_entry, data=new, version=7)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    # here we store the coordinator for future access
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
        hass.data[DOMAIN][entry.entry_id]["vigieau_coordinator"] = VigieauAPICoordinator(
        hass, dict(entry.data), entry.entry_id
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

    STORE_VERSION = 1

    def __init__(self, hass, config: ConfigType, entry_id):
        super().__init__(
            hass,
            _LOGGER,
            name="vigieau api",  # for logging purpose
            update_interval=timedelta(hours=1),
            update_method=self.update_method,
        )
        self.config = config
        self.hass = hass
        self.config_entry_id = entry_id
    
        self._custom_store = Store(
            hass,
            version=self.STORE_VERSION,
            minor_version=0,
            key=f"vigieau_current_location_{self.config_entry_id}",
        )
        self._location = None

    def location(self) -> dict:
        """
        Return, if known, the up to date location data
        """
        if self._location is not None:
            return self._location
        return self.config

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

            while True:
                location = await self._custom_store.async_load()
                if location is None:
                    _LOGGER.debug("first save in storage")
                    # make first save in storage
                    await self._custom_store.async_save({CONF_LATITUDE: self.config[CONF_LATITUDE], CONF_LONGITUDE: self.config[CONF_LONGITUDE], CONF_INSEE_CODE: self.config[CONF_INSEE_CODE], CONF_CITY: self.config[CONF_CITY], CONF_ZONE_TYPE: self.config[CONF_ZONE_TYPE]})
                    continue # one more try
                self._location = location
                city_code = location[CONF_INSEE_CODE]
                lat = location[CONF_LATITUDE]
                long = location[CONF_LONGITUDE]
                zone_type = location[CONF_ZONE_TYPE]
                
                if self.config[CONF_FOLLOW_HA_COORDS] and self.changed_location(location):
                    _LOGGER.info("Coordinates of HA instance changed since last update, will look for vigieau data accordingly")
                    await self.update_config_based_on_location(location)
                    continue
                break

            session = async_get_clientsession(self.hass)
            vigieau = VigieauAPI(session)
            try:
                # TODO(kamaradclimber): there 4 supported profils: particulier, entreprise, collectivite and exploitation
                data = await vigieau.get_data(lat, long, city_code, "particulier", zone_type)
            except VigieauAPIError as e:
                raise UpdateFailed(f"Failed fetching vigieau data: {e.text}")

            for usage in data["usages"]:
                found = False
                for sensor in SENSOR_DEFINITIONS:
                    for matcher in sensor.matchers:
                        if re.search(
                            matcher,
                            usage["nom"] + "|" + usage['thematique'],
                            re.IGNORECASE,
                        ):
                            found = True
                if not found:
                    report_data = json.dumps(
                        {"insee code": city_code, "nom": usage["nom"]},
                        ensure_ascii=False,
                    )
                    _LOGGER.warn(
                        f"The following restriction is unknown from this integration, please report an issue with: {report_data}"
                    )
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        
    def changed_location(self, location: dict) -> bool:
        """
        Return true if the location of the HA instance changed _significantly_ (i.e more than a few meters)
        compared to the configuration of this instance.
        """
        ha_lon = self.hass.config.as_dict()["longitude"]
        ha_lat = self.hass.config.as_dict()["latitude"]
        last_lon = location[CONF_LONGITUDE]
        last_lat = location[CONF_LATITUDE]
        precision = 4 # we use 4 decimals which corresponds to ~10m (it depends on the latitude actually but should be good enough)
        return round(ha_lon, precision) != round(last_lon, precision) or round(ha_lat, precision) != round(last_lat, precision)
    
    async def update_config_based_on_location(self, current_location) -> None:
        """
        Updates the entity config based on location
        """
        try:
            insee_code, city_name, lat, lon = await get_insee_code_fromcoord(self.hass)
        except ValueError as e:
            _LOGGER.warning(f"Impossible to fetch insee code from new location: {e}")
            return
        await self._custom_store.async_save({CONF_LATITUDE: lat, CONF_LONGITUDE: lon, CONF_INSEE_CODE: insee_code, CONF_CITY: city_name, CONF_ZONE_TYPE: current_location[CONF_ZONE_TYPE]})
        _LOGGER.info(f"New location detected {city_name} ({insee_code})")
        

def zone_type_to_str(zone_type: str) -> str:
    names = {
        "SUP": "Eaux de surface",
        "AEP": "Alimentation en eau potable",
        "SOU": "Eaux souterraines",
    }
    return names.get(zone_type, "Zone inconnue")

class AlertLevelEntity(CoordinatorEntity, SensorEntity):
    """Expose the alert level for the location"""

    def __init__(
        self,
        coordinator: VigieauAPICoordinator,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        numeric_state: bool,
    ):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._numeric_state = numeric_state
        self.hass = hass
        self._attr_name = self.build_name()
        self._attr_native_value = None
        self._attr_state_attributes = None
        if MIGRATED_FROM_VERSION_1 in config_entry.data:
            self._attr_unique_id = "sensor-vigieau-Alert level"
        elif MIGRATED_FROM_VERSION_5 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{self._attr_name}-{config_entry.data.get(CONF_INSEE_CODE)}"
        elif MIGRATED_FROM_VERSION_6:
            self._attr_unique_id = f"sensor-vigieau-{self._attr_name}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_ZONE_TYPE)}"
        else:
            self._attr_unique_id = f"sensor-vigieau-alert-{config_entry.entry_id}"

        if self._numeric_state:
            self._attr_unique_id += "-numeric"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_device_info = self.build_device()

    def enrich_attributes(self, data: dict, key_source: str, key_target: str):
        if key_source in data:
            self._attr_state_attributes = self._attr_state_attributes or {}
            if key_source in data:
                self._attr_state_attributes[key_target] = data[key_source]

    def build_device(self) -> DeviceInfo:
        data = self._config_entry.data
        if self.coordinator.location is not None:
            data = self.coordinator.location()
        return DeviceInfo(
            name=f"{NAME} {data.get(CONF_CITY)} {zone_type_to_str(data.get(CONF_ZONE_TYPE))}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    str(data.get(DEVICE_ID_KEY)),
                )
            },
            manufacturer=NAME,
            model=data.get(CONF_INSEE_CODE),
        )

    def build_name(self) -> str:
        data = self._config_entry.data
        if self.coordinator.location is not None:
            data = self.coordinator.location()
        name = f"Alert level in {data.get(CONF_CITY)}"
        if self._numeric_state:
            name += " (numeric)"
        return name

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug(f"Receiving an update for {self.unique_id} sensor")
        if not self.coordinator.last_update_success:
            _LOGGER.debug("Last coordinator failed, assuming state has not changed")
            return
        self._attr_name = self.build_name()
        self._attr_device_info = self.build_device()
        self.numeric_state_value = self.coordinator.data["_numeric_state_value"]

        if self._numeric_state:
            self._attr_native_value = self.numeric_state_value
        else:
            self._attr_native_value = self.coordinator.data["niveauGravite"]
            if self.numeric_state_value == 0:
                self._attr_native_value = "vigilance (pas de restriction)"

        self._attr_icon = {
            0: "mdi:water-check",
            1: "mdi:water-alert",
            2: "mdi:water-remove",
            3: "mdi:water-off",
        }[self.numeric_state_value]

        self.enrich_attributes(self.coordinator.data, "cheminFichier", "source")
        self.enrich_attributes(
            self.coordinator.data, "cheminFichierArreteCadre", "source2"
        )

        restrictions = [
            restriction["nom"] for restriction in self.coordinator.data["usages"]
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
        self,
        coordinator: VigieauAPICoordinator,
        hass: HomeAssistant,
        usage_id: str,
        config_entry: ConfigEntry,
        description: VigieEauSensorEntityDescription,
    ):
        super().__init__(coordinator)
        self.hass = hass
        self._config_entry = config_entry
        # naming the attribute very early before it's updated by first api response is a hack
        # to make sure we have a decent entity_id selected by home assistant
        self._attr_name = (
            f"{description.name}_restrictions_{config_entry.data.get(CONF_CITY)}"
        )
        self._attr_native_value = None
        self._attr_state_attributes = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._config = description
        if MIGRATED_FROM_VERSION_1 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{self._config.key}"
        elif MIGRATED_FROM_VERSION_3 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{self._attr_name}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}"
        elif MIGRATED_FROM_VERSION_5 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{self._config.key}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}"
        else:
            self._attr_unique_id = f"sensor-vigieau-{self._config.key}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}-{config_entry.data.get(CONF_ZONE_TYPE)}"
        self._attr_device_info = self.build_device()

    def build_device(self) -> DeviceInfo:
        data = self._config_entry.data
        if self.coordinator.location is not None:
            data = self.coordinator.location()
        return DeviceInfo(
            name=f"{NAME} {data.get(CONF_CITY)} {zone_type_to_str(data.get(CONF_ZONE_TYPE))}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    str(data.get(DEVICE_ID_KEY)),
                )
            },
            manufacturer=NAME,
            model=data.get(CONF_INSEE_CODE),
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
        self._attr_device_info = self.build_device()
        self._attr_state_attributes = self._attr_state_attributes or {}
        self._restrictions = []
        self._time_restrictions = {}
        self._attr_name = str(self._config.name)
        for usage in self.coordinator.data["usages"]:
            for matcher in self._config.matchers:
                fully_qualified_usage = usage["nom"] + "|" + usage['thematique']
                if re.search(matcher, fully_qualified_usage, re.IGNORECASE):
                    self._attr_state_attributes = self._attr_state_attributes or {}
                    restriction = usage.get("description")
                    if restriction is None:
                        raise UpdateFailed(
                            "Restriction level is not specified"
                        )
                    self._attr_state_attributes[
                        f"Categorie: {usage['nom']}"
                    ] = restriction
                    self._restrictions.append(restriction)

                    self.enrich_attributes(
                        usage, "details", f"{usage['nom']} (details)"
                    )
                    if "heureFin" in usage and "heureDebut" in usage:
                        self._time_restrictions[usage["nom"]] = [
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

        def any_restriction_match(matcher):
            r = re.compile(matcher, re.IGNORECASE)
            for restriction in self._restrictions:
                if r.search(restriction):
                    return True
            return False

        if len(self._restrictions) == 0:
            return "Aucune restriction"
        if any_restriction_match("interdiction sur plage horaire"):
            return "Interdiction sur plage horaire"
        if any_restriction_match("interdi.*sauf"):
            return "Interdiction sauf exception"
        if any_restriction_match("à l’exception"):
            return "Interdiction sauf exception"
        if any_restriction_match("à l’exclusion"):
            return "Interdiction sauf exception"
        if any_restriction_match("Interdit.*dès lors"):
            return "Interdiction sauf exception"
        if any_restriction_match("Interdiction"):
            return "Interdiction"
        if any_restriction_match("interdit"):
            return "Interdiction"
        if any_restriction_match("interdiction"):
            return "Interdiction"
        if any_restriction_match("limitation au strict nécessaire"):
            return "Interdiction sauf strict nécessaire"
        if any_restriction_match("Réduction de prélèvement"):
            return "Réduction de prélèvement"
        if any_restriction_match("Consulter l’arrêté"):
            return "Erreur: consulter l'arrêté"
        if any_restriction_match("Se référer à l'arrêté de restriction en cours de validité."):
            return "Erreur: consulter l'arrêté"
        if any_restriction_match("Pas de restriction sauf arrêté spécifique."):
            return "Autorisé sauf exception"
        if any_restriction_match("Sensibiliser"):
            return "Sensibilisation"
        if any_restriction_match("Sensibilisation"):
            return "Sensibilisation"
        if len(self._restrictions) == 1:
            return self._restrictions[0]
        _LOGGER.warn(f"Restrictions are hard to interpret: {self._restrictions}")
        return None

    @property
    def state_attributes(self):
        return self._attr_state_attributes
