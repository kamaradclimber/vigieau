import json
import unittest

from custom_components.vigieau.api import CLIENT_TIMEOUT, VigieauAPI, VigieauAPIError


class FakeResponse:
    def __init__(self, status, payload=None, text="", json_error=None):
        self.status = status
        self.payload = payload
        self.text_value = text
        self.json_error = json_error

    async def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload

    async def text(self):
        return self.text_value


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return self.response


VALID_ZONE = {
    "niveauGravite": "alerte",
    "usages": [
        {
            "nom": "Arrosage des pelouses",
            "thematique": "Arroser",
            "description": "Interdiction de 8 h à 20 h",
        }
    ],
}


class TestVigieauAPIResilience(unittest.IsolatedAsyncioTestCase):
    async def _get_data(self, response):
        session = FakeSession(response)
        api = VigieauAPI(session)
        return await api.get_data(48.0, 2.0, "75056", "particulier", "SUP"), session

    async def test_valid_response(self):
        data, session = await self._get_data(FakeResponse(200, [VALID_ZONE]))

        self.assertEqual(data["niveauGravite"], "alerte")
        self.assertEqual(data["_numeric_state_value"], 2)
        self.assertEqual(session.calls[0][1], CLIENT_TIMEOUT)
        self.assertEqual(CLIENT_TIMEOUT.total, 60)

    async def test_empty_list_means_no_restriction(self):
        data, _ = await self._get_data(FakeResponse(200, []))

        self.assertEqual(data["niveauGravite"], "Pas de restrictions")
        self.assertEqual(data["_numeric_state_value"], 0)

    async def test_404_no_zone_means_no_restriction(self):
        response = FakeResponse(
            404, {"message": "Aucune zone de restriction n'est en vigueur"}
        )
        data, _ = await self._get_data(response)

        self.assertEqual(data["niveauGravite"], "Pas de restrictions")

    async def test_other_404_is_an_error(self):
        response = FakeResponse(404, {"message": "Commune inconnue"})

        with self.assertRaises(VigieauAPIError):
            await self._get_data(response)

    async def test_http_error_contains_response_body(self):
        response = FakeResponse(500, text="internal server error")

        with self.assertRaises(VigieauAPIError) as raised:
            await self._get_data(response)

        self.assertEqual(raised.exception.text, "internal server error")

    async def test_invalid_json_is_an_error(self):
        response = FakeResponse(
            200, json_error=json.JSONDecodeError("invalid json", "", 0)
        )

        with self.assertRaises(VigieauAPIError):
            await self._get_data(response)

    async def test_non_list_payload_is_an_error(self):
        response = FakeResponse(200, {"niveauGravite": "alerte"})

        with self.assertRaises(VigieauAPIError):
            await self._get_data(response)

    async def test_unknown_severity_is_an_error(self):
        payload = dict(VALID_ZONE, niveauGravite="valeur-inconnue")
        response = FakeResponse(200, [payload])

        with self.assertRaises(VigieauAPIError):
            await self._get_data(response)
