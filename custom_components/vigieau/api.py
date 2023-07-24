import logging
import aiohttp
from aiohttp.client import ClientTimeout
from homeassistant.helpers.update_coordinator import (
    GeoAPICallFailed,UpdateFailed
)
from .const import  GEOAPI_GOUV_URL, ADRESSE_URL
DEFAULT_TIMEOUT = 120
CLIENT_TIMEOUT = ClientTimeout(total=DEFAULT_TIMEOUT)

_LOGGER = logging.getLogger(__name__)


class INSEEAPI:
    """Api to get INSEE data"""
    def __init__(
        self, session: aiohttp.ClientSession = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        if session is not None:
            self._session = session
        else:
            self._session = aiohttp.ClientSession()

    async def get_data(self, zipcode) -> dict:
        """Get INSEE code for a given zip code"""
        url = f"{GEOAPI_GOUV_URL}codePostal={zipcode}&fields=s=code&format=json&geometry=centre"

        resp = await self._session.get(url)
        if  resp.status!=200:
            raise GeoAPICallFailed("Unable to get Insee Code for zip %s", zipcode)

        data = await resp.json()
        _LOGGER.debug("Got Data GEOAPI data : %s ", data)

        if len (data)==0:
            raise GeoAPICallFailed ("No data received with GeoApi")

        return data

class ADRESSEAPI:
    """API for Reverss geocoding"""
    def __init__(
        self, session: aiohttp.ClientSession = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        if session is not None:
            self._session = session
        else:
            self._session = aiohttp.ClientSession()

    async def get_data(self, lat, lon):
        url = f"{ADRESSE_URL}/reverse/?lat={lat}&lon={lon}&type=housenumber"
        resp = await self._session.get(url)
        # r = await client.get(
        #     f"https://api-adresse.data.gouv.fr/reverse/?lat={self.lat}&lon={self.lon}&type=housenumber"
        # )
        if resp.status != 200 :
            raise UpdateFailed(
                "Failed to fetch address from api-adresse.data.gouv.fr api"
            )
        data = await  resp.json()
        _LOGGER.debug(f"Data received from api-adresse.data.gouv.fr: {data}")
        if len(data["features"]) == 0:
            _LOGGER.warn(
                "Data received from api-adresse.data.gouv.fr is empty for those coordinates: (%s, %s). Either coordinates are not located in France or the governement geocoding database has no record for them."
            ,lat, lon)
            raise UpdateFailed(
                "Impossible to find approximate address of the current HA instance. API returned no result."
            )
        properties = data["features"][0]["properties"]
        return [properties["citycode"], properties["city"]]

