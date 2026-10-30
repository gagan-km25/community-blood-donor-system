# Architecture — Django + SQLite build

- Status: Implemented (v1.0)
- Date: 2026-10-29

## 1. High-level structure (Django MTV)

```text
Browser (HTML5 + CSS3 + vanilla JS, server-rendered Django templates)
   │  HTTP form posts / GETs, session cookie, CSRF token
   ▼
Django (config project)
   ├── accounts        registration, login, logout, post-login routing
   ├── donors          DonorProfile, search, matching helpers, donor dashboard
   ├── blood_requests  BloodRequest, RequestStatusHistory, AbuseReport,
   │                   state machine services, request views
   └── dashboard       home, about, admin dashboard, abuse-review
   ▼
SQLite (db.sqlite3 — project-local file, zero installation)
```

All authorization and validation runs server-side in Django views/forms; the
browser only ever receives rendered HTML. Queries go through the Django ORM
(parameterized — no raw SQL anywhere).

## 2. Project layout

```text
Community-Blood-Donor-System/
├── manage.py
├── requirements.txt            Django + python-dotenv only
├── db.sqlite3                  created by migrate (git-ignored)
├── .env.example                placeholder env vars
├── config/
│   ├── settings.py             env-driven SECRET_KEY/DEBUG, session + static config
│   ├── urls.py                 URL router + custom 403/404/500 handlers
│   └── views.py                error page views
├── accounts/                   auth views/forms/urls/tests
├── donors/                     profile model, search, matching.py, seed_demo_data command
├── blood_requests/             request models, services.py (state machine + expiry)
├── dashboard/                  home, about, admin dashboard, abuse review
├── templates/                  namespaced: accounts/, donors/, requests/, dashboard/, errors/
├── static/css/styles.css       red/white medical theme, responsive
├── static/js/main.js           nav toggle, confirm dialogs, message auto-dismiss
└── docs/                       this documentation set
```

## 3. Data model

```text
auth.User (Django built-in — chosen deliberately, see DECISIONS.md)
   │ 1:1                      1:N                        1:N
   ▼                          ▼                          ▼
donors.DonorProfile      blood_requests.BloodRequest   (requester FK)
  user                     requester                    units_needed 1..10
  full_name                patient_name (optional)      units_fulfilled 0..units
  blood_group (8 choices)  blood_group (8 choices)      status: open → matched →
  city                     hospital_name / city           partially_fulfilled →
  phone (regex-validated)  urgency: normal/urgent/critical  fulfilled; cancelled;
  is_available             needed_by (future on create)   expired (auto on overdue)
  last_donation_date?      contact_number               abuse_reports: AbuseReport
  contact_consent          notes?                         (request, reported_by,
  is_active (soft delete)  created_at / updated_at         reason, pending/reviewed/
                           RequestStatusHistory (from, to, changed_by, note, at)
```

Key constraints: unique donor profile per user; `units_needed` 1–10;
`units_fulfilled ≤ units_needed` (model `clean` + form); phone regex on both
profile and request; one abuse report per (request, reporter).

## 4. Request state machine (`blood_requests/services.py`)

```python
ALLOWED_TRANSITIONS = {
    OPEN:                {MATCHED, PARTIALLY_FULFILLED, FULFILLED, CANCELLED},
    MATCHED:             {PARTIALLY_FULFILLED, FULFILLED, CANCELLED},
    PARTIALLY_FULFILLED: {FULFILLED, CANCELLED},
    FULFILLED: set(), CANCELLED: set(), EXPIRED: set(),
}
```

`transition()` is the single entry point: it validates the move, enforces the
unit-fulfilment rules, saves, and appends a history row. `expire_due_requests()`
expires overdue open requests using the same path (actor = None → "System").
Views and the `expire_requests` management command both call it.

## 5. Matching (`donors/matching.py`)

- `COMPATIBLE_DONORS[recipient_group] → [donor groups]` (table in REQUIREMENTS.md FR-5.1), unit-tested for all eight groups plus the inverse lookup used by the donor dashboard.
- `find_potential_donors(request)` = active + available + compatible group + city match (`icontains`), newest first, capped at 20. Output is lead data only; it never mutates request status.

## 6. Security design

| Concern | Mechanism |
|---|---|
| Passwords | Django PBKDF2 hashing + built-in password validators |
| Sessions | `django.contrib.sessions`, HttpOnly cookie, SameSite Lax; logout is POST-only |
| CSRF | `{% csrf_token %}` on every POST form (Django middleware enforces) |
| Authorization | `@login_required` on private pages; `@staff_member_required` on admin pages; object ownership checked in view (`403` via `PermissionDenied` on mismatch) |
| Input validation | Django forms (server-side) + model validators (phone regex, unit bounds, future needed-by) |
| SQL injection | Django ORM parameterized queries only |
| Secrets | `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` from environment via python-dotenv; `.env` git-ignored, `.env.example` has placeholders |
| Error exposure | Custom 403/404/500 pages; safe form errors; DEBUG only from env |
| Privacy | Phone numbers gated on donor consent + authenticated viewer; board hides contacts/patient names; deactivated profiles excluded everywhere |

## 7. Request lifecycle flows

- **Create:** authenticated user → validated form → status `open` → redirect to detail.
- **Progress:** owner/staff presses action buttons on the detail page → `transition()` → history row → message feedback.
- **Cancel:** owner/staff, confirm dialog, any non-terminal status → `cancelled`.
- **Expire:** list/dashboard views call `expire_due_requests()`; terminal states untouched.
- **Fulfil:** `fulfilled` sets `units_fulfilled = units_needed`; never triggered by viewing matches.

## 8. Frontend

Server-rendered Django templates sharing `base.html` (navbar, messages, footer
with emergency guidance). One stylesheet uses CSS custom properties for the
red/white medical theme; `main.js` adds progressive enhancements (mobile nav,
`data-confirm` dialogs). Status/urgency badges are colour-coded consistently.
Error pages live in `templates/errors/` and are wired through `handler403/404/500`.
