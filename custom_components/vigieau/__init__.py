import os
import re
import json
import urllib.parse
import logging
from datetime import timedelta, time as dt_time
from dateutil import tz
from itertools import dropwhile, takewhile
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo
import aiohttp

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    Platform,
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
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

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
    LEGACY_HA_COORD,
    LOCATION_MODES,
    NAME,
    SENSOR_DEFINITIONS,
    VigieEauSensorEntityDescription,
    LEVEL_COLORS,
)


_LOGGER = logging.getLogger(__name__)

MIGRATED_FROM_VERSION_1 = "migrated_from_version_1"
MIGRATED_FROM_VERSION_3 = "migrated_from_version_3"
MIGRATED_FROM_VERSION_5 = "migrated_from_version_5"
MIGRATED_FROM_VERSION_6 = "migrated_from_version_6"

STATE_NO_RESTRICTION = "no_restriction"
STATE_TIME_BASED_BAN = "time_based_ban"
STATE_BAN_WITH_EXCEPTIONS = "ban_with_exceptions"
STATE_BAN = "ban"
STATE_BAN_EXCEPT_STRICTLY_NECESSARY = "ban_except_strictly_necessary"
STATE_WATER_WITHDRAWAL_REDUCTION = "water_withdrawal_reduction"
STATE_ERROR_CHECK_DECREE = "error_check_decree"
STATE_ALLOWED_EXCEPT_SPECIFIC_DECREE = "allowed_except_specific_decree"
STATE_AWARENESS = "awareness"
STATE_REDUCTION = "reduction"

NON_RESTRICTED_STATES = {
    STATE_NO_RESTRICTION,
    STATE_ALLOWED_EXCEPT_SPECIFIC_DECREE,
    STATE_AWARENESS,
}


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

        hass.config_entries.async_update_entry(
            config_entry, data=new, version=3)
    if config_entry.version == 2:
        _LOGGER.warn("config entry version is 2, migrating to version 3")
        new = {**config_entry.data}
        insee_code, city_name, lat, lon = await get_insee_code_fromcoord(hass)
        new[CONF_LATITUDE] = lat
        new[CONF_LONGITUDE] = lon
        hass.config_entries.async_update_entry(
            config_entry, data=new, version=3)

    if config_entry.version == 3:
        _LOGGER.warn("config entry version is 3, migrating to version 4")
        new = {**config_entry.data}
        insee_code, city_name, lat, lon = await get_insee_code_fromcoord(hass)
        new[MIGRATED_FROM_VERSION_3] = True
        hass.config_entries.async_update_entry(
            config_entry, data=new, version=4)
    if config_entry.version == 4:
        _LOGGER.warn("config entry version is 4, migrating to version 5")
        new = {**config_entry.data}
        new[CONF_ZONE_TYPE] = "SUP"
        hass.config_entries.async_update_entry(
            config_entry, data=new, version=5)
    if config_entry.version == 5:
        _LOGGER.warn("config entry version is 5, migrating to version 6")
        new = {**config_entry.data}
        new[MIGRATED_FROM_VERSION_5] = True
        hass.config_entries.async_update_entry(
            config_entry, data=new, version=6)
    if config_entry.version == 6:
        _LOGGER.warn("config entry version is 6, migrating to version 7")
        new = {**config_entry.data}
        new[CONF_FOLLOW_HA_COORDS] = new[CONF_LOCATION_MODE] in (HA_COORD, LEGACY_HA_COORD)
        new[MIGRATED_FROM_VERSION_6] = True
        hass.config_entries.async_update_entry(
            config_entry, data=new, version=7)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    # here we store the coordinator for future access
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
        hass.data[DOMAIN][entry.entry_id]["vigieau_coordinator"] = VigieauAPICoordinator(
            hass, dict(entry.data), entry.entry_id
        )

    # will make sure async_setup_entry from sensor.py and binary_sensor.py are called
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )

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
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
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
                    continue  # one more try
                self._location = location
                city_code = location[CONF_INSEE_CODE]
                lat = location[CONF_LATITUDE]
                long = location[CONF_LONGITUDE]
                zone_type = location[CONF_ZONE_TYPE]

                if self.config[CONF_FOLLOW_HA_COORDS] and self.changed_location(location):
                    _LOGGER.info(
                        "Coordinates of HA instance changed since last update, will look for vigieau data accordingly")
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
                    if sensor.match(usage):
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
        # we use 4 decimals which corresponds to ~10m (it depends on the latitude actually but should be good enough)
        precision = 4
        return round(ha_lon, precision) != round(last_lon, precision) or round(ha_lat, precision) != round(last_lat, precision)

    async def update_config_based_on_location(self, current_location) -> None:
        """
        Updates the entity config based on location
        """
        try:
            insee_code, city_name, lat, lon = await get_insee_code_fromcoord(self.hass)
        except ValueError as e:
            _LOGGER.warning(
                f"Impossible to fetch insee code from new location: {e}")
            return
        await self._custom_store.async_save({CONF_LATITUDE: lat, CONF_LONGITUDE: lon, CONF_INSEE_CODE: insee_code, CONF_CITY: city_name, CONF_ZONE_TYPE: current_location[CONF_ZONE_TYPE]})
        _LOGGER.info(f"New location detected {city_name} ({insee_code})")


