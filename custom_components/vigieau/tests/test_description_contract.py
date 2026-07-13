"""Contract tests: validate the full restriction parsing pipeline against real descriptions.

Each test case specifies:
  - description: the raw restriction text
  - expected_level: what classify_restrictions() should return
  - expected_time_based: whether the restriction is time-based
  - expected_range: expected (start, end) from extract_time_range(), or None
  - restricted_at: a time when the restriction SHOULD be active (time-based only)
  - allowed_at: a time when the restriction should NOT be active (time-based only)
"""
from datetime import time as dt_time
from os import path
import json
import sys
import unittest

current_dir = path.dirname(__file__)
parent_dir = path.dirname(current_dir)
sys.path.append(".")
sys.path.append(parent_dir)

from custom_components.vigieau.__init__ import (
    classify_restrictions,
    extract_time_range,
    _parse_time_str,
)


# ── Hand-verified examples ───────────────────────────────────────────────────

HAND_VERIFIED_CASES = [
    # 1. Simple daytime restriction
    {
        "description": "Interdiction de 10h à 18h.",
        "expected_level": "Interdiction sur plage horaire",
        "expected_time_based": True,
        "expected_range": (dt_time(10, 0), dt_time(18, 0)),
        "restricted_at": dt_time(14, 0),
        "allowed_at": dt_time(20, 0),
    },
    # 2. Overnight "uniquement" → swap to daytime restriction
    #    Classification falls through to single-restriction fallback
    {
        "description": "Autorisé uniquement de 18 h à 10 h pour l'abreuvement",
        "expected_level": "Autorisé uniquement de 18 h à 10 h pour l'abreuvement",
        "expected_time_based": False,
        "expected_range": (dt_time(10, 0), dt_time(18, 0)),
        "restricted_at": dt_time(14, 0),
        "allowed_at": dt_time(20, 0),
    },
    # 3. Overnight "interdit sauf" → swap to daytime restriction
    {
        "description": "Interdit sauf terrain de compétition engazonné entre 18h et 10h",
        "expected_level": "Interdiction sur plage horaire",
        "expected_time_based": True,
        "expected_range": (dt_time(10, 0), dt_time(18, 0)),
        "restricted_at": dt_time(14, 0),
        "allowed_at": dt_time(20, 0),
    },
    # 4. Overnight "uniquement" with different hours
    {
        "description": "Interdit sauf plantations (arbres) et îlots de fraîcheur uniquement de 20 h à 8 h",
        "expected_level": "Interdiction sur plage horaire",
        "expected_time_based": True,
        "expected_range": (dt_time(8, 0), dt_time(20, 0)),
        "restricted_at": dt_time(14, 0),
        "allowed_at": dt_time(22, 0),
    },
    # 5. Simple daytime restriction with spaces
    {
        "description": "Interdiction de 8 h à 20 h",
        "expected_level": "Interdiction sur plage horaire",
        "expected_time_based": True,
        "expected_range": (dt_time(8, 0), dt_time(20, 0)),
        "restricted_at": dt_time(12, 0),
        "allowed_at": dt_time(22, 0),
    },
    # 6. No restriction
    {
        "description": "",
        "expected_level": "Aucune restriction",
        "expected_time_based": False,
        "expected_range": None,
    },
    # 7. Simple interdiction (no time)
    {
        "description": "Interdiction totale",
        "expected_level": "Interdiction",
        "expected_time_based": False,
        "expected_range": None,
    },
    # 8. Sensibilisation
    {
        "description": "Sensibilisation aux règles de bon usage",
        "expected_level": "Sensibilisation",
        "expected_time_based": False,
        "expected_range": None,
    },
    # 9. Interdiction sauf exception (no time)
    {
        "description": "Interdiction sauf abreuvement des animaux",
        "expected_level": "Interdiction sauf exception",
        "expected_time_based": False,
        "expected_range": None,
    },
]


def _is_restricted_at(time_range, now_time):
    """Compute whether a time range restricts a given time (standalone, no mock needed)."""
    if time_range is None:
        return None  # no time info
    start, end = time_range
    if start <= end:
        return start <= now_time < end
    else:
        return now_time >= start or now_time < end


