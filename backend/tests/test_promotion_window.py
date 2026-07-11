"""Promotions are restricted to the end-of-year window: after Term 3 closes
and before the next Term 1 begins (standard Kenyan calendar when no term
dates are configured: Term 1 starts Jan 2, Term 3 ends Nov 7)."""
from datetime import date

from students import promotion_window_open


def test_blocked_during_the_school_year(db_session):
    assert promotion_window_open(db_session, date(2026, 7, 14)) is False   # Term 2
    assert promotion_window_open(db_session, date(2026, 2, 10)) is False   # Term 1
    assert promotion_window_open(db_session, date(2026, 9, 15)) is False   # Term 3
    assert promotion_window_open(db_session, date(2026, 4, 20)) is False   # Term 1-2 holiday


def test_open_after_term_3_ends(db_session):
    assert promotion_window_open(db_session, date(2026, 11, 20)) is True
    assert promotion_window_open(db_session, date(2026, 12, 31)) is True


def test_open_before_term_1_begins(db_session):
    assert promotion_window_open(db_session, date(2026, 1, 1)) is True
    assert promotion_window_open(db_session, date(2026, 1, 2)) is False    # Term 1 day one
