"""
Tests for Step 06 — Date Filter for Profile Page
=================================================
Spec: .claude/specs/06-date-filter.md

These tests verify the date-range filter behaviour added to GET /profile and
the supporting query helpers (get_summary_stats, get_recent_transactions,
get_category_breakdown). Tests are written against the spec, not the
implementation.

Fixture strategy
----------------
We patch `database.db.DB_PATH` to an isolated temp file so no test ever
touches the production database.  A shared helper `_reset_db` re-creates the
schema and inserts a deterministic set of expenses before every test.

All expense dates in the fixture span 2026-04-01 → 2026-06-30 so we can
exercise start-only, end-only, and bounded filters with predictable results.
"""

import os
import sqlite3
import tempfile

import pytest
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Redirect db module to a temp file BEFORE importing anything from the app
# ---------------------------------------------------------------------------
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import database.db as db_mod  # noqa: E402 — must come after tmp setup

db_mod.DB_PATH = _tmp_db.name

from database.queries import (  # noqa: E402
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)
from app import app as flask_app  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic fixture data
#
# USER 1  — has expenses spread across April, May, June 2026
# USER 2  — no expenses (used for zero-data edge cases)
#
# April expenses:  Food 10.00 (Apr-05), Transport 50.00 (Apr-20)
# May expenses:    Bills 120.00 (May-05), Health 35.75 (May-10)
# June expenses:   Shopping 80.00 (Jun-01), Food 25.00 (Jun-15)
#
# All-time total = 10 + 50 + 120 + 35.75 + 80 + 25 = 320.75
# ---------------------------------------------------------------------------

EXPENSES = [
    (1, 10.00,  "Food",      "2026-04-05", "April lunch"),
    (1, 50.00,  "Transport", "2026-04-20", "April bus pass"),
    (1, 120.00, "Bills",     "2026-05-05", "Electricity"),
    (1, 35.75,  "Health",    "2026-05-10", "Pharmacy"),
    (1, 80.00,  "Shopping",  "2026-06-01", "New shoes"),
    (1, 25.00,  "Food",      "2026-06-15", "June groceries"),
]

ALL_TIME_TOTAL = sum(e[1] for e in EXPENSES)  # 320.75
ALL_TIME_COUNT = len(EXPENSES)               # 6


def _reset_db():
    """Drop and recreate tables, then seed deterministic data."""
    conn = sqlite3.connect(_tmp_db.name)
    conn.execute("DROP TABLE IF EXISTS expenses")
    conn.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()

    db_mod.init_db()

    conn = db_mod.get_db()
    conn.execute(
        "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?,?,?,?,?)",
        (1, "Alice", "alice@example.com", generate_password_hash("password1"), "2026-01-01 00:00:00"),
    )
    conn.execute(
        "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?,?,?,?,?)",
        (2, "Bob", "bob@example.com", generate_password_hash("password2"), "2026-01-01 00:00:00"),
    )
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?,?,?,?,?)",
        EXPENSES,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the database before every test."""
    _reset_db()
    yield


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def auth_client(client):
    """Test client pre-authenticated as User 1 (Alice)."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Alice"
    return client


# ===========================================================================
# Auth guard
# ===========================================================================

class TestAuthGuard:
    def test_unauthenticated_profile_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302, "Unauthenticated /profile should redirect"
        assert "/login" in resp.headers["Location"], "Redirect target must be /login"

    def test_unauthenticated_profile_with_date_params_redirects(self, client):
        resp = client.get("/profile?start=2026-05-01&end=2026-05-31")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ===========================================================================
# No-filter baseline — existing all-time behaviour must be unchanged
# ===========================================================================

