import json
import logging
import re
from typing import Any, Optional, Tuple

import aiohttp
from aiohttp.client import ClientTimeout

from .const import ADDRESS_API_URL, GEOAPI_GOUV_URL, VIGIEAU_API_URL

CLIENT_TIMEOUT = ClientTimeout(total=60)

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
        resp = await session.get(GEOAPI_GOUV_URL, timeout=self._timeout)

        if resp.status != 200:
            raise InseeAPIError(
                f"Unable to list all INSEE codes. API status was {resp.status}"
            )

        return await resp.json()

    async def get_data(self, zipcode) -> dict:
        """Get INSEE code for a given zip code"""
        url = f"{GEOAPI_GOUV_URL}&codePostal={zipcode}&format=json&geometry=centre"

        resp = await self._session.get(url, timeout=self._timeout)
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
        resp = await self._session.get(url, timeout=self._timeout)
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
    def __init__(self, message: str, text: Optional[str] = None):
        super().__init__(message)
        self._text = text if text is not None else message

    @property
    def text(self) -> str:
        return self._text


def _no_restriction_data() -> list[dict]:
    return [{"niveauGravite": "Pas de restrictions", "usages": [], "arrete": {}}]


class VigieauAPI:
    def __init__(
        self, session: Optional[aiohttp.ClientSession] = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._timeout = timeout
        self._session = session or aiohttp.ClientSession()

    async def _read_json(self, resp) -> Any:
        try:
            return await resp.json()
        except (json.JSONDecodeError, aiohttp.ContentTypeError, UnicodeDecodeError) as err:
            raise VigieauAPIError(
                "Invalid JSON received from Vigieau API", str(err)
            ) from err

    async def get_data(
            self, lat: Optional[float], long: Optional[float], insee_code: str, profil: str,
            zone_type: str) -> dict:
        url = f"{VIGIEAU_API_URL}/api/zones?commune={insee_code}&profil={profil}&zoneType={zone_type}"
        if lat is not None and long is not None:
            url += f"&lat={lat}&lon={long}"
        _LOGGER.debug(f"Requesting restrictions from {url}")
        resp = await self._session.get(url, timeout=self._timeout)

        if resp.status == 404:
            payload = await self._read_json(resp)
            message = payload.get("message") if isinstance(payload, dict) else None
            if isinstance(message, str) and re.match("Aucune zone.+en vigueur", message):
                _LOGGER.debug("Vigieau replied with no restriction, faking data")
                data = _no_restriction_data()
            else:
                raise VigieauAPIError(
                    "Failed fetching vigieau data (HTTP 404)",
                    json.dumps(payload, ensure_ascii=False),
                )
        elif resp.status in range(200, 300):
            payload = await self._read_json(resp)
            if payload == []:
                _LOGGER.debug("Vigieau replied with no data at all, faking data")
                data = _no_restriction_data()
            elif isinstance(payload, list):
                data = payload
            else:
                raise VigieauAPIError(
                    "Malformed response from Vigieau API: expected a list of zones",
                    repr(payload),
                )
        else:
            text = await resp.text()
            raise VigieauAPIError(
                f"Failed fetching vigieau data (HTTP {resp.status})", text
            )

        _LOGGER.debug(f"Data fetched from vigieau: {data}")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise VigieauAPIError(
                "Malformed response from Vigieau API: expected a non-empty list of zone objects",
                repr(data),
            )

        return data[0]
