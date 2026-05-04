# Spec: Login and Logout

## Overview
This step upgrades the existing stub `GET /login` and `GET /logout` routes into fully functional handlers. Login accepts a POST, looks up the user by email, verifies the password hash, and starts a Flask session. On success, the user is redirected to the landing page (until a dashboard exists). Logout clears the session and redirects to the landing page. Together with registration (Step 02), this completes the authentication flow that all protected features depend on.

## Depends on
- Step 01: Database Setup — `users` table and `get_db()` must exist.
- Step 02: Registration — so users can create accounts to log into. Also provides `secret_key`, flash messages, conditional navbar, and `.auth-success` CSS.

## Routes
- `GET  /login` — render login form (already exists, needs `methods` update) — public
- `POST /login` — validate credentials, start session, redirect — public
- `GET  /logout` — clear session, redirect to landing — logged-in

## Database changes
No schema changes. Reads from the existing `users` table using a `SELECT` by email.

## Templates
- **Modify:** `templates/login.html` — add `value="{{ email or '' }}"` to the email input so it persists on failed login attempts

## Files to change
| File | What changes |
|------|-------------|
| `app.py` | Import `check_password_hash` from werkzeug; convert `/login` route to accept GET + POST with credential validation; replace `/logout` stub with session clear + redirect |
| `templates/login.html` | Add `value` attribute to email input for re-population on error |

## Files to create
None.

## New dependencies
No new dependencies. Uses:
- `werkzeug.security.check_password_hash` (already installed)
- `flask.session` (already imported in Step 02)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords verified with `werkzeug.security.check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Store only `user_id` and `user_name` in the Flask session — never the password or hash
- On failed login: re-render form with a generic `error="Invalid email or password."` — do not reveal whether the email exists
- Server-side validation (re-render form with `error` on failure):
  - Email must not be blank
  - Password must not be blank
- After successful login: set `session['user_id']` and `session['user_name']`, then redirect to `/`
- Logout must call `session.clear()` and redirect to `/`
- Always close the database connection (use `try/finally`)

## Definition of done
- [ ] `GET /login` renders `login.html` with no errors
- [ ] Submitting valid credentials (e.g. `demo@spendly.com` / `demo123`) sets `session['user_id']` and `session['user_name']` and redirects (302) to `/`
- [ ] After login, navbar shows "Sign out" instead of "Sign in" / "Get started"
- [ ] Submitting wrong password re-renders form with `"Invalid email or password."`
- [ ] Submitting non-existent email re-renders form with `"Invalid email or password."`
- [ ] Submitting empty email or password re-renders form with an appropriate error
- [ ] Email field retains its value on failed login
- [ ] Flash success message from registration still displays correctly on the login page
- [ ] `GET /logout` clears the session and redirects (302) to `/`
- [ ] After logout, navbar shows "Sign in" / "Get started" again
- [ ] App starts without errors after all changes
