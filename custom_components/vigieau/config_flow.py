import logging
from typing import Any, Optional

from homeassistant import config_entries

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Description of the config flow:
# async_step_user is called when user starts to configure the integration
# we follow with a flow of form/menu
# eventually we call async_create_entry with a dictionnary of data
# HA calls async_setup_entry with a ConfigEntry which wraps this data (defined in __init__.py)
# in async_setup_entry we call hass.config_entries.async_forward_entry_setups to setup each relevant platform (sensor in our case)
# HA calls async_setup_entry from sensor.py


class SetupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        """Called once with None as user_input, then a second time with user provided input"""
        await self.async_set_unique_id("1")
        self._abort_if_unique_id_configured()
        # will call async_setup_entry defined in __init__.py file
        return self.async_create_entry(title="vigieau", data={})
