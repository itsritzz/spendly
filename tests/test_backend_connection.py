import os
import sqlite3
import tempfile
import unittest

# Point the DB to a temp file before importing app code
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("SPENDLY_DB", _tmp.name)

import database.db as db_mod

# Patch DB_PATH so all queries hit the temp database
db_mod.DB_PATH = _tmp.name

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)
from app import app


class _BaseTestCase(unittest.TestCase):
    """Set up a fresh database with seed data for each test."""

    def setUp(self):
        db_mod.DB_PATH = _tmp.name
        # Reset database
        conn = sqlite3.connect(_tmp.name)
        conn.execute("DROP TABLE IF EXISTS expenses")
        conn.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        conn.close()
        # Re-init schema
        db_mod.init_db()
        # Insert test user
        conn = db_mod.get_db()
        from werkzeug.security import generate_password_hash

        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (1, "Demo User", "demo@spendly.com",
             generate_password_hash("demo123"), "2026-01-15 10:30:00"),
        )
        # Insert test expenses
        expenses = [
            (1, 12.50, "Food", "2026-05-01", "Lunch at cafe"),
            (1, 45.00, "Transport", "2026-05-03", "Monthly bus pass top-up"),
            (1, 120.00, "Bills", "2026-05-05", "Electricity bill"),
            (1, 35.75, "Health", "2026-05-08", "Pharmacy"),
            (1, 18.99, "Entertainment", "2026-05-12", "Streaming subscription"),
            (1, 89.49, "Shopping", "2026-05-15", "New shoes"),
            (1, 7.00, "Other", "2026-05-18", "Miscellaneous"),
            (1, 22.30, "Food", "2026-05-20", "Grocery run"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        # Insert user with no expenses
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (2, "Empty User", "empty@spendly.com",
             generate_password_hash("empty123"), "2026-03-01 08:00:00"),
        )
        conn.commit()
        conn.close()


# ------------------------------------------------------------------ #
# Unit tests for query helpers                                        #
# ------------------------------------------------------------------ #

class TestGetUserById(_BaseTestCase):
    def test_valid_user(self):
        user = get_user_by_id(1)
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "Demo User")
        self.assertEqual(user["email"], "demo@spendly.com")
        self.assertEqual(user["member_since"], "January 2026")

    def test_nonexistent_user(self):
        self.assertIsNone(get_user_by_id(999))


class TestGetSummaryStats(_BaseTestCase):
    def test_user_with_expenses(self):
        stats = get_summary_stats(1)
        self.assertEqual(stats["total_spent"], "351.03")
        self.assertEqual(stats["transaction_count"], 8)
        self.assertEqual(stats["top_category"], "Bills")

    def test_user_with_no_expenses(self):
        stats = get_summary_stats(2)
        self.assertEqual(stats["total_spent"], "0.00")
        self.assertEqual(stats["transaction_count"], 0)
        self.assertEqual(stats["top_category"], "\u2014")


class TestGetRecentTransactions(_BaseTestCase):
    def test_user_with_expenses(self):
        txs = get_recent_transactions(1)
        self.assertEqual(len(txs), 8)
        # Newest first
        self.assertEqual(txs[0]["date"], "20 May 2026")
        self.assertEqual(txs[-1]["date"], "01 May 2026")
        # Check keys
        for tx in txs:
            self.assertIn("date", tx)
            self.assertIn("description", tx)
            self.assertIn("category", tx)
            self.assertIn("amount", tx)

    def test_user_with_no_expenses(self):
        self.assertEqual(get_recent_transactions(2), [])

    def test_limit(self):
        txs = get_recent_transactions(1, limit=3)
        self.assertEqual(len(txs), 3)


class TestGetCategoryBreakdown(_BaseTestCase):
    def test_user_with_expenses(self):
        cats = get_category_breakdown(1)
        self.assertEqual(len(cats), 7)
        # Ordered by amount desc — Bills is largest
        self.assertEqual(cats[0]["name"], "Bills")
        # Percentages sum to 100
        self.assertEqual(sum(c["percentage"] for c in cats), 100)

    def test_user_with_no_expenses(self):
        self.assertEqual(get_category_breakdown(2), [])


# ------------------------------------------------------------------ #
# Route tests                                                         #
# ------------------------------------------------------------------ #

class TestProfileRoute(_BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = app.test_client()
        app.config["TESTING"] = True

    def test_unauthenticated_redirects(self):
        resp = self.client.get("/profile")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_authenticated_returns_200(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"
        resp = self.client.get("/profile")
        self.assertEqual(resp.status_code, 200)

    def test_authenticated_shows_real_data(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"
        resp = self.client.get("/profile")
        html = resp.data.decode()
        self.assertIn("Demo User", html)
        self.assertIn("demo@spendly.com", html)
        self.assertIn("₹", html)
        self.assertIn("351.03", html)
        self.assertIn("Bills", html)

    def test_empty_user_profile(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["user_name"] = "Empty User"
        resp = self.client.get("/profile")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("0.00", html)
        self.assertIn("Empty User", html)


if __name__ == "__main__":
    unittest.main()