def zone_type_to_str(zone_type: str) -> str:
    return zone_type or "unknown"


def _parse_time_str(time_str: str) -> Optional[dt_time]:
    """Parse time string from API (HH:MM or HHhMM) into datetime.time"""
    if not time_str:
        return None
    time_str = time_str.strip()
    match = re.match(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        return dt_time(int(match.group(1)), int(match.group(2)))
    match = re.match(r'(\d{1,2})h(\d{2})', time_str)
    if match:
        return dt_time(int(match.group(1)), int(match.group(2)))
    match = re.match(r'(\d{1,2})h\s*$', time_str)
    if match:
        hour = int(match.group(1))
        if hour == 24:
            hour = 0
        if hour > 23:
            return None
        return dt_time(hour, 0)
    return None


_TIME_CLASSIFICATION_PATTERNS = [r"interdiction sur plage horaire", r"(?:interdiction|interdit).*\d+\s*h"]


def classify_restrictions(restrictions):
    """Classify a list of restriction descriptions into a restriction level.

    Returns (level_string, is_time_based).
    level_string is None when the restrictions cannot be interpreted.
    """
    def any_restriction_match(matcher):
        r = re.compile(matcher, re.IGNORECASE)
        for restriction in restrictions:
            if r.search(restriction):
                return True
        return False

    def has_time_based_interdiction():
        for pattern in _TIME_CLASSIFICATION_PATTERNS:
            r = re.compile(pattern, re.IGNORECASE)
            for restriction in restrictions:
                if r.search(restriction):
                    return True
        return False

    def has_non_time_interdiction():
        r_inter = re.compile(r"interdiction", re.IGNORECASE)
        r_time = re.compile("|".join(_TIME_CLASSIFICATION_PATTERNS), re.IGNORECASE)
        for restriction in restrictions:
            if r_inter.search(restriction) and not r_time.search(restriction):
                return True
        return False

    if len(restrictions) == 0:
        return (STATE_NO_RESTRICTION, False)

    if not has_non_time_interdiction() and has_time_based_interdiction():
        return (STATE_TIME_BASED_BAN, True)

    if any_restriction_match("interdi.*sauf"):
        return (STATE_BAN_WITH_EXCEPTIONS, False)
    if any_restriction_match("à l\u2019exception"):
        return (STATE_BAN_WITH_EXCEPTIONS, False)
    if any_restriction_match("à l\u2019exclusion"):
        return (STATE_BAN_WITH_EXCEPTIONS, False)
    if any_restriction_match("Interdit.*dès lors"):
        return (STATE_BAN_WITH_EXCEPTIONS, False)
    if any_restriction_match("Interdiction"):
        return (STATE_BAN, False)
    if any_restriction_match("interdit"):
        return (STATE_BAN, False)
    if any_restriction_match("interdiction"):
        return (STATE_BAN, False)
    if any_restriction_match("limitation au strict nécessaire"):
        return (STATE_BAN_EXCEPT_STRICTLY_NECESSARY, False)
    if any_restriction_match("Réduction de prélèvement"):
        return (STATE_WATER_WITHDRAWAL_REDUCTION, False)
    if any_restriction_match("Consulter l\u2019arrêté"):
        return (STATE_ERROR_CHECK_DECREE, False)
    if any_restriction_match("Se référer à l'arrêté de restriction en cours de validité."):
        return (STATE_ERROR_CHECK_DECREE, False)
    if any_restriction_match("Pas de restriction sauf arrêté spécifique."):
        return (STATE_ALLOWED_EXCEPT_SPECIFIC_DECREE, False)
    if any_restriction_match("Sensibiliser"):
        return (STATE_AWARENESS, False)
    if any_restriction_match("Sensibilisation"):
        return (STATE_AWARENESS, False)
    if any_restriction_match("il est demandé"):
        return (STATE_AWARENESS, False)
    if any_restriction_match("Réduction"):
        return (STATE_REDUCTION, False)
    if len(set(restrictions)) == 1:
        return (restrictions[0], False)
    return (None, False)


def extract_time_range(restrictions):
    """Extract a time range from restriction description strings.

    Returns (start_time, end_time) or None.
    Handles the "uniquement de X h à Y h" inversion (allowed window → restricted window).
    """
    for restriction in restrictions:
        match = re.search(r"(\d{1,2})\s*h.*?(\d{1,2})\s*h", restriction)
        if match:
            start_str = f"{match.group(1)}h"
            end_str = f"{match.group(2)}h"
            start_time = _parse_time_str(start_str)
            end_time = _parse_time_str(end_str)
            if start_time is not None and end_time is not None:
                # Overnight range with exception wording (sauf/except/uniquement)
                # describes the ALLOWED window. Swap to get the RESTRICTED window.
                if start_time > end_time and re.search(r"sauf|except|uniquement", restriction, re.IGNORECASE):
                    start_time, end_time = end_time, start_time
                return (start_time, end_time)
    return None


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
        self._attr_has_entity_name = True
        self._attr_translation_key = "alert_level_numeric" if numeric_state else "alert_level"
        self._attr_translation_placeholders = self.translation_placeholders()
        legacy_name = self.build_name()
        self._attr_name = None
        self._attr_native_value = None
        self._attr_state_attributes = None
        if MIGRATED_FROM_VERSION_1 in config_entry.data:
            self._attr_unique_id = "sensor-vigieau-Alert level"
        elif MIGRATED_FROM_VERSION_5 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{legacy_name}-{config_entry.data.get(CONF_INSEE_CODE)}"
        elif MIGRATED_FROM_VERSION_6:
            self._attr_unique_id = f"sensor-vigieau-{legacy_name}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_ZONE_TYPE)}"
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

    def translation_placeholders(self) -> dict[str, str]:
        data = self._config_entry.data
        if self.coordinator.location is not None:
            data = self.coordinator.location()
        return {"city": data.get(CONF_CITY)}

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug(f"Receiving an update for {self.unique_id} sensor")
        if not self.coordinator.last_update_success:
            _LOGGER.debug(
                "Last coordinator failed, assuming state has not changed")
            return
        self._attr_translation_placeholders = self.translation_placeholders()
        self._attr_device_info = self.build_device()
        self.numeric_state_value = self.coordinator.data["_numeric_state_value"]

        if self._numeric_state:
            self._attr_native_value = self.numeric_state_value
        else:
            niveauGravite = self.coordinator.data["niveauGravite"]
            self._attr_native_value = niveauGravite.replace("_", " ").capitalize()

        self._attr_icon = {
            0: "mdi:water-check",
            1: "mdi:water-minus",
            2: "mdi:water-alert",
            3: "mdi:water-remove",
            4: "mdi:water-off",
        }[self.numeric_state_value]
        self.enrich_attributes(self.coordinator.data,
                               "cheminFichier", "source")
        self.enrich_attributes(
            self.coordinator.data, "cheminFichierArreteCadre", "source2"
        )

        restrictions = [
            restriction["nom"] for restriction in self.coordinator.data["usages"]
        ]
        self._attr_state_attributes = self._attr_state_attributes or {}
        self._attr_state_attributes["current_restrictions"] = ", ".join(
            restrictions)
        self._attr_state_attributes["Couleur"] = LEVEL_COLORS[self.numeric_state_value]

        self.async_write_ha_state()

    @property
    def state_attributes(self):
        return self._attr_state_attributes


class RestrictionMixin:
    """Shared logic for restriction entities (string sensors and binary sensors)"""

    @property
    def state_attributes(self):
        return self._attr_state_attributes

    def build_device(self) -> DeviceInfo:
        data = self._config_entry.data
        return DeviceInfo(
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

    def compute_native_value(self) -> Optional[str]:
        """This method extract the most relevant restriction level to display as aggregate"""
        result, is_time_based = classify_restrictions(self._restrictions)
        self._native_is_time_based = is_time_based
        if result is None:
            report_data = json.dumps(
                {"insee code": self._config_entry.data.get(CONF_INSEE_CODE), "restrictions": self._restrictions},
                ensure_ascii=False,
            )
            _LOGGER.warning(
                f"The following restriction are hard to interpret by this integration, please report an issue with: {report_data}"
            )
        return result

    def _is_time_based(self) -> bool:
        return self._native_is_time_based

    def _extract_time_range_from_descriptions(self):
        return extract_time_range(self._restrictions)

    def _get_effective_time_ranges(self):
        ranges = []
        for name, (start_str, end_str) in self._time_restrictions.items():
            start = _parse_time_str(start_str)
            end = _parse_time_str(end_str)
            if start is not None and end is not None:
                ranges.append((start, end))
        if not ranges and self._extracted_time_range is not None:
            ranges.append(self._extracted_time_range)
        return ranges

    def _is_currently_restricted(self, now_time=None):
        if now_time is None:
            now_time = dt_util.now().time()
        for start_time, end_time in self._get_effective_time_ranges():
            if start_time <= end_time:
                if start_time <= now_time < end_time:
                    return True
            else:
                if now_time >= start_time or now_time < end_time:
                    return True
        return False

    def _update_dynamic_attributes(self):
        R = self._attr_state_attributes.get("restriction") if self._attr_state_attributes else None

        if self._native_is_time_based:
            now_time = dt_util.now().time()
            is_restricted = self._is_currently_restricted(now_time)
            time_ranges = self._get_effective_time_ranges()
            _LOGGER.debug(f"Dynamic attr for {self.unique_id}: time_based=True, now_time={now_time}, ranges={time_ranges}, is_restricted={is_restricted}, R={R}")
        elif R in NON_RESTRICTED_STATES:
            is_restricted = False
        else:
            is_restricted = True

        self._attr_state_attributes["currently_restricted"] = is_restricted

        if self._native_is_time_based:
            now = dt_util.now()
            now_time = now.time()
            ranges = self._get_effective_time_ranges()

            if ranges:
                start_time, end_time = ranges[0]
                start_dt = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
                end_dt = now.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)

                if start_dt <= now:
                    start_dt += timedelta(days=1)
                if end_dt <= now:
                    end_dt += timedelta(days=1)

                if start_time > end_time:
                    if is_restricted:
                        next_autorisation = end_dt
                        next_coupure = start_dt
                    else:
                        next_coupure = start_dt
                        next_autorisation = end_dt
                else:
                    if is_restricted:
                        next_autorisation = end_dt
                        next_coupure = start_dt
                    else:
                        next_coupure = start_dt
                        next_autorisation = end_dt

                self._attr_state_attributes["next_restriction_start"] = next_coupure.isoformat()
                self._attr_state_attributes["next_restriction_end"] = next_autorisation.isoformat()
        else:
            self._attr_state_attributes.pop("next_restriction_start", None)
            self._attr_state_attributes.pop("next_restriction_end", None)

    def _cancel_timer(self):
        if self._unsub_timer is not None:
            _LOGGER.debug(f"Cancelling timer for {getattr(self, 'unique_id', 'unknown')}")
            self._unsub_timer()
            self._unsub_timer = None

    def _schedule_next_time_update(self):
        now = dt_util.now()
        now_time = now.time()
        next_boundary = None
        ranges = self._get_effective_time_ranges()

        _LOGGER.debug(f"Schedule compute for {self.unique_id}: now={now.isoformat()}, now_time={now_time}, ranges={ranges}, time_restrictions={getattr(self, '_time_restrictions', {})}, extracted_range={getattr(self, '_extracted_time_range', None)}")

        for start_time, end_time in ranges:
            start_dt = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
            end_dt = now.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)

            _LOGGER.debug(f"Range raw: start_time={start_time}, end_time={end_time}, start_dt={start_dt}, end_dt={end_dt}")

            if start_dt <= now:
                start_dt += timedelta(days=1)
                _LOGGER.debug(f"start_dt adjusted to {start_dt} (was <= now)")
            if end_dt <= now:
                end_dt += timedelta(days=1)
                _LOGGER.debug(f"end_dt adjusted to {end_dt} (was <= now)")

            if start_time > end_time:
                if now_time >= start_time or now_time < end_time:
                    candidate = end_dt
                else:
                    candidate = start_dt
            else:
                candidate = min(start_dt, end_dt)

            _LOGGER.debug(f"Candidate for range {start_time}-{end_time}: {candidate.isoformat()}, start_dt={start_dt.isoformat()}, end_dt={end_dt.isoformat()}")

            if next_boundary is None or candidate < next_boundary:
                next_boundary = candidate

        if next_boundary is not None:
            _LOGGER.debug(f"Scheduling next attribute update for {self.unique_id} at {next_boundary.isoformat()} (tzinfo={next_boundary.tzinfo})")
            self._unsub_timer = async_track_point_in_time(
                self.hass,
                self._time_boundary_reached,
                next_boundary,
            )
        else:
            _LOGGER.debug(f"No next boundary to schedule for {self.unique_id}")

    @callback
    def _time_boundary_reached(self, now):
        _LOGGER.debug(f"Time boundary reached for {self.unique_id}, updating attributes. event_time={now}, system_time={dt_util.now().isoformat()}, timer_active={self._unsub_timer is not None}")
        self._update_dynamic_attributes()
        self._schedule_next_time_update()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        self._cancel_timer()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug(f"Receiving an update for {self.unique_id} sensor (timer_active={self._unsub_timer is not None})")
        if not self.coordinator.last_update_success:
            _LOGGER.debug(
                "Last coordinator failed, assuming state has not changed")
            return
        self._cancel_timer()
        self._attr_device_info = self.build_device()
        self._attr_state_attributes = self._attr_state_attributes or {}
        self._restrictions = []
        self._time_restrictions = {}
        self._extracted_time_range = None
        self._attr_translation_placeholders = {
            "city": self._config_entry.data.get(CONF_CITY)
        }
        for usage in self.coordinator.data["usages"]:
            if self._config.match(usage):
                self._attr_state_attributes = self._attr_state_attributes or {}
                restriction = usage.get("description")
                if restriction is None:
                    raise UpdateFailed(
                        "Restriction level is not specified"
                    )
                self._attr_state_attributes[
                    f"usage: {usage['nom']}"
                ] = restriction
                self._restrictions.append(restriction)

                self.enrich_attributes(
                    usage, "details", f"{usage['nom']} (details)"
                )
                if "heureFin" in usage and "heureDebut" in usage:
                    debut = usage["heureDebut"]
                    fin = usage["heureFin"]
                    debut_time = _parse_time_str(debut)
                    fin_time = _parse_time_str(fin)
                    # Overnight range with exception wording (sauf/except/uniquement)
                    # describes the ALLOWED window. Swap to get the RESTRICTED window.
                    if debut_time is not None and fin_time is not None and debut_time > fin_time and re.search(r"sauf|except|uniquement", restriction, re.IGNORECASE):
                        debut, fin = fin, debut
                    self._time_restrictions[usage["nom"]] = [debut, fin]

        if len(set([repr(r) for r in self._time_restrictions.values()])) == 1:
            restrictions = list(self._time_restrictions.values())[0]
            self._attr_state_attributes["start_time"] = restrictions[0]
            self._attr_state_attributes["end_time"] = restrictions[1]
        elif len(self._time_restrictions) > 0:
            _LOGGER.debug(
                f"There are {len(self._time_restrictions)} usage with time restrictions for this sensor, exposing info per usage"
            )
            for name in self._time_restrictions:
                self._attr_state_attributes[
                    f"{name} (start_time)"
                ] = self._time_restrictions[name][0]
                self._attr_state_attributes[
                    f"{name} (end_time)"
                ] = self._time_restrictions[name][1]

        if not self._time_restrictions:
            self._extracted_time_range = self._extract_time_range_from_descriptions()

        native_value = self.compute_native_value()
        self._attr_state_attributes["restriction"] = native_value
        self._update_dynamic_attributes()
        self._on_restrictions_updated(native_value)
        _LOGGER.debug(f"Coordinator update for {self.unique_id}: is_time_based={self._is_time_based()}, _native_is_time_based={self._native_is_time_based}, _time_restrictions={self._time_restrictions}, extracted_range={self._extracted_time_range}")
        if self._is_time_based():
            self._schedule_next_time_update()
        self.async_write_ha_state()

    def _on_restrictions_updated(self, native_value: str):
        """Hook for subclasses to update entity state after restriction data changes"""
        pass


