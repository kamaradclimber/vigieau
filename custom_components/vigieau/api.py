import logging
import aiohttp
from typing import Optional, Tuple
from aiohttp.client import ClientTimeout
from homeassistant.helpers.update_coordinator import UpdateFailed
from .const import GEOAPI_GOUV_URL, ADDRESS_API_URL

DEFAULT_TIMEOUT = 120
CLIENT_TIMEOUT = ClientTimeout(total=DEFAULT_TIMEOUT)

_LOGGER = logging.getLogger(__name__)


class InseeApiError(RuntimeError):
    pass


class InseeApi:
    """Api to get INSEE data"""

    def __init__(
        self, session: Optional[aiohttp.ClientSession] = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        self._session = session or aiohttp.ClientSession()

    async def get_data(self, zipcode) -> dict:
        """Get INSEE code for a given zip code"""
        url = f"{GEOAPI_GOUV_URL}codePostal={zipcode}&fields=code,centre&format=json&geometry=centre"

        resp = await self._session.get(url)
        if resp.status != 200:
            raise InseeApiError(f"Unable to get Insee Code for zip {zipcode}")

        data = await resp.json()
        _LOGGER.debug("Got Data GEOAPI data : %s ", data)

        if len(data) == 0:
            raise InseeApiError("No data received with GeoApi")

        return data


class AddressApiError(RuntimeError):
    pass


class AddressApi:
    """API for Reverse geocoding"""

    def __init__(
        self, session: Optional[aiohttp.ClientSession] = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        self._session = session or aiohttp.ClientSession()

    async def get_data(self, lat: float, lon: float) -> Tuple[str, str, float, float]:
        url = f"{ADDRESS_API_URL}/reverse/?lat={lat}&lon={lon}&type=housenumber"
        resp = await self._session.get(url)
        if resp.status != 200:
            raise AddressApiError(
                "Failed to fetch address from api-adresse.data.gouv.fr api"
            )
        data = await resp.json()
        _LOGGER.debug(f"Data received from {ADDRESS_API_URL}: {data}")
        if len(data["features"]) == 0:
            _LOGGER.warn(
                "Data received from api-adresse.data.gouv.fr is empty for those coordinates: (%s, %s). Either coordinates are not located in France or the governement geocoding database has no record for them.",
                lat,
                lon,
            )
            raise AddressApiError(
                "Impossible to find approximate address of the current HA instance. API returned no result."
            )
        properties = data["features"][0]["properties"]
        return (properties["citycode"], properties["city"], lat, lon)
