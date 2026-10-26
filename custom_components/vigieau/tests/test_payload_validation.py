import copy
import unittest

from custom_components.vigieau import validate_vigieau_data
from custom_components.vigieau.api import VigieauAPIError


def payload():
    return {
        "niveauGravite": "alerte_renforcee",
        "usages": [
            {
                "nom": "Arrosage des pelouses",
                "thematique": "Arroser",
                "description": "Interdiction de 8 h à 20 h",
                "heureDebut": "8h",
                "heureFin": "20h",
            }
        ],
    }


class TestPayloadValidation(unittest.TestCase):
    def assert_invalid(self, data):
        with self.assertRaises(VigieauAPIError):
            validate_vigieau_data(data)

    def test_valid_payload_adds_numeric_severity(self):
        data = validate_vigieau_data(payload())

        self.assertEqual(data["_numeric_state_value"], 3)

    def test_payload_must_be_an_object(self):
        self.assert_invalid([])

    def test_severity_must_be_known(self):
        data = payload()
        data["niveauGravite"] = "valeur-inconnue"
        self.assert_invalid(data)

    def test_usages_must_be_a_list(self):
        data = payload()
        data["usages"] = None
        self.assert_invalid(data)

    def test_usage_must_be_an_object(self):
        data = payload()
        data["usages"] = ["not-an-object"]
        self.assert_invalid(data)

    def test_usage_required_string_fields(self):
        for field in ("nom", "thematique", "description"):
            with self.subTest(field=field):
                data = payload()
                del data["usages"][0][field]
                self.assert_invalid(data)

    def test_invalid_description_type(self):
        data = payload()
        data["usages"][0]["description"] = 42
        self.assert_invalid(data)

    def test_invalid_time_field_type(self):
        for field in ("heureDebut", "heureFin"):
            with self.subTest(field=field):
                data = payload()
                data["usages"][0][field] = 8
                self.assert_invalid(data)

    def test_optional_time_fields_are_accepted(self):
        data = copy.deepcopy(payload())
        del data["usages"][0]["heureDebut"]
        del data["usages"][0]["heureFin"]

        self.assertEqual(validate_vigieau_data(data)["_numeric_state_value"], 3)
