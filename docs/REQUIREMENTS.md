# Requirements — Community Blood Donor and Emergency Request System

- Status: Implemented scope for v1.0 (Django + SQLite build)
- Date: 2026-10-29
- Supersedes: the React/Go draft in `../community-blood-donor-system-base/docs/` for this codebase (see `DECISIONS.md`)

## 1. Objective

Provide a secure, responsive web platform where community members can register as
blood donors, search for potential donors, submit emergency blood requests, and
track request progress. Built as a college mini project: simple enough to explain
in a viva, complete enough to demonstrate every core workflow live.

**Safety statement:** this system identifies *potential donor leads only*. It does
not confirm medical eligibility, clinical compatibility, or real-time blood
availability. Clinical decisions belong to qualified healthcare professionals. In a
real emergency, contact local emergency services or go to a hospital. This notice
appears in the app footer and on every matching/search screen.

## 2. User roles

| Role | Who | Can do |
|---|---|---|
| Guest | Not logged in | Home, About, Register, Login, donor search (no phone numbers) |
| Registered user | Any authenticated account | Everything a guest can, plus: donor profile, create/manage own requests, community request board, file abuse reports |
| Donor | Registered user with a donor profile | Donor dashboard, profile edit, availability toggle, contact-consent control, see compatible open requests |
| Requester | Any registered user (donors included) | Requester dashboard, create/edit/cancel own requests, track status history, view authorized potential matches |
| Administrator | `is_staff` user (created only via `createsuperuser`) | Admin dashboard with real database statistics, abuse-report review, full management through Django admin |

One account can be both donor and requester; roles follow from what the account
*has* (a donor profile) and what it *does*, not from separate accounts. Public
registration can never grant administrator privileges.

## 3. Functional requirements

### FR-1 Accounts and authentication
- FR-1.1 Register with username, email, password + confirmation; Django password validators enforced.
- FR-1.2 Login with Django session authentication; logout via CSRF-protected POST only.
- FR-1.3 Passwords stored only as Django hashes (PBKDF2); never in plaintext.
- FR-1.4 Protected pages redirect anonymous users to login; after login the user lands on a role-appropriate dashboard.
- FR-1.5 Success/error feedback via Django messages on every action.

### FR-2 Donor profiles
- FR-2.1 Fields: full name, blood group (A+, A-, B+, B-, AB+, AB-, O+, O-), city, phone, availability flag, optional last-donation date, contact-sharing consent.
- FR-2.2 Server-side validation: blood group from fixed choices, phone format `^\+?[0-9][0-9\s\-()]{6,17}$`, last-donation date not in the future, required fields non-empty.
- FR-2.3 Create once, then edit; deactivate/reactivate profile (deactivated profiles never appear in search or matching).
- FR-2.4 Phone numbers are private: shown only when the donor has given contact consent **and** the viewer is authenticated. Guests never see phone numbers.

### FR-3 Donor search
- FR-3.1 Public search filtered by blood group, city (case-insensitive contains), and availability.
- FR-3.2 Only active donor profiles are returned.
- FR-3.3 Results paginated (8 per page) with an explicit empty state when nothing matches.
- FR-3.4 Every result is labelled a *potential lead*, not a guarantee.

### FR-4 Emergency blood requests
- FR-4.1 Fields: requester, optional patient/beneficiary name, required blood group, units needed (1–10), hospital name, hospital city, urgency (Normal/Urgent/Critical), required date-time (must be future at creation), contact number, optional notes.
- FR-4.2 Statuses: `open`, `matched`, `partially_fulfilled`, `fulfilled`, `cancelled`, `expired`.
- FR-4.3 State machine (illegal transitions rejected server-side):

```text
open ──► matched ──► partially_fulfilled ──► fulfilled
  │          │              │
  └──────────┴──────────────┴──► cancelled        (terminal: fulfilled, cancelled, expired)
```
  `open/matched/partially_fulfilled` may each go straight to `fulfilled` or `cancelled`.
  Terminal states can never be reopened through normal use.
- FR-4.4 Every status change writes a `RequestStatusHistory` row (actor, from, to, note, timestamp).
- FR-4.5 `partially_fulfilled` requires `0 < units_fulfilled < units_needed`; `fulfilled` sets `units_fulfilled = units_needed`.
- FR-4.6 Overdue non-terminal requests are auto-expired (checked when request lists/dashboards load, and via the `expire_requests` management command).
- FR-4.7 Only the owner (or an administrator) can view, edit, cancel, or change the status of a request. Anyone else gets **403 Forbidden**, even with the correct ID.
- FR-4.8 Displaying a potential donor match **never** changes a request's status.

### FR-5 Matching (lead discovery)
- FR-5.1 Preliminary ABO/Rh compatibility map, documented and unit-tested:

| Recipient | Compatible donor groups |
|---|---|
| O- | O- |
| O+ | O+, O- |
| A- | A-, O- |
| A+ | A+, A-, O+, O- |
| B- | B-, O- |
| B+ | B+, B-, O+, O- |
| AB- | AB-, A-, B-, O- |
| AB+ | all eight |

- FR-5.2 Request detail shows potential donors: compatible group, available, active profile, hospital-city match — capped at 20, labelled as leads.
- FR-5.3 Donor dashboard shows up to 5 compatible open community requests as opportunities.
- FR-5.4 Contact details follow FR-2.4 privacy rules everywhere.

### FR-6 Community request board
- FR-6.1 Authenticated users can browse open/matched/partially-fulfilled requests (urgency first, then needed-by).
- FR-6.2 The board hides contact numbers and patient names; it exists so donors can find requests and users can report abuse.

### FR-7 Abuse reports
- FR-7.1 Any authenticated user may report a community-board request once per request, with a required reason.
- FR-7.2 Administrators review reports from the admin dashboard: mark *reviewed* or *dismissed* (records reviewer and review time).

### FR-8 Dashboards
- FR-8.1 Donor dashboard: profile summary, availability, consent status, compatible opportunities.
- FR-8.2 Requester dashboard: personal statistics from real database counts, own request table with status badges, links to create/view.
- FR-8.3 Administrator dashboard (staff only): total registered users, active donors, open requests, fulfilled requests, pending abuse reports, recent status-history audit trail — all computed live from the database.

### FR-9 Audit history
- FR-9.1 Status history per request (FR-4.4) visible to owner/admin on the request detail page.
- FR-9.2 Recent status history shown on the admin dashboard.
- FR-9.3 Django's built-in admin LogEntry records administrative edits (Django admin default).

## 4. Non-functional requirements
- Responsive desktop/mobile layout (CSS media queries, no frontend framework).
- Accessible forms: labels for every input, keyboard-operable navigation, visible focus states.
- Local CSS/JS only; no CDNs, paid services, or third-party frontend libraries.
- Versioned migrations; schema changes only through Django migrations.
- Automated tests for auth, permissions, validation, transitions, matching, and privacy.
- Safe error messages; DEBUG-controlled detail; no secrets in code or logs.

## 5. Out of scope (v1)
Medical eligibility decisions, blood-bank inventory, hospital integrations, SMS/
email/WhatsApp notifications, geolocation/maps, payments, real deployments with
real personal data, API/OpenAPI surface (Django template app, not a REST API).
