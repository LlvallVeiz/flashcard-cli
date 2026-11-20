"""Command-line interface for flashcard-cli (argparse, stdlib only).

Subcommands:
- ``add``    add a card (front/back, optional tags)
- ``list``   list cards (optionally --tag / --due-only)
- ``quiz``   review session over due cards, grades read from stdin
- ``review`` non-interactive single-card review (--id, --grade)
- ``stats``  deck statistics

The deck path is set with the global ``--deck`` option
(default ``deck.json`` in the current directory). Every mutation
is persisted to disk immediately.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from .deck import add_card, compute_stats, due_cards, load_deck, review_card, save_deck

DEFAULT_DECK = "deck.json"


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _format_card(card: dict) -> str:
    tags = ",".join(card.get("tags", [])) or "-"
    return (
        f"[{card['id']}] {card['front']} -> {card['back']} "
        f"(tags: {tags}; due: {card['due_date']}; EF: {card['ef']:.2f}; "
        f"interval: {card['interval']}d; reps: {card['repetitions']}; "
        f"reviews: {len(card.get('history', []))})"
    )


def cmd_add(args, deck: dict) -> int:
    card = add_card(deck, args.front, args.back, _parse_tags(args.tags))
    save_deck(args.deck, deck)
    print(f"Added card [{card['id']}]: {card['front']} -> {card['back']} (due {card['due_date']})")
    return 0


def cmd_list(args, deck: dict) -> int:
    cards = list(deck["cards"])
    if args.due_only:
        due_ids = {c["id"] for c in due_cards(deck)}
        cards = [c for c in cards if c["id"] in due_ids]
    if args.tag:
        cards = [c for c in cards if args.tag in c.get("tags", [])]
    if not cards:
        print("No cards.")
        return 0
    for card in sorted(cards, key=lambda c: c["id"]):
        print(_format_card(card))
    return 0


def cmd_quiz(args, deck: dict, input_fn=None) -> int:
    if input_fn is None:
        input_fn = input
    """Review due cards one by one; grades come from stdin.

    Works with piped stdin: each line is one grade (0-5). EOF or
    an empty line ends the session. Invalid grades are reported
    and that card is skipped (not rescheduled).
    """
    today = date.today()
    cards = due_cards(deck, today)
    if not cards:
        print("No cards due.")
        return 0
    reviewed = 0
    for card in cards:
        print(f"Card [{card['id']}]: {card['front']}")
        print(f"Answer: {card['back']}")
        try:
            raw = input_fn("Grade (0-5): ")
        except EOFError:
            print("Session ended (EOF).")
            break
        raw = raw.strip()
        if raw == "":
            print("Session ended.")
            break
        try:
            grade = int(raw)
            updated = review_card(deck, card["id"], grade, today)
        except (ValueError, KeyError) as exc:
            print(f"Skipped card [{card['id']}]: {exc}")
            continue
        save_deck(args.deck, deck)
        reviewed += 1
        print(
            f"  -> next due {updated['due_date']} "
            f"(interval {updated['interval']}d, EF {updated['ef']:.2f})"
        )
    print(f"Reviewed {reviewed} card(s).")
    return 0


def cmd_review(args, deck: dict) -> int:
    try:
        card = review_card(deck, args.id, args.grade)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    save_deck(args.deck, deck)
    print(
        f"Reviewed card [{card['id']}] grade {args.grade}: "
        f"next due {card['due_date']} (interval {card['interval']}d, EF {card['ef']:.2f})"
    )
    return 0


def cmd_stats(args, deck: dict) -> int:
    stats = compute_stats(deck)
    print(f"Total cards: {stats['total_cards']}")
    print(f"Due today: {stats['due_today']}")
    print(f"Reviews done: {stats['reviews_done']}")
    print(f"Retention rate: {stats['retention_rate']:.1%}")
    print(f"Current streak: {stats['current_streak']} day(s)")
    print("Reviews per card:")
    if not stats["per_card_reviews"]:
        print("  (none)")
    for card_id in sorted(stats["per_card_reviews"]):
        print(f"  card [{card_id}]: {stats['per_card_reviews'][card_id]} review(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flashcard-cli",
        description="Spaced-repetition flashcards (SM-2) with a JSON deck file.",
    )
    parser.add_argument(
        "--deck",
        default=DEFAULT_DECK,
        help="path to the JSON deck file (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a new card (due immediately)")
    p_add.add_argument("--front", required=True, help="front (question) text")
    p_add.add_argument("--back", required=True, help="back (answer) text")
    p_add.add_argument("--tags", default="", help="comma-separated tags, e.g. 'geo,exam'")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list cards")
    p_list.add_argument("--tag", default=None, help="only cards with this tag")
    p_list.add_argument("--due-only", action="store_true", help="only cards due today or earlier")
    p_list.set_defaults(func=cmd_list)

    p_quiz = sub.add_parser("quiz", help="review due cards (grades read from stdin)")
    p_quiz.set_defaults(func=cmd_quiz)

    p_review = sub.add_parser("review", help="review a single card non-interactively")
    p_review.add_argument("--id", type=int, required=True, help="card id")
    p_review.add_argument("--grade", type=int, required=True, help="quality grade 0-5")
    p_review.set_defaults(func=cmd_review)

    p_stats = sub.add_parser("stats", help="show deck statistics")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    deck = load_deck(args.deck)
    return args.func(args, deck)


if __name__ == "__main__":
    raise SystemExit(main())
