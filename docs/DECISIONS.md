# Decisions log

- Date: 2026-10-29

## D-01 — Stack switched from React+Go+PostgreSQL to Django+SQLite
The user supplied two conflicting briefs (React/Go/PostgreSQL vs Django/SQLite)
plus an existing base project documented for the React/Go stack. Inspection
showed **Go and PostgreSQL are not installed** on this machine, while Python
3.12.1 is. The user explicitly chose the Django + SQLite MASTER PROMPT option.
The React/Go draft docs in the sibling `community-blood-donor-system-base`
folder were left untouched; their domain content (state machine, compatibility
rules, privacy rules, acceptance-criteria style) was carried over.

## D-02 — Django's built-in `auth.User` instead of a custom user model
A custom user model is only worth its migration pain when you must store extra
identity fields. Here the only extra identity data (blood group, city, phone…)
belongs to the *donor profile*, not the account — a `OneToOneField` profile is
the classic, viva-explainable pattern. Custom models also cannot be changed
after first migrate without resetting the DB; built-in `User` keeps the project
simple and safe to demonstrate.

## D-03 — Session-cookie authentication, POST-only logout
Django's session auth is the framework default, secure (HttpOnly cookies,
rotating session keys), and easy to explain. Logout accepts POST only so a
prefetched/cross-site GET cannot log the user out. Login redirects staff →
admin dashboard, profile holders → donor dashboard, others → requester dashboard.

## D-04 — SQLite for the mini project
Zero installation, single file, git-ignored. The brief forbids installing
PostgreSQL and the whole ORM/data layer is portable to PostgreSQL later by
changing one setting.

## D-05 — Administrator via `is_staff` + Django admin
Public registration can never produce staff. Admins are created only with
`createsuperuser`. A custom admin dashboard shows live statistics and abuse
review; heavy management (user editing, request correction) delegates to Django
admin, which also gives free audit logs of admin edits.

## D-06 — Added a "community request board" (small scope extension)
Abuse reporting and donor opportunities both need a place where logged-in users
can see *open* requests that are not theirs, while contact numbers and patient
names stay private (owner + staff only, enforced with 403s). The board is that
place; it is listed in REQUIREMENTS.md FR-6.

## D-07 — Duplicate request submissions
Full idempotency keys were judged over-engineered for a mini project. Mitigation
instead: all timestamps use `auto_now_add`, the create form warns against
re-submitting, and repeated identical submissions simply create distinct requests
that the owner can cancel — documented as a known limitation.

## D-08 — Expiry is lazy + command-triggered, not cron
Windows demo machines have no cron. `expire_due_requests()` runs whenever request
lists/dashboards load and on demand via `python manage.py expire_requests`, so
demo data always looks consistent without background jobs.

## D-09 — python-dotenv for configuration
Two tiny dependencies total (Django, python-dotenv) so `.env` files actually
load on Windows without teaching PowerShell env-var syntax; `.env.example`
documents `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` with
placeholders only.
