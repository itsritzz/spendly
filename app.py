import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name:
        error = "Name is required."
    elif "@" not in email:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm_password:
        error = "Passwords do not match."
    else:
        error = None

    if error:
        return render_template("register.html", error=error, name=name, email=email)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        )
    finally:
        conn.close()

    flash("Account created successfully! Please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email:
        return render_template("login.html", error="Email is required.", email=email)
    if not password:
        return render_template("login.html", error="Password is required.", email=email)

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.", email=email)

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded data — will be replaced with DB queries in Step 5
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "May 2026",
    }

    stats = {
        "total_spent": "351.03",
        "transaction_count": 8,
        "top_category": "Food",
    }

    transactions = [
        {"date": "20 May 2026", "description": "Grocery run", "category": "Food", "amount": "22.30"},
        {"date": "18 May 2026", "description": "Miscellaneous", "category": "Other", "amount": "7.00"},
        {"date": "15 May 2026", "description": "New shoes", "category": "Shopping", "amount": "89.49"},
        {"date": "12 May 2026", "description": "Streaming subscription", "category": "Entertainment", "amount": "18.99"},
        {"date": "08 May 2026", "description": "Pharmacy", "category": "Health", "amount": "35.75"},
        {"date": "05 May 2026", "description": "Electricity bill", "category": "Bills", "amount": "120.00"},
        {"date": "03 May 2026", "description": "Monthly bus pass top-up", "category": "Transport", "amount": "45.00"},
        {"date": "01 May 2026", "description": "Lunch at cafe", "category": "Food", "amount": "12.50"},
    ]

    categories = [
        {"name": "Bills", "amount": "120.00", "percentage": 34},
        {"name": "Shopping", "amount": "89.49", "percentage": 25},
        {"name": "Transport", "amount": "45.00", "percentage": 13},
        {"name": "Health", "amount": "35.75", "percentage": 10},
        {"name": "Food", "amount": "34.80", "percentage": 10},
        {"name": "Entertainment", "amount": "18.99", "percentage": 5},
        {"name": "Other", "amount": "7.00", "percentage": 2},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
