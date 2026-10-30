# Implementation plan — Django + SQLite build

- Status: Executed (phases verified 2026-10-29)
- Date: 2026-10-29

Stack decision context: see `DECISIONS.md`. Each phase below lists what was built
and how it was verified. No phase was marked done without running its command.

## Phase 1–2 — Environment inspection + documentation
- Inspected: Python 3.12.1, pip 23.2.1, Node v24.21.0, npm 12.1.0, Git 2.55.0; **Go and PostgreSQL not installed**; read existing base-project docs before writing anything.
- Produced: `REQUIREMENTS.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `ACCEPTANCE_CRITERIA.md`, `DECISIONS.md`.

## Phase 3 — Django project setup
- Created `.venv`, installed Django 5.2.x + python-dotenv.
- `django-admin startproject config .`; `startapp` for accounts, donors, blood_requests, dashboard.
- **Verify:** `manage.py check` → *no issues*.

## Phase 4 — Models, migrations, authentication, roles
- Models: `DonorProfile`, `BloodRequest`, `RequestStatusHistory`, `AbuseReport`; state machine in `services.py`; compatibility map in `matching.py`.
- Auth: register / login / logout (POST-only) with messages and role-aware redirects.
- **Verify:** `makemigrations` + `migrate` applied cleanly; `check` passes.

## Phase 5 — Donor profiles, search, privacy
- Profile create/edit/deactivate; public search with blood-group/city/availability filters + pagination; phone hidden without consent+auth.
- **Verify:** donor app tests (filters, privacy, deactivation, validation).

## Phase 6 — Blood requests, status tracking, cancellation
- Create/edit/cancel with ownership 403s; status actions through `transition()`; history timeline; auto-expiry; potential-donor leads on detail.
- **Verify:** request app tests (transitions incl. illegal ones, units rules, expiry, permissions, history).

## Phase 7 — Dashboards, admin, responsive UI
- Donor / requester / admin dashboards (live DB stats); community board; abuse reporting + review; custom error pages; red/white responsive theme.
- **Verify:** dashboard tests (staff gating, stats) + manual page loads via runserver smoke test.

## Phase 8 — Automated tests and defect fixing
- Full suite in each app covering the Section-14 checklist of the project brief.
- **Verify:** `manage.py test` green; every failure fixed before completion claim.

## Phase 9 — README and delivery
- Beginner-friendly README with exact PowerShell commands, demo data seeding, superuser steps, troubleshooting.
- **Verify:** clean-setup walkthrough (fresh venv path documented), runserver smoke test of public pages.

## Verification log (actual commands, final run 2026-10-29)
```text
manage.py check                    → System check identified no issues (0 silenced)
manage.py makemigrations           → donors/0001_initial, blood_requests/0001_initial
manage.py migrate                  → Applying ... OK (all 19 migrations, no pending)
manage.py seed_demo_data           → Created 12 donor profiles, 4 demo blood requests
manage.py test                     → OK — 84 tests (after fixing 3 real defects, see below)
runserver + curl smoke test        → 200 on /, /about/, /donors/search/ (filtered too),
                                     /accounts/login/, /accounts/register/
                                   → 302 on /requests/board/ and /admin-dashboard/
                                     (protected — redirect to login / admin login)
                                   → 404 on a nonexistent page
                                   → guest search shows donor names but NO phone
                                     numbers ("log in to view" instead); home stats
                                     render live (12 donors / 2 open / 0 fulfilled)
```

Defects caught by the test suite and fixed before completion:
1. `StatusUpdateForm.to_status` had no choices → every manual status change was
   silently rejected by form validation.
2. Automatic expiry used the manual transition map → overdue requests could
   never expire; `transition()` now accepts `automatic=True` reserved for the
   system path.
3. `recipient_groups_for_donor` returned groups in dict order → inverse lookup
   now returns canonical `BloodGroup.values` order.
