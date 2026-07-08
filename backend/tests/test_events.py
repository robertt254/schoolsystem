import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from events import compute_current_term, ALL_TERMS

# Build MOCK_RANGES using the actual ALL_TERMS constant to prevent
# drift and test failures if ALL_TERMS changes in the future.
MOCK_RANGES = {
    ALL_TERMS[0]: (date(2024, 1, 10), date(2024, 4, 10)),
    ALL_TERMS[1]: (date(2024, 5, 10), date(2024, 8, 10)),
    ALL_TERMS[2]: (date(2024, 9, 10), date(2024, 11, 10)),
}

@pytest.fixture
def mock_db():
    return MagicMock()

@patch("events._term_ranges")
def test_compute_current_term_in_range(mock_term_ranges, mock_db):
    mock_term_ranges.return_value = (MOCK_RANGES, False)

    # Inside Term 1
    today = date(2024, 2, 15)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[0]
    assert source == "configured"

    # Inside Term 2
    today = date(2024, 6, 15)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[1]
    assert source == "configured"

    # Inside Term 3
    today = date(2024, 10, 15)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[2]
    assert source == "configured"

@patch("events._term_ranges")
def test_compute_current_term_holiday_gap(mock_term_ranges, mock_db):
    mock_term_ranges.return_value = (MOCK_RANGES, False)

    # Gap between Term 1 and Term 2 (April 11 to May 9)
    today = date(2024, 4, 20)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[1]
    assert source == "configured"

    # Gap between Term 2 and Term 3 (August 11 to Sept 9)
    today = date(2024, 8, 20)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[2]
    assert source == "configured"

@patch("events._term_ranges")
def test_compute_current_term_before_first_term(mock_term_ranges, mock_db):
    mock_term_ranges.return_value = (MOCK_RANGES, False)

    # Before Term 1 begins
    today = date(2024, 1, 5)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[0]
    assert source == "configured"

@patch("events._term_ranges")
def test_compute_current_term_after_last_term(mock_term_ranges, mock_db):
    mock_term_ranges.return_value = (MOCK_RANGES, False)

    # After Term 3 ends
    today = date(2024, 11, 20)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == "Term 3" # Fallback if beyond all terms usually defaults to Term 3
    assert source == "configured"

@patch("events._term_ranges")
@patch("events.date")
def test_compute_current_term_today_fallback(mock_date, mock_term_ranges, mock_db):
    mock_term_ranges.return_value = (MOCK_RANGES, True)
    mock_date.today.return_value = date(2024, 6, 15)

    year, term, source = compute_current_term(mock_db)
    assert year == 2024
    assert term == ALL_TERMS[1]
    assert source == "default"

@patch("events._term_ranges")
def test_compute_current_term_source_default(mock_term_ranges, mock_db):
    # Test that `source` correctly reflects `is_default=True`
    mock_term_ranges.return_value = (MOCK_RANGES, True)

    today = date(2024, 2, 15)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[0]
    assert source == "default"

@patch("events._term_ranges")
def test_compute_current_term_missing_ranges(mock_term_ranges, mock_db):
    # Missing Term 2 entirely in configured ranges
    ranges_missing_t2 = {
        ALL_TERMS[0]: (date(2024, 1, 10), date(2024, 4, 10)),
        ALL_TERMS[2]: (date(2024, 9, 10), date(2024, 11, 10)),
    }
    mock_term_ranges.return_value = (ranges_missing_t2, False)

    # In the gap after Term 1 ends (should jump straight to Term 3)
    today = date(2024, 5, 15)
    year, term, source = compute_current_term(mock_db, today)
    assert year == 2024
    assert term == ALL_TERMS[2]
    assert source == "configured"
