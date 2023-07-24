import logging
from typing import Any, Optional
import voluptuous as vol
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from .api import INSEEAPI, ADRESSEAPI
from .const import DOMAIN, CONF_LOCATION_MODE, LOCATION_MODES, HA_COORD, ZIP_CODE, CONF_INSEE_CODE, CONF_CODE_POSTAL, CONF_CITY

_LOGGER = logging.getLogger(__name__)

# Description of the config flow:
# async_step_user is called when user starts to configure the integration
# we follow with a flow of form/menu
# eventually we call async_create_entry with a dictionnary of data
# HA calls async_setup_entry with a ConfigEntry which wraps this data (defined in __init__.py)
# in async_setup_entry we call hass.config_entries.async_forward_entry_setups to setup each relevant platform (sensor in our case)
# HA calls async_setup_entry from sensor.py

LOCATION_SCHEMA= vol.Schema(
{
    vol.Required(CONF_LOCATION_MODE, default=HA_COORD):vol.In(LOCATION_MODES)
}
)

ZIPCODE_SCHEMA = vol.Schema({vol.Required(CONF_CODE_POSTAL, default=""): cv.string})

async def get_insee_code_fromzip(hass: HomeAssistant, data: dict) -> None:
    """Get Insee code from zip code"""
    session = async_get_clientsession(hass)
    try:
        client = INSEEAPI(session)
        return await client.get_data(data)
    except ValueError as exc:
        raise exc

async def get_insee_code_fromcoord(hass: HomeAssistant) -> None:
    """Get Insee code from zip code"""
    session = async_get_clientsession(hass)
    try:
        client = ADRESSEAPI(session)
        lon=hass.config.as_dict()["longitude"]
        lat= hass.config.as_dict()["latitude"]
        return await client.get_data(lat, lon)
    except ValueError as exc:
        raise exc

def _build_place_key(city) -> str:
    return f"{city['code']};{city['nom']}"

class SetupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    def __init__(self):
        """Initialize"""
        self.data = {}
        self.city_insee = []

    @callback
    def _show_setup_form(self, step_id=None, user_input=None, schema=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors or {},
        )
    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        """Called once with None as user_input, then a second time with user provided input"""
        errors={}
        _LOGGER.debug("Launching configuration")
        if user_input is not None:
            if user_input[CONF_LOCATION_MODE]== HA_COORD:
                try:
                    city_infos= await get_insee_code_fromcoord(self.hass)
                except ValueError:
                    errors["base"] = "noinsee"
                if not errors:
                    self.data[CONF_INSEE_CODE] = city_infos[0]
                    self.data[CONF_CITY] = city_infos[1]
                    return await self.async_step_location(user_input= self.data)
            elif user_input[CONF_LOCATION_MODE]== ZIP_CODE:
                self.data=user_input
                return await self.async_step_location()

        return self._show_setup_form("user",user_input,LOCATION_SCHEMA, errors)

    async def async_step_location(self, user_input=None):
            """Handle location step"""
            errors = {}
            _LOGGER.debug("in async_step_location !!")
            if user_input is not None:
                city_insee = user_input.get(CONF_INSEE_CODE)
                if not city_insee:
                    # get INSEE Code
                    try:
                        self.city_insee = await get_insee_code_fromzip(
                            self.hass, user_input[CONF_CODE_POSTAL]
                        )
                    except ValueError:
                        errors["base"] = "noinsee"
                    if not errors:
                        return await self.async_step_multilocation()
                    else:
                        return self._show_setup_form(
                            "location", user_input, ZIPCODE_SCHEMA, errors
                        )
                return self.async_create_entry(title="vigieau", data=self.data)
            return self._show_setup_form("location", None, ZIPCODE_SCHEMA, errors)

    async def async_step_multilocation(self, user_input=None):
        """Handle location step"""
        errors = {}
        locations_for_form = {}
        for city in self.city_insee:
            locations_for_form[_build_place_key(city)] = f"{city['nom']}"

        if not user_input:
            if len(self.city_insee) > 1:
                return self.async_show_form(
                    step_id="multilocation",
                    data_schema=vol.Schema(
                        {
                            vol.Required("city", default=[]): vol.In(
                                locations_for_form
                            ),
                        }
                    ),
                    errors=errors,
                )
            user_input = {CONF_CITY: _build_place_key(self.city_insee[0])}

        city_infos = user_input[CONF_CITY].split(";")
        self.data[CONF_INSEE_CODE] = city_infos[0]
        self.data[CONF_CITY] = city_infos[1]
        return await self.async_step_location(self.data)
