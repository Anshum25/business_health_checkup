# Implementation plan

Phases after Phase 1, based on [workbook_audit.md](workbook_audit.md) and [data_model.md](data_model.md). Each phase lists the open questions ([open_questions.md](open_questions.md)) that must be answered before it starts; anything still open stays out of that phase.

## Phase 1 — done (2026-10-27)

- App `business_health_checkup` created (`bench new-app`) and installed on `ai-erpnext.local`.
- Workbook audited: `docs/workbook_audit.md`.
- Workbook masters extracted with source cells and file hash: `business_health_checkup/workbook_v1/{rules,departments,questions}.json`.
- Scoring engine `business_health_checkup/scoring.py` (question score, department and overall totals, maturity, priority, gap ranking, suggested dates) — pure Python, verified against the workbook’s cached results.
- 28 unit tests (`business_health_checkup/tests/`), no site needed.
- No DocTypes, no hooks beyond the app metadata, no data written to the site.

## Phase 2 — masters, assessments, scoring integration, access control — done (2026-10-27)

Built (details in [data_model.md](data_model.md)):

- 14 DocTypes: BHC Department (+ Growth Recommendation), BHC Question, BHC Scoring Model (+ 5 rule tables), BHC Business (+ Business User), BHC Assessment (+ Assessment Response, Assessment Department Result).
- Idempotent importer `business_health_checkup.setup.importer.import_workbook_v1` (validates the whole package first; creates missing records; reports conflicts and extra records without overwriting), run automatically by `after_install`.
- Assessment controller and `business_health_checkup/assessments.py`: question snapshot on creation, snapshot tamper checks, scoring through `scoring.py` only, results verification, re-assessment, comparison data.
- `scoring.py`: backward-compatible additions only — optional growth/strength thresholds on `Rules` and `growth_status()` (BUSINESS GROWTH PLAN!E8, workbook parity).
- Roles BHC Consultant and BHC Manager; fail-closed record-level access (`permissions.py`), share blocking.
- Form script: *Create → Re-assessment*, *Verify Results*, link filters.

Verified:

- `ci-test.local`: app installed with `bench --site ci-test.local install-app business_health_checkup` (import: 10 departments, 150 questions, scoring model BHC-SM-0001); **83 tests pass** (51 integration + 32 unit); the test runs leave no records behind.
- `ai-erpnext.local`: fresh backup `20261027_163150`; this app's DocTypes synced with `bench --site ai-erpnext.local execute frappe.model.sync.sync_for --args '["business_health_checkup"]'`, then `…setup.install.after_migrate` (roles), `clear-cache` and the importer (10 / 150 / BHC-SM-0001 created; a second dry run reports everything unchanged). All 14 tables exist. A smoke test in a rolled-back transaction created a business and an assessment with the workbook sample answers (24.242424 %, 8 / 33), finalised it, verified it, and confirmed an unassigned consultant sees nothing.
- A **full `bench migrate` was not run on `ai-erpnext.local`**: it would also apply other apps’ pending changes (the `proposals` app has uncommitted DocType and print-format work not yet approved for that site). The targeted sync is what `migrate` does for this one app. Run a full migrate when you are ready to take everyone’s changes; it will find this app already in sync.

Still open from the Phase 2 brief: every blocking question (open_questions.md). Nothing in the code decides them; the provisional behaviour of each is listed there.

## Phase 3 — gap analysis, department ranking, re-assessment comparison — done (2026-10-27)

Built (details in [data_model.md](data_model.md) §5.4–5.6 and §9):

