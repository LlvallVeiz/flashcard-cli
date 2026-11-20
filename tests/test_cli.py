"""Tests for the CLI wiring (main() with argv, piped quiz input)."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from flashcard_cli.cli import main
from flashcard_cli.deck import load_deck


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.deck_path = os.path.join(self._tmp.name, "deck.json")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--deck", self.deck_path, *args])
        return code, out.getvalue()

    def test_add_list_review_stats_flow(self):
        code, out = self.run_cli("add", "--front", "Q1", "--back", "A1", "--tags", "geo,exam")
        self.assertEqual(code, 0)
        self.assertIn("Added card [1]", out)

        code, out = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("Q1 -> A1", out)

        code, out = self.run_cli("list", "--tag", "geo")
        self.assertIn("Q1", out)
        code, out = self.run_cli("list", "--tag", "missing")
        self.assertIn("No cards.", out)

        code, out = self.run_cli("review", "--id", "1", "--grade", "5")
        self.assertEqual(code, 0)
        self.assertIn("interval 1d", out)

        deck = load_deck(self.deck_path)
        self.assertEqual(len(deck["cards"][0]["history"]), 1)

        code, out = self.run_cli("stats")
        self.assertEqual(code, 0)
        self.assertIn("Total cards: 1", out)
        self.assertIn("Reviews done: 1", out)
        self.assertIn("Retention rate: 100.0%", out)
        self.assertIn("card [1]: 1 review(s)", out)

    def test_review_unknown_id_fails(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code, _ = self.run_cli("review", "--id", "99", "--grade", "5")
        self.assertEqual(code, 1)
        self.assertIn("no card with id 99", err.getvalue())

    def test_quiz_with_piped_input(self):
        self.run_cli("add", "--front", "Q1", "--back", "A1")
        self.run_cli("add", "--front", "Q2", "--back", "A2")
        grades = iter(["5", "2"])
        with patch("builtins.input", lambda prompt="": next(grades)):
            code, out = self.run_cli("quiz")
        self.assertEqual(code, 0)
        self.assertIn("Reviewed 2 card(s).", out)
        deck = load_deck(self.deck_path)
        histories = [c["history"] for c in deck["cards"]]
        self.assertEqual(histories[0][0]["grade"], 5)
        self.assertEqual(histories[1][0]["grade"], 2)

    def test_quiz_no_due_cards(self):
        code, out = self.run_cli("quiz")
        self.assertEqual(code, 0)
        self.assertIn("No cards due.", out)


if __name__ == "__main__":
    unittest.main()