class UsageRestrictionEntity(RestrictionMixin, CoordinatorEntity, SensorEntity):
    """Expose a restriction for a given usage as a string sensor"""

    entity_description: VigieEauSensorEntityDescription

    def __init__(
        self,
        coordinator: VigieauAPICoordinator,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        description: VigieEauSensorEntityDescription,
    ):
        super().__init__(coordinator)
        self.hass = hass
        self._config_entry = config_entry
        self._attr_has_entity_name = True
        self._attr_translation_key = f"{description.key}_restrictions"
        self._attr_translation_placeholders = {
            "city": config_entry.data.get(CONF_CITY)
        }
        legacy_name = (
            f"{description.name}_restrictions_{config_entry.data.get(CONF_CITY)}"
        )
        self._attr_name = None
        self._attr_native_value = None
        self._attr_state_attributes = None
        self._attr_entity_registry_enabled_default = False
        self._config = description
        self._unsub_timer = None
        self._native_is_time_based = False
        self._extracted_time_range = None
        if MIGRATED_FROM_VERSION_1 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{self._config.key}"
        elif MIGRATED_FROM_VERSION_3 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{legacy_name}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}"
        elif MIGRATED_FROM_VERSION_5 in config_entry.data:
            self._attr_unique_id = f"sensor-vigieau-{self._config.key}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}"
        else:
            self._attr_unique_id = f"sensor-vigieau-{self._config.key}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}-{config_entry.data.get(CONF_ZONE_TYPE)}"
        self._attr_device_info = self.build_device()

    @property
    def icon(self):
        return self._config.icon

    def _on_restrictions_updated(self, native_value: str):
        self._attr_native_value = native_value


