"""SM-2 spaced-repetition scheduling algorithm.

Implements the classic SM-2 algorithm (SuperMemo 2) as described in
the task specification:

- Ease factor (EF) starts at 2.5, minimum 1.3.
- Interval progression: I(1) = 1 day, I(2) = 6 days,
  I(n) = I(n-1) * EF for n > 2.
- Quality grades are integers 0..5.
- EF update: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
- If q < 3, the repetition count is reset to 0 and the interval
  is reset to 1 day.

The interval for repetition n > 2 is computed with the EF value
held *before* this review's EF update; the updated EF is then
stored for the next review. Intervals are rounded to whole days
with a minimum of 1.
"""

from __future__ import annotations

from datetime import date, timedelta

INITIAL_EF = 2.5
MIN_EF = 1.3


def update_ef(ef: float, grade: int) -> float:
    """Return the new ease factor after a review with ``grade``.

    EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02)), floored at 1.3.
    """
    if not isinstance(grade, int) or isinstance(grade, bool):
        raise ValueError("grade must be an int between 0 and 5")
    if grade < 0 or grade > 5:
        raise ValueError("grade must be between 0 and 5")
    diff = 5 - grade
    new_ef = ef + (0.1 - diff * (0.08 + diff * 0.02))
    return max(MIN_EF, new_ef)


def next_interval(repetitions: int, interval: int, ef: float, grade: int) -> tuple[int, int]:
    """Compute (new_repetitions, new_interval) for a review.

    ``repetitions`` is the count of consecutive successful reviews
    (grade >= 3) *before* this review, ``interval`` is the previous
    interval in days, and ``ef`` is the ease factor before this
    review's EF update.
    """
    if grade < 3:
        return 0, 1
    if repetitions == 0:
        return 1, 1
    if repetitions == 1:
        return 2, 6
    new_interval = int(round(interval * ef))
    if new_interval < 1:
        new_interval = 1
    return repetitions + 1, new_interval


def review_schedule(
    repetitions: int,
    interval: int,
    ef: float,
    grade: int,
    today: date | None = None,
) -> dict:
    """Apply one SM-2 review and return the updated scheduling fields.

    Returns a dict with keys ``ef``, ``interval``, ``repetitions``
    and ``due_date`` (a ``datetime.date``). ``today`` defaults to
    ``date.today()`` and exists so tests can pin the current date.
    """
    if today is None:
        today = date.today()
    # Validate grade early (update_ef also validates).
    if not isinstance(grade, int) or isinstance(grade, bool) or grade < 0 or grade > 5:
        raise ValueError("grade must be an int between 0 and 5")
    new_repetitions, new_interval = next_interval(repetitions, interval, ef, grade)
    new_ef = update_ef(ef, grade)
    due = today + timedelta(days=new_interval)
    return {
        "ef": new_ef,
        "interval": new_interval,
        "repetitions": new_repetitions,
        "due_date": due,
    }