class TestContractHandVerified(unittest.TestCase):
    """Test hand-verified examples through the full pipeline."""

    def test_all_hand_verified_cases(self):
        failures = []
        for i, case in enumerate(HAND_VERIFIED_CASES):
            desc = case["description"]
            restrictions = [desc] if desc else []

            # 1. Classification
            level, is_time = classify_restrictions(restrictions)
            if level != case["expected_level"]:
                failures.append(
                    f"Case {i}: classification mismatch: got '{level}', "
                    f"expected '{case['expected_level']}' (desc: {desc[:80]})"
                )
                continue
            if is_time != case["expected_time_based"]:
                failures.append(
                    f"Case {i}: is_time_based mismatch: got {is_time}, "
                    f"expected {case['expected_time_based']} (desc: {desc[:80]})"
                )
                continue

            # 2. Time extraction
            time_range = extract_time_range(restrictions) if restrictions else None
            if time_range != case["expected_range"]:
                failures.append(
                    f"Case {i}: time range mismatch: got {time_range}, "
                    f"expected {case['expected_range']} (desc: {desc[:80]})"
                )
                continue

            # 3. Temporal behavior (only for time-based)
            if case["expected_time_based"] and time_range is not None:
                restricted_at = case.get("restricted_at")
                allowed_at = case.get("allowed_at")

                if restricted_at is not None:
                    result = _is_restricted_at(time_range, restricted_at)
                    if result is not True:
                        failures.append(
                            f"Case {i}: should be restricted at {restricted_at} "
                            f"but got {result} (range={time_range}, desc: {desc[:80]})"
                        )

                if allowed_at is not None:
                    result = _is_restricted_at(time_range, allowed_at)
                    if result is not False:
                        failures.append(
                            f"Case {i}: should be allowed at {allowed_at} "
                            f"but got {result} (range={time_range}, desc: {desc[:80]})"
                        )

        if failures:
            msg = f"{len(failures)} contract case(s) failed:\n"
            for f in failures:
                msg += f"  - {f}\n"
            self.fail(msg)


# ── Full dataset contract tests ───────────────────────────────────────────────

DESCRIPTIONS_FILE = path.join(
    path.dirname(parent_dir), "scripts", "full_descriptions_list.json"
)


def _load_descriptions():
    if not path.exists(DESCRIPTIONS_FILE):
        return []
    with open(DESCRIPTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["descriptions"]


def _hour_after(t):
    """Return the hour after a given time, wrapped to [0, 24)."""
    return dt_time((t.hour + 1) % 24, t.minute)


class TestContractFullDataset(unittest.TestCase):
    """Validate every known description through the full pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.descriptions = _load_descriptions()

    def test_all_descriptions_classified(self):
        """Every description must produce a non-None classification."""
        unclassified = []
        for entry in self.descriptions:
            desc = entry["description"]
            level, _ = classify_restrictions([desc] if desc else [])
            if level is None:
                unclassified.append(desc[:120])
        if unclassified:
            msg = f"{len(unclassified)} description(s) could not be classified:\n"
            for d in unclassified[:10]:
                msg += f"  - {d}\n"
            if len(unclassified) > 10:
                msg += f"  ... and {len(unclassified) - 10} more\n"
            self.fail(msg)

    def test_time_extractions_produce_valid_ranges(self):
        """When a time pattern is present, extract_time_range must return a valid range."""
        failures = []
        for entry in self.descriptions:
            if not entry["has_time_pattern"]:
                continue
            desc = entry["description"]
            time_range = extract_time_range([desc])
            if time_range is None:
                failures.append(f"No time range extracted: {desc[:120]}")
                continue
            start, end = time_range
            if not (isinstance(start, dt_time) and isinstance(end, dt_time)):
                failures.append(f"Invalid range types: {time_range} (desc: {desc[:80]})")
        if failures:
            msg = f"{len(failures)} time extraction issue(s):\n"
            for f in failures[:20]:
                msg += f"  - {f}\n"
            if len(failures) > 20:
                msg += f"  ... and {len(failures) - 20} more\n"
            self.fail(msg)

    def test_temporal_behavior_consistency(self):
        """For time-based descriptions, verify restricted/allowed at correct times."""
        failures = []
        for entry in self.descriptions:
            if not entry["has_time_pattern"]:
                continue
            desc = entry["description"]
            time_range = extract_time_range([desc])
            if time_range is None:
                continue

            start, end = time_range

            # Pick a time that should be restricted: just after start
            restricted_at = _hour_after(start)
            # Pick a time that should be allowed: just after end
            allowed_at = _hour_after(end)

            is_restricted = _is_restricted_at(time_range, restricted_at)
            is_allowed = _is_restricted_at(time_range, allowed_at)

            if is_restricted is not True:
                failures.append(
                    f"Should be restricted at {restricted_at} for range "
                    f"({start}-{end}) but got {is_restricted}: {desc[:100]}"
                )
            if is_allowed is not False:
                failures.append(
                    f"Should be allowed at {allowed_at} for range "
                    f"({start}-{end}) but got {is_allowed}: {desc[:100]}"
                )

        if failures:
            msg = f"{len(failures)} temporal behavior issue(s):\n"
            for f in failures[:20]:
                msg += f"  - {f}\n"
            if len(failures) > 20:
                msg += f"  ... and {len(failures) - 20} more\n"
            self.fail(msg)


if __name__ == "__main__":
    unittest.main()