- `scoring.py` (pure, workbook formulas only): `rank_departments` (SCORE CALCULATION!T5:U14, exact parity) and `repeated_problem_area` (GAP ANALYSIS!H7).
- `analysis.py` (new, Frappe-free): coverage labels and the read-only comparison of two stored assessments.
- `assessments.py`: `department_rows`, `assessment_view`, whitelisted `get_results_summary`, and a rewritten `get_comparison`.
- `reporting.py` (new): the permission-filtered assessment query every report starts from.
- Script Reports **BHC Gap Analysis**, **BHC Department Results**, **BHC Assessment Comparison**.
- Assessment form: Results Summary section, *View* buttons for the three reports, Connections (re-assessments), list-view status indicator; BHC Business Connections (assessments).
- No new DocType and no new database column (the Results Summary is an HTML field; rank and coverage are derived from stored values).

Decisions not taken (open_questions.md): Q-04 (rank and growth status of unassessed departments kept at workbook parity, coverage shown beside them), Q-05 (growth status is a label only), Q-11 (difference in points only when both sides are assessed, comparability flagged, no improvement/decline wording); new Q-19, Q-20, Q-21.

Verified:

- `ci-test.local`: this app synced (`sync_for`); **116 tests pass** (71 integration + 45 unit). New tests cover gap rows and order against GAP ANALYSIS!A19:N22, every report filter, cancelled/draft handling, snapshot and phase of finalised gaps after master and model changes, workbook rank against SCORE CALCULATION!U5:U14, coverage of unanswered / all-N/A / partly / fully answered departments, the repeated-problem rule, results summary, comparison with the same rules, a different scoring version, changed / added / removed questions, a cancelled previous assessment, no previous assessment, read-only and repeatable comparisons, and report/service access for assigned, unassigned, role-less and System Manager users. Removing the permission filter from `reporting.py` makes 5 permission tests fail (checked, then restored).
- `ai-erpnext.local`: backup `20261027_165426`; same app-only sync as Phase 2 (adds the HTML field and the three Report records; no data change, nothing from other apps). Smoke test in a rolled-back transaction: gap report, department ranks, comparison (+30.30 points overall, +43.48 STR, HR not comparable), results summary; an unassigned consultant saw no rows and was refused the comparison. Form and report scripts load.

## Phase 4 — improvement actions and 90-day plan — done (2026-10-27)

Built (details in [data_model.md](data_model.md) §5.7, §6, §9):

- DocType **BHC Improvement Action** (one per gap selected for action; gap context copied from the source assessment and read-only; agreed action, responsible, responsible user, target / measure, start and target dates, status, completed on, remarks).
- `planning.py` (new, Frappe-free): status list, suggested dates without a fallback to today, the ACTION PLAN date validation, “overdue” (ACTION PLAN!Q8) and the A4:G4 counters.
- `actions.py` (new): creation from selected gaps (validated first, savepoint, idempotent), source snapshot and tamper checks, date / responsible-user / status validation, completion date, reopening guard, link queries.
- `permissions.py`: actions follow the source assessment’s business (list conditions, document check, sharing blocked).
- Script Report **BHC 90 Day Plan**; Gap Analysis gains *Improvement Action* / *Action Status* columns; Department Results links each department’s gap count to its gaps.
- Assessment form: *Create → Improvement Actions* dialog, *View → 90 Day Plan / Improvement Actions*, action counts in the Results Summary, Connections; action form and list view.
- No scheduled jobs, notifications or new dependencies.

Decisions not taken (open_questions.md): Q-07 and Q-14 (provisional handling implemented and isolated), new Q-22 to Q-26.

Verified:

- `ci-test.local`: **163 tests pass** (109 integration + 54 unit; baseline before Phase 4 was 116). New tests cover creation from selected gaps, no automatic actions, every invalid source (draft, cancelled, missing, not a gap, N/A, unanswered, unknown, empty), forged caller values, read-only source fields, duplicates and retries, an all-or-nothing failure, phases and suggested dates at days 0/30/31/60/61/90, a missing assessment date, agreed-date validation, status values, completion date and reopening (including the version log), responsible-user eligibility, master / scoring-model / other-assessment / re-assessment changes, traceability, deletion protection, the 90 Day Plan rows, order, overdue rule, every filter and summary, and access for assigned consultant, assigned manager, unassigned consultant, role-less user and System Manager (lists, direct and API access, creation, link queries, sharing, Assign To, report). Two permission mutations (no list conditions; trusting the action’s own business field) were each caught by the tests, then reverted.
- `ai-erpnext.local`: backup `20261027_172152`; app-only sync (`sync_for`), adding the action table (unique `source_key` index) and the 90 Day Plan report; no data changed, nothing from other apps. Smoke test in a rolled-back transaction: no actions on finalising, eligible gaps as in the workbook, creation and retry, completion, 90 Day Plan figures, and an unassigned consultant seeing nothing and refused creation. Form, list and report scripts load.

