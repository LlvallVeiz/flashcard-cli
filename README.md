# flashcard-cli

A spaced-repetition flashcard command-line tool implementing the
**SM-2** scheduling algorithm. Pure Python 3.12 standard library —
no third-party dependencies. Cards and their full review history
live in a single JSON deck file.

## Features

- Add cards with optional tags; new cards are due immediately.
- List cards, optionally filtered by tag or due-only.
- Interactive `quiz` session over due cards (grades read from
  stdin, so it also works with piped input).
- Non-interactive single-card `review` for scripting.
- `stats`: total cards, due-today count, reviews done, retention
  rate, current streak, and per-card review counts.
- Every mutation is persisted to the JSON deck file immediately.

## The SM-2 algorithm

SM-2 schedules each card's next review based on how well you
remembered it. After each review you grade your recall with a
quality score **q** from 0 (complete blackout) to 5 (perfect
recall). Each card carries:

- **EF** — the *ease factor*, starting at **2.5**, minimum **1.3**
- **I** — the current interval in days
- **repetitions** — consecutive successful reviews (q ≥ 3)

### Interval progression

```
I(1) = 1 day
I(2) = 6 days
I(n) = round(I(n-1) × EF)     for n > 2
```

The multiplication uses the EF held *before* this review's EF
update; the updated EF is stored for the next review. Intervals
are whole days, minimum 1. The next due date is
`today + I(n) days`.

### Ease factor update

```
EF' = EF + (0.1 − (5−q) × (0.08 + (5−q) × 0.02))
EF' = max(EF', 1.3)
```

So q = 5 raises EF by 0.1, q = 4 leaves it unchanged, and lower
grades decrease it (q = 0 lowers it by 0.8).

### Failed reviews

If **q < 3**, the repetition count resets to 0 and the interval
resets to 1 day — the card is relearned from the start of the
progression (its EF still updates by the formula above).

### Grade guide

| q | Meaning |
|---|---------|
| 5 | Perfect recall |
| 4 | Correct, with hesitation |
| 3 | Correct, with serious difficulty |
| 2 | Incorrect, but the answer felt familiar |
| 1 | Incorrect, answer barely recalled |
| 0 | Complete blackout |

## Usage

Run everything through the module entry point. The global
`--deck` option selects the deck file (default: `deck.json` in
the current directory); it goes **before** the subcommand.

```bash
cd flashcard-cli

# Add cards (due immediately)
python3 -m flashcard_cli --deck mydeck.json add \
    --front "Capital of France?" --back "Paris" --tags geo,exam
python3 -m flashcard_cli --deck mydeck.json add \
    --front "H2O is?" --back "Water"

# List cards (optionally filtered)
python3 -m flashcard_cli --deck mydeck.json list
python3 -m flashcard_cli --deck mydeck.json list --tag geo
python3 -m flashcard_cli --deck mydeck.json list --due-only

# Interactive quiz over due cards: shows front + answer, asks 0-5.
# Works with piped stdin too:
printf '5\n4\n' | python3 -m flashcard_cli --deck mydeck.json quiz

# Non-interactive single-card review
python3 -m flashcard_cli --deck mydeck.json review --id 1 --grade 5

# Statistics
python3 -m flashcard_cli --deck mydeck.json stats
```

Example `stats` output:

```
Total cards: 2
Due today: 1
Reviews done: 3
Retention rate: 66.7%
Current streak: 1 day(s)
Reviews per card:
  card [1]: 2 review(s)
  card [2]: 1 review(s)
```

**Retention rate** is the fraction of all reviews with grade ≥ 3.
**Current streak** is the number of consecutive days with at
least one review, counting back from today (or from yesterday if
today has no review yet).

In `quiz`, an empty line or EOF ends the session; an invalid
grade skips that card without rescheduling it.

## Deck file format

The deck is one JSON object. Dates are ISO strings
(`YYYY-MM-DD`). Each card stores its scheduling state and a
`history` list of `{"date", "grade"}` entries.

```json
{
  "next_id": 3,
  "cards": [
    {
      "id": 1,
      "front": "Capital of France?",
      "back": "Paris",
      "tags": ["geo", "exam"],
      "ef": 2.6,
      "interval": 1,
      "repetitions": 1,
      "due_date": "2026-11-21",
      "history": [
        {"date": "2026-11-20", "grade": 5}
      ]
    }
  ]
}
```

A missing deck file is treated as an empty deck and created on
the first mutation. Writes are atomic (write to a temp file,
then rename).

## Project layout

```
flashcard_cli/
  __init__.py     package metadata
  __main__.py     `python3 -m flashcard_cli` entry point
  sm2.py          SM-2 scheduling (pure functions, testable "today")
  deck.py         deck model, JSON storage, statistics
  storage.py      storage interface (load_deck / save_deck / new_deck)
  cli.py          argparse CLI (add / list / quiz / review / stats)
tests/
  test_sm2.py     interval progression, EF floor, reset on failure
  test_deck.py    persistence, due-card selection, statistics
  test_cli.py     CLI end-to-end (incl. piped quiz input)
```

## Running the tests

```bash
cd flashcard-cli
python3 -m unittest discover -s tests -v
```

All tests use only the standard library (`unittest`, `tempfile`)
and pin "today" to a fixed date, so they are fully deterministic.
