"""Deck model, JSON storage, and statistics for flashcard-cli.

A deck is a dict of the form::

    {
        "next_id": 3,
        "cards": [
            {
                "id": 1,
                "front": "Capital of France?",
                "back": "Paris",
                "tags": ["geography"],
                "ef": 2.5,
                "interval": 0,
                "repetitions": 0,
                "due_date": "2026-11-20",
                "history": [{"date": "2026-11-20", "grade": 5}]
            }
        ]
    }

Dates are stored as ISO strings (``YYYY-MM-DD``) in JSON and
parsed back to ``datetime.date`` where scheduling needs them.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

from .sm2 import INITIAL_EF, review_schedule


def new_deck() -> dict:
    """Return an empty deck."""
    return {"next_id": 1, "cards": []}


def load_deck(path: str) -> dict:
    """Load a deck from ``path``; return an empty deck if missing."""
    if not os.path.exists(path):
        return new_deck()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Tolerate a bare list of cards from hand-written files.
    if isinstance(data, list):
        cards = data
        next_id = max((c.get("id", 0) for c in cards), default=0) + 1
        return {"next_id": next_id, "cards": cards}
    data.setdefault("cards", [])
    if "next_id" not in data:
        data["next_id"] = max((c.get("id", 0) for c in data["cards"]), default=0) + 1
    return data


def save_deck(path: str, deck: dict) -> None:
    """Persist ``deck`` to ``path`` as JSON (creating parent dirs)."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(deck, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp_path, path)


def add_card(deck: dict, front: str, back: str, tags=None, today: date | None = None) -> dict:
    """Append a new card to ``deck`` and return it.

    New cards are due immediately (``due_date`` == today), start
    with EF 2.5, interval 0 and repetitions 0.
    """
    if today is None:
        today = date.today()
    if tags is None:
        tags = []
    card = {
        "id": deck["next_id"],
        "front": front,
        "back": back,
        "tags": list(tags),
        "ef": INITIAL_EF,
        "interval": 0,
        "repetitions": 0,
        "due_date": today.isoformat(),
        "history": [],
    }
    deck["next_id"] += 1
    deck["cards"].append(card)
    return card


def get_card(deck: dict, card_id: int) -> dict | None:
    """Return the card with ``card_id`` or None."""
    for card in deck["cards"]:
        if card["id"] == card_id:
            return card
    return None


def parse_date(value) -> date:
    """Parse an ISO date string (or pass through a date)."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def due_cards(deck: dict, today: date | None = None) -> list[dict]:
    """Return cards whose due date is today or earlier, ordered by id."""
    if today is None:
        today = date.today()
    result = [c for c in deck["cards"] if parse_date(c["due_date"]) <= today]
    result.sort(key=lambda c: c["id"])
    return result


def review_card(deck: dict, card_id: int, grade: int, today: date | None = None) -> dict:
    """Apply an SM-2 review to one card and record it in history.

    Raises KeyError if the card does not exist and ValueError for
    an out-of-range grade.
    """
    if today is None:
        today = date.today()
    card = get_card(deck, card_id)
    if card is None:
        raise KeyError(f"no card with id {card_id}")
    sched = review_schedule(
        repetitions=card["repetitions"],
        interval=card["interval"],
        ef=card["ef"],
        grade=grade,
        today=today,
    )
    card["ef"] = sched["ef"]
    card["interval"] = sched["interval"]
    card["repetitions"] = sched["repetitions"]
    card["due_date"] = sched["due_date"].isoformat()
    card["history"].append({"date": today.isoformat(), "grade": grade})
    return card


def compute_stats(deck: dict, today: date | None = None) -> dict:
    """Compute deck statistics.

    Returns a dict with:
    - ``total_cards``: number of cards in the deck
    - ``due_today``: cards with due date <= today
    - ``reviews_done``: total history entries across all cards
    - ``retention_rate``: fraction of reviews with grade >= 3
      (0.0 when there are no reviews)
    - ``current_streak``: consecutive days with at least one
      review, counting back from today (or from yesterday if
      today has no review yet, so the streak is not broken
      until a full day is missed)
    - ``per_card_reviews``: {card_id: review_count}
    """
    if today is None:
        today = date.today()
    cards = deck["cards"]
    reviews_done = 0
    retained = 0
    review_dates: set[date] = set()
    per_card: dict[int, int] = {}
    for card in cards:
        history = card.get("history", [])
        per_card[card["id"]] = len(history)
        for entry in history:
            reviews_done += 1
            if entry["grade"] >= 3:
                retained += 1
            review_dates.add(parse_date(entry["date"]))
    retention = (retained / reviews_done) if reviews_done else 0.0

    streak = 0
    if today in review_dates:
        cursor = today
    elif (today - timedelta(days=1)) in review_dates:
        cursor = today - timedelta(days=1)
    else:
        cursor = None
    while cursor is not None and cursor in review_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)

    return {
        "total_cards": len(cards),
        "due_today": len(due_cards(deck, today)),
        "reviews_done": reviews_done,
        "retention_rate": retention,
        "current_streak": streak,
        "per_card_reviews": per_card,
    }
