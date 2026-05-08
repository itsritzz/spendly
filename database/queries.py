from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return user dict with name, email, member_since — or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
    }


def get_summary_stats(user_id):
    """Return dict with total_spent, transaction_count, top_category."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        total_spent = row["total"]
        transaction_count = row["cnt"]

        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": f"{total_spent:.2f}",
        "transaction_count": transaction_count,
        "top_category": top["category"] if top else "\u2014",
    }


def get_recent_transactions(user_id, limit=10):
    """Return list of transaction dicts ordered newest-first."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    transactions = []
    for r in rows:
        dt = datetime.strptime(r["date"], "%Y-%m-%d")
        transactions.append({
            "date": dt.strftime("%d %b %Y"),
            "description": r["description"],
            "category": r["category"],
            "amount": f"{r['amount']:.2f}",
        })
    return transactions


def get_category_breakdown(user_id):
    """Return list of category dicts with name, amount, percentage (summing to 100)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(r["total"] for r in rows)

    categories = []
    for r in rows:
        categories.append({
            "name": r["category"],
            "amount": f"{r['total']:.2f}",
            "percentage": round(r["total"] / grand_total * 100),
        })

    # Adjust largest category so percentages sum to exactly 100
    pct_sum = sum(c["percentage"] for c in categories)
    if pct_sum != 100:
        categories[0]["percentage"] += 100 - pct_sum

    return categories
