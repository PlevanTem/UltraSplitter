from __future__ import annotations

import unittest
from pathlib import Path

from ultrasplitter.evaluator import evaluate_grid


FIXTURES = Path(__file__).parents[1] / "fixtures" / "generated"


class GeneratedFixtureTests(unittest.TestCase):
    def test_all_declared_fixture_cases_exist(self) -> None:
        expected = {
            "p0-irregular-panels.png",
            "p0-scattered-objects.png",
            "p0-bbox-overlap-disjoint.png",
            "p0-touching-subjects.png",
            "p0-occluded-subjects.png",
            "p0-edge-clipped-four-sides.png",
            "p0-valid-repair-grid-2x2.png",
            "p0-invalid-repair-grid-2x2.png",
            "p1-transparent-subject.png",
            "p1-detached-shadow.png",
            "p1-disconnected-one-subject.png",
            "p1-gradient-background.png",
            "p1-dense-60-subjects.png",
            "p1-small-noise.png",
            "p1-identity-source.png",
            "p1-identity-drift.png",
        }
        self.assertEqual({path.name for path in FIXTURES.glob("*.png")}, expected)

    def test_valid_repair_grid_passes_mechanical_checks(self) -> None:
        result = evaluate_grid(
            FIXTURES / "p0-valid-repair-grid-2x2.png",
            {"rows": 2, "columns": 2, "count": 4},
        )
        self.assertTrue(result["passed"], result["issues"])

    def test_invalid_repair_grid_fails_and_surfaces_duplicate_candidates(self) -> None:
        result = evaluate_grid(
            FIXTURES / "p0-invalid-repair-grid-2x2.png",
            {"rows": 2, "columns": 2, "count": 4},
        )
        self.assertFalse(result["passed"])
        self.assertIn("background_not_uniform", result["issues"])
        self.assertTrue(result["metrics"]["possible_duplicate_cells"])


if __name__ == "__main__":
    unittest.main()
