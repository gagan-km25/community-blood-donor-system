# Acceptance criteria — Django + SQLite build

- Date: 2026-10-29
- Every criterion maps to an automated test (named exactly as in the codebase)
  or an executed command. Statuses were set only after the referenced evidence
  actually ran. Full suite result: **`manage.py test` → OK — 84 tests**.

## Authentication and roles
| ID | Criterion | Status / evidence |
|---|---|---|
| AC-001 | Valid registration creates an account and logs the user in | Pass — `accounts.RegistrationTests.test_registration_success_creates_and_logs_in` |
| AC-002 | Duplicate username / mismatched passwords rejected with safe errors | Pass — `test_registration_duplicate_username_rejected`, `test_registration_password_mismatch_rejected` |
| AC-003 | Passwords stored only as hashes | Pass — Django PBKDF2 (framework guarantee); no plaintext password field exists |
| AC-004 | Valid login and logout work | Pass — `LoginLogoutTests.test_login_success`, `test_logout_post_only` |
| AC-005 | Protected pages reject anonymous users (redirect to login) | Pass — `ProtectedPageTests.test_protected_pages_redirect_anonymous` (all six pages) |
| AC-006 | Users cannot read/modify another user's private records via IDs | Pass — `RequestPermissionTests.test_stranger_gets_403`, `test_stranger_cannot_edit/cannot_cancel/cannot_change_status` |
| AC-007 | Admin-only pages reject non-admin users | Pass — `AdminDashboardTests.test_non_staff_rejected` / `test_anonymous_redirected_to_admin_login` (rejected via redirect to the admin login page) |

## Donor profiles and discovery
| ID | Criterion | Status / evidence |
|---|---|---|
| AC-008 | Authenticated user can create and update own donor profile | Pass — `DonorProfileTests.test_profile_create_and_edit` |
| AC-009 | Invalid phone / future last-donation date rejected server-side | Pass — `test_profile_phone_validation`, `test_profile_future_donation_date_rejected` |
| AC-010 | Availability and consent can be updated | Pass — `test_profile_create_and_edit` (consent toggled off during edit) |
| AC-011 | Search filters by blood group, city, availability | Pass — `DonorSearchTests.test_search_filter_blood_group/city/availability` |
| AC-012 | Public search hides phone numbers; consent + login required to reveal | Pass — `test_guest_never_sees_phone`, `test_authenticated_sees_phone_only_with_consent` |
| AC-013 | Deactivated profiles never appear in search or matches | Pass — `test_deactivated_profile_hidden_from_search`, `CompatibilityMapTests.test_find_potential_donors_filters_correctly` |

## Blood requests
| ID | Criterion | Status / evidence |
|---|---|---|
| AC-014 | Authenticated user can create a valid request | Pass — `RequestCreateTests.test_create_request_success` |
| AC-015 | Invalid units, past date, missing fields rejected | Pass — `test_units_bounds_rejected`, `test_past_needed_by_rejected`, `test_missing_hospital_rejected`, `test_invalid_phone_rejected` |
| AC-016 | Owner manages own requests only; others get 403 | Pass — `RequestPermissionTests` (six tests incl. `test_my_requests_lists_only_own`) |
| AC-017 | Status changes follow the documented state machine | Pass — `TransitionTests.test_open_to_matched`, `test_illegal_transition_rejected`, `test_fulfilled_cannot_be_reopened` |
| AC-018 | Cancelled / expired / partially fulfilled / fulfilled tracked distinctly | Pass — `test_cancel_from_open`, `test_partial_fulfilment_records_units`, `ExpiryTests.test_overdue_request_expires` |
| AC-019 | Viewing potential matches never auto-fulfils a request | Pass — `MatchingLeadTests.test_viewing_matches_does_not_change_status` |
| AC-020 | Duplicate abuse reports by same user blocked | Pass — `CommunityBoardTests.test_abuse_report_flow` (single-report guard; duplicate *request* submissions documented in DECISIONS.md D-07) |
| AC-021 | Status changes record actor, from, to, timestamp | Pass — `TransitionTests.test_status_history_recorded` |

## Matching and safety
| ID | Criterion | Status / evidence |
|---|---|---|
| AC-022 | Compatibility map correct for all 8 groups (and inverse) | Pass — `CompatibilityMapTests.test_all_eight_groups`, `test_inverse_lookup` |
| AC-023 | Matches presented as potential leads with disclaimer | Pass — disclaimers in search/detail/dashboard templates; verified in smoke test |
| AC-024 | Contact revealed only with consent + authenticated viewer | Pass — `MatchingLeadTests.test_match_cards_respect_privacy` |
| AC-025 | Emergency guidance shown in UI | Pass — footer + request-form + board banners; verified in smoke test |

## Administration, audit, privacy
| ID | Criterion | Status / evidence |
|---|---|---|
| AC-026 | Admin dashboard stats computed from real DB counts | Pass — `AdminDashboardTests.test_staff_sees_dashboard_with_real_stats` |
| AC-027 | Abuse reports submitted, reviewed with status + reviewer | Pass — `test_abuse_report_flow`, `AbuseReviewTests.test_staff_marks_reviewed` |
| AC-028 | Status history acts as audit trail; visible to owner/admin | Pass — `test_status_history_recorded`; recent history listed on the admin dashboard |
| AC-029 | Safe error pages; no secrets in responses | Pass — custom 403/404/500 handlers via `config.views`; `.env` git-ignored |
| AC-030 | Profile deactivation hides donor without deleting data | Pass — `DonorProfileTests.test_deactivation_hides_profile` |

## Quality and delivery
| ID | Criterion | Status / evidence |
|---|---|---|
| AC-031 | Schema changes only via versioned migrations | Pass — `donors/migrations/0001_initial.py`, `blood_requests/migrations/0001_initial.py` |
| AC-032 | Documented test suite runs with actual results reported | Pass — `manage.py test` → **OK, 84 tests** |
| AC-033 | REST/OpenAPI contract | N/A — template-based Django app per approved stack switch (DECISIONS.md D-01) |
| AC-034 | Loading/empty/error states present | Pass — empty states on search/board/requests list; verified in smoke test |
| AC-035 | App starts locally from clean setup using README | Pass — venv + migrate + `runserver` smoke test (HTTP 200 on public pages) |
| AC-036 | No known critical authorization/data-exposure defect at acceptance | Pass — permission + privacy tests green (84/84) |
