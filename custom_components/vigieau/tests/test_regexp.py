from os import path
import sys

current_dir = path.dirname(__file__)
parent_dir = path.dirname(current_dir)
sys.path.append(".")
sys.path.append(parent_dir)
from custom_components.vigieau.const import SENSOR_DEFINITIONS
import unittest
from pathlib import Path
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
            with self.subTest(
                msg="One matcher failed"
            ):  # For soft fail, ref https://stackoverflow.com/questions/4732827/continuing-in-pythons-unittest-when-an-assertion-fails
                found = False
                for sensor in SENSOR_DEFINITIONS:
                    # We may have to create a function rather than copy/paste, but it's a 'simple re.search....
                    for matcher in sensor.matchers:
                        if re.search(
                            matcher,
                            restriction["usage"],
                            re.IGNORECASE,
                        ):
                            found = True
                self.assertTrue(
                    found,
                    f"Value **{restriction['usage']}** in category **{restriction['thematique']}** not found in matcher",
                )  # Check for one usage if it has been found


if __name__ == "__main__":
    unittest.main()
