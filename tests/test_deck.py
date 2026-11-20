"""Tests for deck storage, due-card selection, and statistics."""

import os
import tempfile
import unittest
from datetime import date, timedelta

from flashcard_cli.deck import (
    add_card,
    compute_stats,
    due_cards,
    get_card,
    load_deck,
    new_deck,
    review_card,
    save_deck,
)

TODAY = date(2026, 11, 20)


class TestAddAndStorage(unittest.TestCase):
    def test_add_list_round_trip_via_storage_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "deck.json")
            deck = load_deck(path)  # missing file -> empty deck
            self.assertEqual(deck["cards"], [])
            card = add_card(deck, "Capital of France?", "Paris", ["geo"], today=TODAY)
            save_deck(path, deck)

            reloaded = load_deck(path)
            self.assertEqual(len(reloaded["cards"]), 1)
            loaded = get_card(reloaded, card["id"])
            self.assertEqual(loaded["front"], "Capital of France?")
            self.assertEqual(loaded["back"], "Paris")
            self.assertEqual(loaded["tags"], ["geo"])
            self.assertEqual(loaded["due_date"], TODAY.isoformat())  # due immediately
            self.assertEqual(loaded["ef"], 2.5)
            self.assertEqual(loaded["history"], [])

    def test_persistence_save_reload_data_intact_after_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "deck.json")  # parent dir created
            deck = new_deck()
            c1 = add_card(deck, "2+2?", "4", today=TODAY)
            add_card(deck, "H2O?", "water", ["chem"], today=TODAY)
            review_card(deck, c1["id"], 5, today=TODAY)
            review_card(deck, c1["id"], 4, today=TODAY)
            save_deck(path, deck)

            reloaded = load_deck(path)
            self.assertEqual(len(reloaded["cards"]), 2)
            self.assertEqual(reloaded["next_id"], 3)
            card = get_card(reloaded, c1["id"])
            self.assertEqual(card["interval"], 6)
            self.assertEqual(card["repetitions"], 2)
            self.assertEqual(
                card["history"],
                [
                    {"date": TODAY.isoformat(), "grade": 5},
                    {"date": TODAY.isoformat(), "grade": 4},
                ],
            )
            # IDs keep increasing after reload.
            c3 = add_card(reloaded, "new?", "yes", today=TODAY)
            self.assertEqual(c3["id"], 3)


class TestDueCards(unittest.TestCase):
    def test_due_selection_includes_today_and_past_excludes_future(self):
        deck = new_deck()
        past = add_card(deck, "past", "x", today=TODAY - timedelta(days=3))
        today_card = add_card(deck, "today", "x", today=TODAY)
        future = add_card(deck, "future", "x", today=TODAY)
        future["due_date"] = (TODAY + timedelta(days=5)).isoformat()

        due = due_cards(deck, TODAY)
        due_ids = [c["id"] for c in due]
        self.assertIn(past["id"], due_ids)
        self.assertIn(today_card["id"], due_ids)
        self.assertNotIn(future["id"], due_ids)

    def test_reviewed_card_leaves_due_list(self):
        deck = new_deck()
        card = add_card(deck, "q", "a", today=TODAY)
        review_card(deck, card["id"], 5, today=TODAY)  # interval 1 -> due tomorrow
        self.assertEqual(due_cards(deck, TODAY), [])
        self.assertEqual(len(due_cards(deck, TODAY + timedelta(days=1))), 1)


class TestStats(unittest.TestCase):
    def test_retention_rate_and_counts(self):
        deck = new_deck()
        c1 = add_card(deck, "q1", "a1", today=TODAY)
        c2 = add_card(deck, "q2", "a2", today=TODAY)
        review_card(deck, c1["id"], 5, today=TODAY)  # retained
        review_card(deck, c1["id"], 3, today=TODAY)  # retained (>=3)
        review_card(deck, c2["id"], 2, today=TODAY)  # not retained
        review_card(deck, c2["id"], 0, today=TODAY)  # not retained

        stats = compute_stats(deck, TODAY)
        self.assertEqual(stats["total_cards"], 2)
        self.assertEqual(stats["reviews_done"], 4)
        self.assertAlmostEqual(stats["retention_rate"], 0.5)
        self.assertEqual(stats["per_card_reviews"], {c1["id"]: 2, c2["id"]: 2})

    def test_retention_zero_with_no_reviews(self):
        deck = new_deck()
        add_card(deck, "q", "a", today=TODAY)
        stats = compute_stats(deck, TODAY)
        self.assertEqual(stats["retention_rate"], 0.0)
        self.assertEqual(stats["due_today"], 1)
        self.assertEqual(stats["current_streak"], 0)

    def test_current_streak_counts_consecutive_days(self):
        deck = new_deck()
        card = add_card(deck, "q", "a", today=TODAY)
        review_card(deck, card["id"], 5, today=TODAY - timedelta(days=2))
        review_card(deck, card["id"], 5, today=TODAY - timedelta(days=1))
        review_card(deck, card["id"], 5, today=TODAY)
        stats = compute_stats(deck, TODAY)
        self.assertEqual(stats["current_streak"], 3)

    def test_streak_broken_by_gap(self):
        deck = new_deck()
        card = add_card(deck, "q", "a", today=TODAY)
        review_card(deck, card["id"], 5, today=TODAY - timedelta(days=3))
        review_card(deck, card["id"], 5, today=TODAY)
        stats = compute_stats(deck, TODAY)
        self.assertEqual(stats["current_streak"], 1)


if __name__ == "__main__":
    unittest.main()