class TestNoFilterBaseline:
    def test_profile_loads_200_no_params(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200, "Authenticated /profile should return 200"

    def test_all_time_total_shown(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        assert "320.75" in html, "All-time total should be visible without filter"

    def test_all_time_transaction_count(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        # 6 transactions in fixture
        assert "6" in html, "All transaction count should be present without filter"

    def test_all_time_top_category_is_bills(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        assert "Bills" in html, "Top category (Bills, 120.00) should appear without filter"

    def test_all_time_categories_present(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        for category in ("Food", "Transport", "Bills", "Health", "Shopping"):
            assert category in html, f"Category '{category}' should appear in all-time view"

    def test_user_name_shown(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        assert "Alice" in html, "Logged-in user name must appear on profile page"


# ===========================================================================
# Filter form in template
# ===========================================================================

class TestFilterFormTemplate:
    def test_date_input_start_present(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        assert 'type="date"' in html or "type='date'" in html, \
            "Profile page must contain date inputs (type=date)"

    def test_filter_form_submits_via_get(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        # The form must use method="get" (case-insensitive)
        assert 'method="get"' in html.lower() or "method='get'" in html.lower(), \
            "Filter form must submit via GET"

    def test_clear_link_points_to_profile_no_query_string(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        # Clear link should be a plain href to /profile (no start/end params)
        assert 'href="/profile"' in html or "href='/profile'" in html, \
            "Clear link must point to /profile with no query string"

    def test_sticky_start_input_prefilled(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "2026-05-01" in html, \
            "Start date input must be pre-filled with the submitted value"

    def test_sticky_end_input_prefilled(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "2026-05-31" in html, \
            "End date input must be pre-filled with the submitted value"

    def test_no_sticky_values_when_no_filter(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode()
        # Neither of our specific filter dates should appear in the default view
        assert "2026-05-01" not in html, \
            "No filter date should appear in input when no params were supplied"


# ===========================================================================
# Start-only filter
# ===========================================================================

class TestStartOnlyFilter:
    def test_start_only_returns_200(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01")
        assert resp.status_code == 200

    def test_start_only_excludes_earlier_transactions(self, auth_client):
        # start=2026-05-01 should exclude April expenses (Apr-05, Apr-20)
        resp = auth_client.get("/profile?start=2026-05-01")
        html = resp.data.decode()
        assert "April lunch" not in html, \
            "Transactions before start date must not appear"
        assert "April bus pass" not in html, \
            "Transactions before start date must not appear"

    def test_start_only_includes_on_boundary(self, auth_client):
        # 2026-05-05 is exactly on the boundary — must be included
        resp = auth_client.get("/profile?start=2026-05-05")
        html = resp.data.decode()
        assert "Electricity" in html, \
            "Transaction on the start date boundary must be included"

    def test_start_only_total_is_correct(self, auth_client):
        # start=2026-05-01 => May + June = 120.00+35.75+80.00+25.00 = 260.75
        resp = auth_client.get("/profile?start=2026-05-01")
        html = resp.data.decode()
        assert "260.75" in html, \
            "Total after start-only filter should be 260.75"

    def test_start_only_sticky_input_filled(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01")
        html = resp.data.decode()
        assert "2026-05-01" in html, \
            "Start value must be sticky in the form after start-only filter"


# ===========================================================================
# End-only filter
# ===========================================================================

class TestEndOnlyFilter:
    def test_end_only_returns_200(self, auth_client):
        resp = auth_client.get("/profile?end=2026-04-30")
        assert resp.status_code == 200

    def test_end_only_excludes_later_transactions(self, auth_client):
        # end=2026-04-30 should exclude May and June expenses
        resp = auth_client.get("/profile?end=2026-04-30")
        html = resp.data.decode()
        assert "Electricity" not in html, \
            "Transactions after end date must not appear"
        assert "New shoes" not in html, \
            "Transactions after end date must not appear"

    def test_end_only_includes_on_boundary(self, auth_client):
        # 2026-04-20 is exactly on the boundary — must be included
        resp = auth_client.get("/profile?end=2026-04-20")
        html = resp.data.decode()
        assert "April bus pass" in html, \
            "Transaction on the end date boundary must be included"

    def test_end_only_total_is_correct(self, auth_client):
        # end=2026-04-30 => April only = 10.00 + 50.00 = 60.00
        resp = auth_client.get("/profile?end=2026-04-30")
        html = resp.data.decode()
        assert "60.00" in html, \
            "Total after end-only filter should be 60.00"

    def test_end_only_sticky_input_filled(self, auth_client):
        resp = auth_client.get("/profile?end=2026-04-30")
        html = resp.data.decode()
        assert "2026-04-30" in html, \
            "End value must be sticky in the form after end-only filter"


# ===========================================================================
# Bounded filter (start + end)
# ===========================================================================

class TestBoundedFilter:
    def test_bounded_filter_returns_200(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        assert resp.status_code == 200

    def test_bounded_filter_includes_range_transactions(self, auth_client):
        # May only: Bills (May-05), Health (May-10)
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "Electricity" in html, "May Bills expense must appear in May filter"
        assert "Pharmacy" in html, "May Health expense must appear in May filter"

    def test_bounded_filter_excludes_out_of_range_transactions(self, auth_client):
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "April lunch" not in html, "April expense must be excluded from May filter"
        assert "New shoes" not in html, "June expense must be excluded from May filter"

    def test_bounded_filter_total_is_correct(self, auth_client):
        # May: 120.00 + 35.75 = 155.75
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "155.75" in html, "Total for May filter should be 155.75"

    def test_bounded_filter_transaction_count(self, auth_client):
        # May has exactly 2 transactions
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "2" in html, "Transaction count for May should be 2"

    def test_bounded_filter_top_category(self, auth_client):
        # In May, Bills (120.00) > Health (35.75) => Bills is top
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "Bills" in html, "Top category in May filter must be Bills"

    def test_bounded_filter_category_breakdown_correct(self, auth_client):
        # In May only Bills and Health should appear in the breakdown
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        assert "Bills" in html
        assert "Health" in html

    def test_bounded_filter_excludes_other_categories(self, auth_client):
        # Transport and Shopping have no May expenses
        resp = auth_client.get("/profile?start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        # Transport only appears in April; Shopping only in June
        # We check the description strings which are unique to their months
        assert "April bus pass" not in html
        assert "June groceries" not in html

    def test_single_day_filter(self, auth_client):
        # start == end => only that one day
        resp = auth_client.get("/profile?start=2026-05-05&end=2026-05-05")
        html = resp.data.decode()
        assert "Electricity" in html, "Expense exactly on start=end date must appear"
        assert "Pharmacy" not in html, "Expense outside single-day range must not appear"
        assert "120.00" in html, "Total for single-day filter should be 120.00"


# ===========================================================================
# start > end — must fall back to all-time data
# ===========================================================================

class TestStartGreaterThanEnd:
    def test_start_gt_end_returns_200(self, auth_client):
        resp = auth_client.get("/profile?start=2026-06-01&end=2026-04-01")
        assert resp.status_code == 200

    def test_start_gt_end_shows_all_time_total(self, auth_client):
        resp = auth_client.get("/profile?start=2026-06-01&end=2026-04-01")
        html = resp.data.decode()
        assert "320.75" in html, \
            "When start > end, all-time total must be shown"

    def test_start_gt_end_shows_all_time_count(self, auth_client):
        resp = auth_client.get("/profile?start=2026-06-01&end=2026-04-01")
        html = resp.data.decode()
        # All 6 transactions — count "6" must appear
        assert "6" in html, \
            "When start > end, all transaction count must be shown"

    def test_start_gt_end_inputs_not_prefilled(self, auth_client):
        # Spec says both are silently ignored — inputs should NOT show the bad values
        resp = auth_client.get("/profile?start=2026-06-01&end=2026-04-01")
        html = resp.data.decode()
        assert "2026-06-01" not in html, \
            "Discarded start value must not be pre-filled in the form"
        assert "2026-04-01" not in html, \
            "Discarded end value must not be pre-filled in the form"


# ===========================================================================
# Invalid / empty date params — must not crash and must fall back to all-time
# ===========================================================================

class TestInvalidDateParams:
    @pytest.mark.parametrize("query_string", [
        "start=&end=",
        "start=not-a-date&end=also-bad",
        "start=99999&end=00000",
        "start=2026-13-40&end=2026-00-00",
        "start='; DROP TABLE expenses; --&end=2026-05-31",
    ])
    def test_invalid_params_do_not_crash(self, auth_client, query_string):
        resp = auth_client.get(f"/profile?{query_string}")
        assert resp.status_code == 200, \
            f"Invalid date params ({query_string!r}) must not cause a 500 error"

    def test_empty_string_params_show_all_time_data(self, auth_client):
        resp = auth_client.get("/profile?start=&end=")
        html = resp.data.decode()
        assert "320.75" in html, \
            "Empty start/end params must fall back to all-time total"

    def test_sql_injection_attempt_safe(self, auth_client):
        # Parameterised queries should neutralise this; the page must return 200
        resp = auth_client.get("/profile?start='; DROP TABLE expenses; --&end=2026-05-31")
        assert resp.status_code == 200, "SQL injection attempt must not crash the app"


# ===========================================================================
# No matching expenses in range
# ===========================================================================

class TestEmptyRangeResults:
    def test_range_with_no_expenses_returns_200(self, auth_client):
        # Year 2020 has no fixture data
        resp = auth_client.get("/profile?start=2020-01-01&end=2020-12-31")
        assert resp.status_code == 200

    def test_range_with_no_expenses_shows_zero_total(self, auth_client):
        resp = auth_client.get("/profile?start=2020-01-01&end=2020-12-31")
        html = resp.data.decode()
        assert "0.00" in html, \
            "Total should be 0.00 when date range contains no expenses"

    def test_range_with_no_expenses_shows_zero_count(self, auth_client):
        resp = auth_client.get("/profile?start=2020-01-01&end=2020-12-31")
        html = resp.data.decode()
        assert "0" in html, \
            "Transaction count should be 0 when date range contains no expenses"


# ===========================================================================
# DB unit tests — get_summary_stats with date filters
# ===========================================================================

class TestGetSummaryStatsDateFilter:
    def test_no_filter_returns_all_time(self):
        stats = get_summary_stats(1)
        assert stats["total_spent"] == "320.75", "All-time total must be 320.75"
        assert stats["transaction_count"] == 6, "All-time count must be 6"

    def test_start_date_only_filters_correctly(self):
        # start_date=2026-05-01 => May+June = 260.75
        stats = get_summary_stats(1, start_date="2026-05-01")
        assert stats["total_spent"] == "260.75", \
            "start_date filter total should be 260.75"
        assert stats["transaction_count"] == 4, \
            "start_date filter count should be 4"

    def test_end_date_only_filters_correctly(self):
        # end_date=2026-04-30 => April = 60.00
        stats = get_summary_stats(1, end_date="2026-04-30")
        assert stats["total_spent"] == "60.00", \
            "end_date filter total should be 60.00"
        assert stats["transaction_count"] == 2, \
            "end_date filter count should be 2"

    def test_bounded_filter_returns_correct_total(self):
        # May: 155.75
        stats = get_summary_stats(1, start_date="2026-05-01", end_date="2026-05-31")
        assert stats["total_spent"] == "155.75", \
            "Bounded filter total should be 155.75"
        assert stats["transaction_count"] == 2, \
            "Bounded filter count should be 2"

    def test_bounded_filter_correct_top_category(self):
        # May: Bills (120) > Health (35.75)
        stats = get_summary_stats(1, start_date="2026-05-01", end_date="2026-05-31")
        assert stats["top_category"] == "Bills", \
            "Top category in May should be Bills"

    def test_empty_range_returns_zero_stats(self):
        stats = get_summary_stats(1, start_date="2020-01-01", end_date="2020-12-31")
        assert stats["total_spent"] == "0.00", "Empty range must return 0.00"
        assert stats["transaction_count"] == 0, "Empty range must return count 0"
        assert stats["top_category"] == "\u2014", \
            "Empty range top_category must be em-dash"

    def test_none_params_do_not_filter(self):
        # Explicitly passing None should produce all-time results
        stats = get_summary_stats(1, start_date=None, end_date=None)
        assert stats["transaction_count"] == 6


# ===========================================================================
# DB unit tests — get_recent_transactions with date filters
# ===========================================================================

class TestGetRecentTransactionsDateFilter:
    def test_no_filter_returns_all_transactions(self):
        txs = get_recent_transactions(1)
        assert len(txs) == 6, "No filter should return all 6 transactions"

    def test_start_date_excludes_earlier(self):
        txs = get_recent_transactions(1, start_date="2026-05-01")
        descriptions = [t["description"] for t in txs]
        assert "April lunch" not in descriptions, \
            "April transaction must be excluded by start_date filter"
        assert "April bus pass" not in descriptions

    def test_start_date_includes_boundary(self):
        txs = get_recent_transactions(1, start_date="2026-05-05")
        descriptions = [t["description"] for t in txs]
        assert "Electricity" in descriptions, \
            "Transaction on start_date boundary must be included"

    def test_end_date_excludes_later(self):
        txs = get_recent_transactions(1, end_date="2026-04-30")
        descriptions = [t["description"] for t in txs]
        assert "Electricity" not in descriptions, \
            "May transaction must be excluded by end_date filter"

    def test_end_date_includes_boundary(self):
        txs = get_recent_transactions(1, end_date="2026-04-20")
        descriptions = [t["description"] for t in txs]
        assert "April bus pass" in descriptions, \
            "Transaction on end_date boundary must be included"

    def test_bounded_filter_returns_only_range(self):
        txs = get_recent_transactions(1, start_date="2026-05-01", end_date="2026-05-31")
        assert len(txs) == 2, "Bounded May filter should return exactly 2 transactions"
        descriptions = [t["description"] for t in txs]
        assert "Electricity" in descriptions
        assert "Pharmacy" in descriptions

    def test_results_ordered_newest_first(self):
        txs = get_recent_transactions(1, start_date="2026-05-01", end_date="2026-05-31")
        # May-10 (Pharmacy) should appear before May-05 (Electricity) in desc order
        assert txs[0]["description"] == "Pharmacy", \
            "Most recent transaction must be first"
        assert txs[1]["description"] == "Electricity"

    def test_empty_range_returns_empty_list(self):
        txs = get_recent_transactions(1, start_date="2020-01-01", end_date="2020-12-31")
        assert txs == [], "Empty range must return empty list"

    def test_none_params_return_all(self):
        txs = get_recent_transactions(1, start_date=None, end_date=None)
        assert len(txs) == 6


# ===========================================================================
# DB unit tests — get_category_breakdown with date filters
# ===========================================================================

class TestGetCategoryBreakdownDateFilter:
    def test_no_filter_all_categories(self):
        cats = get_category_breakdown(1)
        names = [c["name"] for c in cats]
        assert "Food" in names
        assert "Transport" in names
        assert "Bills" in names
        assert "Health" in names
        assert "Shopping" in names

    def test_bounded_filter_only_relevant_categories(self):
        # May: only Bills and Health
        cats = get_category_breakdown(1, start_date="2026-05-01", end_date="2026-05-31")
        names = [c["name"] for c in cats]
        assert "Bills" in names, "Bills must appear in May breakdown"
        assert "Health" in names, "Health must appear in May breakdown"
        assert "Transport" not in names, "Transport must not appear in May breakdown"
        assert "Shopping" not in names, "Shopping must not appear in May breakdown"

    def test_percentages_sum_to_100(self):
        cats = get_category_breakdown(1, start_date="2026-05-01", end_date="2026-05-31")
        assert sum(c["percentage"] for c in cats) == 100, \
            "Category percentages must sum to exactly 100"

    def test_empty_range_returns_empty_list(self):
        cats = get_category_breakdown(1, start_date="2020-01-01", end_date="2020-12-31")
        assert cats == [], "Empty range must return empty category list"

    def test_ordered_by_amount_descending(self):
        # May: Bills (120.00) > Health (35.75)
        cats = get_category_breakdown(1, start_date="2026-05-01", end_date="2026-05-31")
        assert cats[0]["name"] == "Bills", \
            "Category with highest amount must be first"

    def test_start_only_excludes_april_categories(self):
        # start=2026-05-01 => Transport (Apr only) should not appear
        cats = get_category_breakdown(1, start_date="2026-05-01")
        names = [c["name"] for c in cats]
        assert "Transport" not in names, \
            "Transport (April only) must not appear in May+ breakdown"

    def test_amounts_formatted_to_two_decimal_places(self):
        cats = get_category_breakdown(1, start_date="2026-05-01", end_date="2026-05-31")
        for c in cats:
            assert "." in c["amount"], "Amount must be formatted with decimal point"
            assert len(c["amount"].split(".")[1]) == 2, \
                "Amount must have exactly 2 decimal places"

    def test_none_params_return_all_categories(self):
        cats = get_category_breakdown(1, start_date=None, end_date=None)
        assert len(cats) == 5, "All 5 distinct categories must appear with no filter"

    def test_user_with_no_expenses_returns_empty(self):
        cats = get_category_breakdown(2)
        assert cats == [], "User with no expenses must get empty category list"
