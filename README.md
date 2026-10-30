# Community Blood Donor and Emergency Request System (BloodConnect)

A complete, working Django web application where community members register as
blood donors, search for potential donors, submit emergency blood requests, and
track each request from **Open** to **Fulfilled** (or Cancelled/Expired).

> ⚠ **Safety:** the app shows *potential donor leads only*. It does not confirm
> medical eligibility, clinical compatibility, or blood availability. In a real
> emergency, call local emergency services or go to the nearest hospital.

## Prerequisites (Windows)

- **Python 3.12** (or 3.10+) — check with `python --version`
- No database installation needed — the project uses SQLite (a single local file)
- No internet needed after dependencies are installed

## Quick start (exact PowerShell commands)

From the project folder `Community-Blood-Donor-System`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** in your browser.

If PowerShell blocks activation with a script-execution error, run once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Optional (recommended) setup steps

```powershell
# Synthetic demo data: 12 donors, 2 requesters, 4 blood requests.
# Demo password for these accounts: Demo@12345
python manage.py seed_demo_data

# Administrator account (the ONLY way to get admin rights —
# public registration never grants admin):
python manage.py createsuperuser
```

Log in as administrator at **http://127.0.0.1:8000/admin/** (Django admin) and
see the statistics dashboard at **http://127.0.0.1:8000/admin-dashboard/**.

## Environment configuration (optional)

Copy `.env.example` to `.env` to set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and
`DJANGO_ALLOWED_HOSTS`. For local development the defaults work fine without a
`.env` file.

## Running the automated tests

```powershell
python manage.py test
```

Expected result: **OK, 84 tests** (they use a separate test database; your
`db.sqlite3` is untouched).

## Demo walkthrough (viva script)

1. **Guest:** open the home page, About, and Donor Search — phone numbers are
   hidden for guests.
2. **Register:** create an account → you land on the requester dashboard.
3. **Become a donor:** "Become a Donor" in the navbar → create a profile →
   redirected to the donor dashboard (availability, consent, opportunities).
4. **Donor search:** filter by blood group + city → consenting donors show their
   phone number once you are logged in.
5. **Create a request:** pick blood group, units, hospital, urgency, future
   date → status **Open**.
6. **Track it:** on the request detail page, see *potential donor leads*
   (compatibility + city matched), progress buttons, and the status-history
   timeline. Move Open → Matched → Partially Fulfilled (units) → Fulfilled, or
   Cancel. Illegal moves (e.g. re-opening a fulfilled request) are rejected.
7. **Board & abuse report:** "Request Board" shows open requests from others;
   you can report a suspicious one.
8. **Admin:** log in as the superuser → admin dashboard (live statistics,
   pending reports to review/mark) and full management in Django admin.

## Project structure

```text
Community-Blood-Donor-System/
├── manage.py                  # Django command-line helper
├── requirements.txt           # Django + python-dotenv (nothing else)
├── db.sqlite3                 # local database (created by migrate)
├── .env.example               # template for optional environment variables
├── config/                    # project settings, root urls, error pages
├── accounts/                  # register / login / logout
├── donors/                    # donor profiles, search, matching, seed command
├── blood_requests/            # requests, status machine, history, abuse reports
├── dashboard/                 # home, about, admin dashboard
├── templates/                 # server-rendered pages (Django templates)
├── static/css|js|images/      # local styles, script, favicon
└── docs/                      # requirements, architecture, plan, criteria
```

## Features

- Registration, login, POST-only logout, session auth (Django-hashed passwords)
- Donor profiles: blood group, city, phone, availability, last donation,
  contact-consent, deactivate/reactivate
- Public donor search with blood-group / city / availability filters and
  pagination; deactivated profiles never appear
- **Privacy:** phone numbers visible only when the donor consented AND the
  viewer is logged in
- Emergency requests with validated inputs (units 1–10, future date, phone)
- Status lifecycle `Open → Matched → Partially Fulfilled → Fulfilled`, plus
  `Cancelled` and automatic `Expired`, with full status-history audit trail
- Preliminary ABO/Rh compatibility matching, clearly labelled as leads
- Community request board (contact details stay private) + abuse reporting
- Role-aware dashboards: donor / requester / administrator (staff-only)
- Admin dashboard with live database statistics and abuse-review actions
- Custom 403/404/500 pages, responsive red/white medical UI, accessible forms

## Known limitations (intentional, college-mini-project scope)

- No email/SMS notifications; no geolocation or maps
- No idempotency keys — duplicate request submissions are possible; cancel the
  extra one (see `docs/DECISIONS.md` D-07)
- SQLite is single-user; a production deployment would swap to PostgreSQL
- Matching ignores donation intervals/eligibility rules — professionals decide
- Custom error pages show when `DJANGO_DEBUG=False` (default error pages show
  technical detail while debugging locally)

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Install Python 3.12 from python.org and re-open the terminal |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Port 8000 already in use | `python manage.py runserver 8001` |
| Login page loops after login | Clear cookies for 127.0.0.1 or use another browser profile |
| Want a fresh database | Delete `db.sqlite3` (demo data only) and run `python manage.py migrate` again |
