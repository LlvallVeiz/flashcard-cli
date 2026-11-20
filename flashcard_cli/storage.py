"""Storage layer: thin re-export of the deck JSON persistence.

Kept as its own module so callers (and tests) can depend on a
stable storage interface: ``load_deck`` / ``save_deck`` /
``new_deck``. The implementation lives in ``deck.py``.
"""

from .deck import load_deck, new_deck, save_deck

__all__ = ["load_deck", "save_deck", "new_deck"]
