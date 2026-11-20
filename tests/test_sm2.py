"""Tests for the SM-2 scheduling algorithm."""

import unittest
from datetime import date, timedelta

from flashcard_cli.sm2 import INITIAL_EF, MIN_EF, review_schedule, update_ef

TODAY = date(2026, 11, 20)


class TestIntervalProgression(unittest.TestCase):
    def test_progression_1_6_then_times_ef_with_good_grades(self):
        # Grade 5 every time: intervals 1, 6, then round(6 * EF).
        s1 = review_schedule(0, 0, INITIAL_EF, 5, TODAY)
        self.assertEqual(s1["interval"], 1)
        self.assertEqual(s1["repetitions"], 1)
        self.assertEqual(s1["due_date"], TODAY + timedelta(days=1))

        s2 = review_schedule(s1["repetitions"], s1["interval"], s1["ef"], 5, TODAY)
        self.assertEqual(s2["interval"], 6)
        self.assertEqual(s2["repetitions"], 2)
        self.assertEqual(s2["due_date"], TODAY + timedelta(days=6))

        # Third interval uses the EF held before this review (s2's EF).
        expected = int(round(6 * s2["ef"]))
        s3 = review_schedule(s2["repetitions"], s2["interval"], s2["ef"], 5, TODAY)
        self.assertEqual(s3["interval"], expected)
        self.assertGreater(s3["interval"], 6)
        self.assertEqual(s3["repetitions"], 3)

    def test_grade_4_keeps_ef_stable(self):
        # q=4: (5-q)=1 -> 0.1 - 1*(0.08+0.02) = 0.0, EF unchanged.
        self.assertAlmostEqual(update_ef(2.5, 4), 2.5)

    def test_grade_5_increases_ef_by_0_1(self):
        self.assertAlmostEqual(update_ef(2.5, 5), 2.6)

    def test_invalid_grade_rejected(self):
        with self.assertRaises(ValueError):
            review_schedule(0, 0, INITIAL_EF, 6, TODAY)
        with self.assertRaises(ValueError):
            review_schedule(0, 0, INITIAL_EF, -1, TODAY)


class TestEaseFactorFloor(unittest.TestCase):
    def test_ef_decreases_with_poor_grades(self):
        self.assertLess(update_ef(2.5, 3), 2.5)
        self.assertLess(update_ef(2.5, 0), update_ef(2.5, 3))

    def test_ef_floored_at_1_3(self):
        ef = INITIAL_EF
        for _ in range(50):
            ef = update_ef(ef, 0)
            self.assertGreaterEqual(ef, MIN_EF)
        self.assertAlmostEqual(ef, MIN_EF)


class TestResetOnFailure(unittest.TestCase):
    def test_grade_below_3_resets_interval_and_repetitions(self):
        for bad_grade in (0, 1, 2):
            result = review_schedule(5, 30, 2.5, bad_grade, TODAY)
            self.assertEqual(result["repetitions"], 0)
            self.assertEqual(result["interval"], 1)
            self.assertEqual(result["due_date"], TODAY + timedelta(days=1))

    def test_grade_3_does_not_reset(self):
        result = review_schedule(2, 6, 2.5, 3, TODAY)
        self.assertEqual(result["repetitions"], 3)
        self.assertEqual(result["interval"], int(round(6 * 2.5)))


if __name__ == "__main__":
    unittest.main()
