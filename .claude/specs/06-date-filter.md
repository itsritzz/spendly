# Spec: Date Filter for Profile Page

## Overview
Add a date-range filter to the profile page so users can view their
expense summary, transaction history, and category breakdown for a
specific time period. The filter appears as a compact form above the
stats cards. When no filter is applied the page behaves exactly as it
does today (all-time data). This is the natural next step after the
backend profile data is wired up, giving users control over the
window of data they see.

## Depends on
- Step 05 — Backend Route Profile Page (provides the query functions
  and the `/profile` route that this feature extends).

## Routes
- `GET /profile` (modify) — accept optional `start` and `end` query
  parameters (format `YYYY-MM-DD`). Pass them through to the query
  helpers so every stat, transaction, and category row respects the
  chosen date range. Invalid or missing dates are silently ignored
  (fall back to all-time). Access level: logged-in.

No new routes.

## Database changes
No database changes.

## Templates
- **Modify:** `templates/profile.html` — add a date-range filter form
  (two date inputs + a submit button + a "Clear" link) between the
  user-info card and the summary stats row. The form submits via GET.
  Pre-fill inputs with the currently active filter values so the
  selection is sticky across page loads.

## Files to change
| File | What changes |
|---|---|
| `app.py` | Read `start` / `end` query params in the `/profile` route and forward them to every query helper. Pass `start`, `end` back to the template for sticky inputs. |
| `database/queries.py` | Add optional `start_date` and `end_date` parameters to `get_summary_stats`, `get_recent_transactions`, and `get_category_breakdown`. Append `AND date >= ?` / `AND date <= ?` clauses when provided. |
| `templates/profile.html` | Add the date-filter form. |
| `static/style.css` | Add styles for the filter form row (`.profile-filter-form`). |

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only.
- Parameterised queries only — never interpolate user input into SQL.
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html`.
- Date inputs must use `type="date"` for native browser pickers.
- Validate that `start <= end` when both are supplied; if not, ignore
  both and show all-time data.
- The "Clear" link reloads `/profile` with no query string.
- Keep the existing default behaviour: when no dates are supplied,
  show all-time data (no `WHERE date` clause added).
- Do not change function signatures in a breaking way — the new
  `start_date` / `end_date` parameters must default to `None`.

## Definition of done
- [ ] Profile page loads without errors when no date params are set
      (existing behaviour unchanged).
- [ ] Selecting a start and end date and clicking "Filter" reloads the
      page with only matching transactions visible in the table.
- [ ] Summary stats (total spent, transaction count, top category)
      update to reflect the filtered date range.
- [ ] Category breakdown percentages and amounts update to reflect
      the filtered date range.
- [ ] The date inputs are pre-filled with the active filter values
      after form submission.
- [ ] Clicking "Clear" removes the filter and shows all-time data.
- [ ] Supplying `start` without `end` (or vice-versa) still filters
      correctly using the single bound.
- [ ] Supplying `start` > `end` falls back to all-time data.
- [ ] The filter form is responsive and looks good on mobile.