## Phase 5 — management report and owner dashboard — done (2026-10-27)

Specification and audit: [workbook_audit.md](workbook_audit.md) §11 (MANAGEMENT REPORT!A1:H115, OWNER DASHBOARD!A1:P50, Q-08, Q-15).

Built:

- `management.py` (new): `get_management_report` and `get_owner_dashboard` (whitelisted), built only from stored results through the Phase 3–4 functions (department rows and workbook rank, `get_comparison`, action counters, suggested dates); workbook text formats (`0%` and `+0%` rounding half away from zero, “dd mmmm yyyy”, “dd-mmm-yyyy”); section limits as constants (Q-15).
- `charts.py` (new, Frappe-free): bar, radar and trend charts as escaped SVG, with “not assessed” departments drawn apart.
- Print format **BHC Management Report** (Jinja, standard, Chrome PDF) on BHC Assessment: the ten workbook sections, draft banner, signature lines; §8 states that the KPI numbers are not recorded (Q-10).
- Desk page **BHC Owner Dashboard** (`/app/bhc-owner-dashboard`): the eight cards, heat map with band colours and coverage, trend table and chart, bar and radar charts, links; the 10-number KPI block states it is not recorded.
- Assessment form: *View → Management Report* and *View → Owner Dashboard*.
- `permissions.py` / hooks: Document Share Keys refused for BHC records; Jinja method for the print format.
- No new DocType, field, scheduled job, e-mail or dependency.

Verified:

- `ci-test.local`: **187 tests pass** (128 integration + 59 unit; baseline 163). New tests check every Management Report section and the dashboard cards, heat map and trend against the workbook’s cached values for its sample, actions versus recommendations and agreed versus suggested due dates, change against a re-assessment, no answers, draft and cancelled assessments, print rendering, escaping, no writes when viewing, and access for assigned consultant / manager, unassigned consultant, role-less user and System Manager through the API, the print view, the print render, share links and the page roles, plus forged identifiers. Two mutations (no permission check before loading; no share-key block) are each caught; a chart rounding inconsistency (54.5 → 54 %) was found and fixed.
- `ai-erpnext.local`: backup `20261027_174800`; app-only sync adding the print format and the page; the site’s existing assessments render (read only, unchanged); a rolled-back smoke test produced the workbook’s figures, the print HTML with charts and a PDF, and denied an unassigned consultant on all paths.

## Phase 6 — KPI tracking (only if Q-10 says so)

BHC KPI Review per business per period; KPI CALCULATOR formulas (workbook §3.6) added to the engine with tests for every zero-denominator guard; the 10-number dashboard with On Track / Watch / Off Track (tolerance from the scoring model) and trend vs the previous period’s record.

## Not planned

Unless a confirmed requirement asks for them: AI/LLM features, external APIs, scheduled jobs or background monitoring, notifications, a client portal, automatic submission or closing of records, and any change to ERPNext or to the other apps on this bench.

## Next step

1. Send the status table at the top of [open_questions.md](open_questions.md) to the manager. Phase 6 needs Q-10 (KPI tracking in scope?); Q-08 and Q-15 decide whether the report stays as the workbook has it; Q-27 to Q-29 are new; the provisional answers of Phases 2–4 still need confirming.
2. Phase 6 only if Q-10 says so; otherwise the system is functionally complete against the workbook apart from KPI tracking.