class UsageRestrictionBinaryEntity(RestrictionMixin, CoordinatorEntity, BinarySensorEntity):
    """Expose a restriction for a given usage as a binary sensor (on=restricted)"""

    entity_description: VigieEauSensorEntityDescription

    def __init__(
        self,
        coordinator: VigieauAPICoordinator,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        description: VigieEauSensorEntityDescription,
    ):
        super().__init__(coordinator)
        self.hass = hass
        self._config_entry = config_entry
        self._attr_has_entity_name = True
        self._attr_translation_key = f"{description.key}_binary"
        self._attr_translation_placeholders = {
            "city": config_entry.data.get(CONF_CITY)
        }
        self._attr_name = None
        self._attr_is_on = False
        self._attr_state_attributes = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = description.commonly_used
        self._config = description
        self._unsub_timer = None
        self._native_is_time_based = False
        self._extracted_time_range = None
        self._attr_unique_id = f"binary_sensor-vigieau-{self._config.key}-{config_entry.data.get(CONF_INSEE_CODE)}-{config_entry.data.get(CONF_LATITUDE)}-{config_entry.data.get(CONF_LONGITUDE)}-{config_entry.data.get(CONF_ZONE_TYPE)}"
        self._attr_device_info = self.build_device()

    @property
    def is_on(self):
        return not self._attr_state_attributes.get("currently_restricted", True) if self._attr_state_attributes else True

    @property
    def icon(self):
        if self._attr_state_attributes and self._attr_state_attributes.get("currently_restricted"):
            return "mdi:water-off"
        return "mdi:water-check"
