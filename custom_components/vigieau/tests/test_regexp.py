from os import path
import sys

current_dir = path.dirname(__file__)
parent_dir = path.dirname(current_dir)
sys.path.append(".")
sys.path.append(parent_dir)
from custom_components.vigieau.const import SENSOR_DEFINITIONS
import unittest
import json
import os
import re


class TestRegexp(unittest.TestCase):
    def test_matcher_in_component(self):
        file = os.path.join(parent_dir, "scripts/full_usage_list.json")
        with open(file) as f:
            input = f.read()
        data = json.loads(input)

        for restriction in data["restrictions"]:  # For all restrictions in the list
            restriction["nom"] = restriction["usage"]
            with self.subTest(
                msg="One matcher failed"
            ):  # For soft fail, ref https://stackoverflow.com/questions/4732827/continuing-in-pythons-unittest-when-an-assertion-fails
                found = False
                for sensor in SENSOR_DEFINITIONS:
                    if sensor.match(restriction):
                        found = True
                        break
                self.assertTrue(
                    found,
                    f"Value **{restriction['usage']}** in category **{restriction['thematique']}** not found in matcher",
                )  # Check for one usage if it has been found

    def test_hors_exclusion_stripped_for_potagers(self):
        """Usages with '(hors ... jardins potagers)' must NOT match the potagers sensor."""
        potagers_sensor = None
        for s in SENSOR_DEFINITIONS:
            if s.name == "Arrosage des jardins potagers":
                potagers_sensor = s
                break
        self.assertIsNotNone(potagers_sensor)

        usage = {
            "nom": "Arrosage des espaces verts (hors pelouses, fleurs et massifs fleuris ainsi que jardins potagers)",
            "thematique": "Arroser",
        }
        self.assertFalse(
            potagers_sensor.match(usage),
            "Usage with '(hors ... jardins potagers)' should NOT match potagers sensor",
        )

    def test_potagers_still_matches(self):
        """Genuine potager usages must still match the potagers sensor."""
        potagers_sensor = None
        for s in SENSOR_DEFINITIONS:
            if s.name == "Arrosage des jardins potagers":
                potagers_sensor = s
                break
        self.assertIsNotNone(potagers_sensor)

        for nom in [
            "Arrosage des jardins potagers",
            "Arrosage des potagers",
            "Arrosage des jardins potagers (y compris serres non-agricoles)",
        ]:
            with self.subTest(nom=nom):
                self.assertTrue(
                    potagers_sensor.match({"nom": nom, "thematique": "Arroser"}),
                    f"'{nom}' should match potagers sensor",
                )

    def test_hors_exclusion_does_not_affect_matchers_with_hors(self):
        """Matchers that contain 'hors' in their pattern must still match with full names."""
        file = os.path.join(parent_dir, "scripts/full_usage_list.json")
        with open(file) as f:
            data = json.loads(f.read())

        matched_restrictions = []
        for restriction in data["restrictions"]:
            restriction["nom"] = restriction["usage"]
            if "hors périmètres irrigués" in restriction["usage"]:
                matched_restrictions.append(restriction)
                found = False
                for sensor in SENSOR_DEFINITIONS:
                    if sensor.match(restriction):
                        found = True
                        break
                self.assertTrue(
                    found,
                    f"'{restriction['usage']}' should match at least one sensor "
                    f"(matcher with 'hors' should use full name)",
                )
        self.assertGreater(
            len(matched_restrictions), 0,
            "No restriction with 'hors périmètres irrigués' found in test data",
        )

    def test_hors_exclusion_reclassifies_out_of_maraichage(self):
        """Usage with '(hors usage agricole)' must NOT match Maraîchage et cultures."""
        maraichage_sensor = None
        for s in SENSOR_DEFINITIONS:
            if s.name == "Maraîchage et cultures":
                maraichage_sensor = s
                break
        self.assertIsNotNone(maraichage_sensor)

        usage = {
            "nom": "Arrosage des plants destinés à l'alimentation (hors usage agricole)",
            "thematique": "Arroser",
        }
        self.assertFalse(
            maraichage_sensor.match(usage),
            "Usage with '(hors usage agricole)' should NOT match Maraîchage et cultures",
        )

    def test_hors_exclusion_potager_reclassified_to_potagers(self):
        """Usage '(hors usage agricole)' reclassified should match potagers."""
        potagers_sensor = None
        for s in SENSOR_DEFINITIONS:
            if s.name == "Arrosage des jardins potagers":
                potagers_sensor = s
                break
        self.assertIsNotNone(potagers_sensor)

        usage = {
            "nom": "Arrosage des plants destinés à l'alimentation (hors usage agricole)",
            "thematique": "Arroser",
        }
        self.assertTrue(
            potagers_sensor.match(usage),
            "Usage 'plants destinés à l\\'alimentation (hors usage agricole)' should match potagers",
        )


if __name__ == "__main__":
    unittest.main()
