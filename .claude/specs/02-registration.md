# Spec: Registration

## Overview
This step upgrades the existing stub `GET /register` route into a fully functional form that accepts a POST, validates input, and hashes the password before storing it. The `register.html` template and all CSS already exist — this step adds the server-side logic. On success, the user is shown a success message and redirected to the login page. This is the entry point for all authenticated features that follow.

## Depends on
- Step 01: Database Setup — `users` table, `get_db()`, and `init_db()` must be in place.

## Routes
- `GET  /register` — render registration form (already exists, needs `methods` update) — public
- `POST /register` — validate input, create user, set session, redirect — public

## Database changes
No schema changes. Uses the existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`).

## Templates
- **Modify:** `templates/register.html` — preserve form values on validation failure (populate `value="{{ name }}"`, `value="{{ email }}"` so the user doesn't re-type)
- **Modify:** `templates/base.html` — conditional navbar: show "Dashboard" + "Sign out" when `session.user_id` is set, otherwise show "Sign in" + "Get started"

## Files to change
| File | What changes |
|------|-------------|
| `app.py` | Add `secret_key`; import `request`, `redirect`, `url_for`, `session` from Flask; import `generate_password_hash` from werkzeug; convert `/register` route to accept GET + POST; add POST logic |
| `templates/register.html` | Add `value` attributes to name/email inputs for re-population on error |
| `templates/base.html` | Conditional nav links based on `session.get('user_id')` |

## Files to create
None.

## New dependencies
No new dependencies. Uses:
- `flask.session`, `flask.request`, `flask.redirect` (built-in)
- `werkzeug.security.generate_password_hash` (already installed)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Hash passwords with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Set `app.secret_key` to a hard-coded dev string (e.g. `"spendly-dev-secret"`)
- Store only `user_id` and `user_name` in the Flask session — never the password or hash
- Catch `sqlite3.IntegrityError` on insert to detect duplicate emails — re-render with `error="An account with that email already exists."`
- Server-side validation (re-render form with `error` on failure):
  - Name must not be blank
  - Email must contain `@` (basic check)
  - Password must be ≥ 8 characters
- After successful registration: flash a success message (e.g. `"Account created successfully! Please sign in."`) and redirect to `/login`
- Always close the database connection (use `try/finally`)

## Definition of done
- [ ] `GET /register` renders `register.html` with no errors
- [ ] Submitting valid data creates a `users` row with a hashed password (never plain text)
- [ ] After registration the browser receives a 302 redirect to `/`
- [ ] `session['user_id']` and `session['user_name']` are set after registration
- [ ] Navbar shows "Sign out" link when session is active
- [ ] Navbar shows "Sign in" / "Get started" when no session
- [ ] Duplicate email re-renders form with `"An account with that email already exists."`
- [ ] Password < 8 chars re-renders form with an error
- [ ] Empty name re-renders form with an error
- [ ] Form fields retain previously entered name/email on validation error
- [ ] App starts without errors after all changes
