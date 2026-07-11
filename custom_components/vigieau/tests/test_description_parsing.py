from os import path
import json
import subprocess
import sys
import unittest

current_dir = path.dirname(__file__)
parent_dir = path.dirname(current_dir)
scripts_dir = path.join(parent_dir, "scripts")
sys.path.append(".")
sys.path.append(parent_dir)

from custom_components.vigieau.__init__ import classify_restrictions, extract_time_range

DESCRIPTIONS_FILE = path.join(scripts_dir, "full_descriptions_list.json")


def _load_descriptions():
    if not path.exists(DESCRIPTIONS_FILE):
        subprocess.check_call(
            [sys.executable, path.join(scripts_dir, "generate_descriptions.py")],
            cwd=path.join(parent_dir, "..", ".."),
        )
    with open(DESCRIPTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["descriptions"]


class TestDescriptionClassification(unittest.TestCase):
    """Verify that every known restriction description can be classified."""

    @classmethod
    def setUpClass(cls):
        cls.descriptions = _load_descriptions()

    def test_all_descriptions_classified(self):
        unclassified = []
        for entry in self.descriptions:
            desc = entry["description"]
            level, _ = classify_restrictions([desc])
            if level is None:
                unclassified.append(desc)
        if unclassified:
            msg = f"{len(unclassified)} description(s) could not be classified:\n"
            for d in unclassified[:10]:
                msg += f"  - {d[:120]}\n"
            if len(unclassified) > 10:
                msg += f"  ... and {len(unclassified) - 10} more\n"
            self.fail(msg)


class TestDescriptionTimeExtraction(unittest.TestCase):
    """Verify that time patterns in restriction descriptions can be extracted."""

    @classmethod
    def setUpClass(cls):
        cls.descriptions = _load_descriptions()

    def test_time_descriptions_extractable(self):
        failed = []
        for entry in self.descriptions:
            if not entry["has_time_pattern"]:
                continue
            desc = entry["description"]
            try:
                extract_time_range([desc])
            except Exception as e:
                failed.append((desc, str(e)))
        if failed:
            msg = f"{len(failed)} time-bearing description(s) raised exceptions:\n"
            for d, e in failed[:10]:
                msg += f"  - {d[:80]}: {e}\n"
            self.fail(msg)

    def test_uniquement_descriptions_extract_without_exception(self):
        failed = []
        for entry in self.descriptions:
            if not entry["has_uniquement"] or not entry["has_time_pattern"]:
                continue
            desc = entry["description"]
            try:
                extract_time_range([desc])
            except Exception as e:
                failed.append((desc, str(e)))
        if failed:
            msg = f"{len(failed)} 'uniquement' description(s) raised exceptions:\n"
            for d, e in failed[:10]:
                msg += f"  - {d[:80]}: {e}\n"
            self.fail(msg)


if __name__ == "__main__":
    unittest.main()
