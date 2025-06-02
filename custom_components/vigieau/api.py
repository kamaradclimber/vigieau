import logging
import aiohttp
from typing import Optional, Tuple
from aiohttp.client import ClientTimeout
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import ADDRESS_API_URL, GEOAPI_GOUV_URL, VIGIEAU_API_URL

import re

CLIENT_TIMEOUT = ClientTimeout(total=120)

_LOGGER = logging.getLogger(__name__)


class InseeAPIError(RuntimeError):
    pass


class InseeAPI:
    """API to get INSEE data"""

    def __init__(
        self, session: Optional[aiohttp.ClientSession] = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        self._session = session or aiohttp.ClientSession()

    async def get_insee_list(self):
        """Get all INSEE codes"""
        session = aiohttp.ClientSession()
        resp = await session.get(GEOAPI_GOUV_URL)

        if resp.status != 200:
            raise InseeAPIError(
                f"Unable to list all INSEE codes. API status was {resp.status}"
            )

        return await resp.json()

    async def get_data(self, zipcode) -> dict:
        """Get INSEE code for a given zip code"""
        url = f"{GEOAPI_GOUV_URL}&codePostal={zipcode}&format=json&geometry=centre"

        resp = await self._session.get(url)
        if resp.status != 200:
            raise InseeAPIError(
                f"Unable to get INSEE Code for zip {zipcode}"
            )

        data = await resp.json()
        _LOGGER.debug("Got data GeoAPI : %s ", data)

        if len(data) == 0:
            raise InseeAPIError("No data received with GeoAPI")

        return data


class AddressAPIError(RuntimeError):
    pass


class AddressAPI:
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
            raise AddressAPIError(
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
            raise AddressAPIError(
                "Impossible to find approximate address of the current HA instance. API returned no result."
            )
        properties = data["features"][0]["properties"]
        return (properties["citycode"], properties["city"], lat, lon)


class VigieauAPIError(RuntimeError):
    def __init__(self, message, text):
        super().__init__(message)
        self._text = text

    @property
    def text(self) -> str:
        return self._text


class VigieauAPI:
    def __init__(
        self, session: Optional[aiohttp.ClientSession] = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        self._session = session or aiohttp.ClientSession()

    async def get_data(
            self, lat: Optional[float], long: Optional[float], insee_code: str, profil: str,
            zone_type: str) -> dict:
        url = f"{VIGIEAU_API_URL}/api/zones?commune={insee_code}&profil={profil}&zoneType={zone_type}"
        if lat is not None and long is not None:
            url += f"&lat={lat}&lon={long}"
        _LOGGER.debug(f"Requesting restrictions from {url}")
        resp = await self._session.get(url)
        if (
            resp.status == 404
            and "message" in await resp.json()
            and re.match("Aucune zone.+en vigueur", (await resp.json())["message"])
        ):
            _LOGGER.debug(f"Vigieau replied with no restriction, faking data")
            data = [{"niveauGravite": "Pas de restrictions",
                     "usages": [], "arrete": {}}]
        elif resp.status == 200 and (await resp.json()) == []:
            _LOGGER.debug(f"Vigieau replied with no data at all, faking data")
            data = [{"niveauGravite": "Pas de restrictions",
                     "usages": [], "arrete": {}}]
        elif resp.status in range(200, 300):
            data = await resp.json()
        else:
            raise VigieauAPIError(f"Failed fetching vigieau data", resp.text)
        _LOGGER.debug(f"Data fetched from vigieau: {data}")
        # enriching with numeric state value
        data = data[0]
        data["_numeric_state_value"] = {
            "Pas de restrictions": 0,
            "vigilance": 1,
            "alerte": 2,
            "alerte_renforcée": 3,
            "alerte_renforcee": 3,
            "crise": 4,
        }[data["niveauGravite"]]
        return data
