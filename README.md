### Business Health Checkup

A Frappe app that turns the *Manufacturing Business Health Checkup* workbook (`Business_Health_Checkup_System.xlsx`) into a system: record a business, run an assessment of 150 questions over 10 departments, score it with the workbook’s rules, and give the results to the manager for the decisions that follow (reports, actions, re-assessment).

**Status: Phase 5.** Masters, versioned scoring models, businesses and assessments work end to end with record-level access control; gap analysis, department results with the workbook ranking, comparison with a previous assessment, improvement actions, the 90-day plan, the printable Management Report and the Owner Dashboard are available. KPI tracking (the workbook's KPI CALCULATOR and Owner's 10 numbers) is not built (open question Q-10). Several business decisions are still open and are handled provisionally (see [docs/open_questions.md](docs/open_questions.md)).

| Document | Content |
|---|---|
| [docs/workbook_audit.md](docs/workbook_audit.md) | Every sheet, formula, threshold and report of the workbook, with cell references (source of truth for formulas) |
| [docs/data_model.md](docs/data_model.md) | Implemented DocTypes and fields, assessment lifecycle, scoring integration, access control |
| [docs/implementation_plan.md](docs/implementation_plan.md) | Phase status and what blocks each next phase |
| [docs/open_questions.md](docs/open_questions.md) | Decisions needed from the manager, and what the system does until then |

#### How it works

1. A System Manager imports the masters (automatic on install), creates a **BHC Business** and lists the users who may work on it under *Assigned Users*.
2. A **BHC Consultant** creates a **BHC Assessment**. It copies every active question, with the weight of the default **BHC Scoring Model**, and the consultant answers YES / PARTIALLY / NO / N/A with evidence. Each save scores the assessment on the server.
3. A **BHC Manager** (or System Manager) submits it: the assessment is *Finalised* and frozen.
4. *Create → Re-assessment* starts a new, separate assessment linked to the finalised one.
5. Results: the assessment form's **Results Summary**, and the reports below (also under *View* on the form).
6. On a finalised assessment, *Create → Improvement Actions* turns the gaps you tick into **BHC Improvement Actions** (nothing is created automatically). Each action keeps the gap's priority, 90-day phase, suggested dates and recommendation from that assessment; you maintain the agreed action, responsible person, agreed dates, target / measure, status and remarks.

7. **Management Report**: *View → Management Report* on the assessment (print view / PDF, print format *BHC Management Report*), the workbook's ten sections. **Owner Dashboard**: *View → Owner Dashboard*, or `/app/bhc-owner-dashboard` — cards, heat map, trend and charts for one assessment.

#### Reports

| Report | Shows | Filters |
|---|---|---|
| BHC Gap Analysis | every NO / PARTIALLY answer ranked as in the workbook's GAP ANALYSIS, with recommendation, KPI, risk and 90-day phase; totals per priority and points lost | business, assessment, status, department, criticality, priority, answer |
| BHC Department Results | per department: workbook rank (1 = weakest), coverage (not assessed / partly / fully answered), answered, N/A, score, maturity, gaps, growth plan status, repeated problem area | business, assessment, status, department, coverage, sort |
| BHC 90 Day Plan | improvement actions by assessment and gap order with phase, priority, responsible, suggested and agreed dates (separately), status, completion date and overdue (agreed target date passed, not completed); totals as in the workbook's ACTION PLAN | business, assessment, department, priority, phase, status, responsible, responsible user, target date range, overdue only |
| BHC Assessment Comparison | an assessment against its previous one: scores, difference in percentage points (only when both sides were assessed), comparable yes/no with reasons; per department or per question | assessment, show |

A department with no applicable answer keeps the workbook's 0 % and rank but is always labelled *Not assessed* (open question Q-04). Every report, list and action shows only businesses the user is assigned to; naming someone as an action's responsible person gives them no access.

#### Layout

```
business_health_checkup/
  scoring.py          scoring engine (no Frappe imports); the only implementation of the workbook formulas
  assessments.py      snapshot, scoring, verification, results, re-assessment and comparison for BHC Assessment
  analysis.py         coverage labels and assessment comparison (no Frappe imports)
  reporting.py        permission-filtered assessment query shared by the reports
  planning.py         ACTION PLAN / 90 DAY PLAN rules: statuses, suggested dates, overdue, counters (no Frappe imports)
  management.py       Management Report and Owner Dashboard data, from stored results
  charts.py           bar / radar / trend charts as SVG (no Frappe imports)
  actions.py          improvement actions: creation from selected gaps, snapshot, validation, link queries
  permissions.py      record-level access (assigned users only; sharing blocked)
  setup/importer.py   idempotent import of workbook_v1/ into the masters
  setup/install.py    roles and import on install
  workbook_v1/        rules.json, departments.json, questions.json copied from the workbook,
                      each value with its source cell and the workbook's SHA-256
  business_health_checkup/doctype/   the 15 BHC DocTypes
  business_health_checkup/report/    the 4 BHC script reports
  business_health_checkup/print_format/  BHC Management Report
  business_health_checkup/page/      BHC Owner Dashboard
  tests/              unit tests (engine, package) and integration tests (masters, assessments, permissions)
docs/                 audit and design documents
```

#### Prerequisites

Frappe v16 bench with Python 3.14 and Redis/MariaDB running. ERPNext v16 is on the bench but not required (Q-13). No third-party Python packages.

#### Installation

```bash
bench --site <site> install-app business_health_checkup      # creates roles and imports the masters
bench --site <site> list-apps
```

On a site where the app is already installed, sync it and import:

```bash
bench --site <site> migrate      # or, for this app only:
bench --site <site> execute frappe.model.sync.sync_for --args '["business_health_checkup"]'
bench --site <site> execute business_health_checkup.setup.install.after_migrate
bench --site <site> clear-cache
bench --site <site> execute business_health_checkup.setup.importer.import_workbook_v1
```

The importer can be run any time; add `--kwargs "{'dry_run': True}"` to only report. It creates missing records, reports records that differ from the workbook (conflicts) or exist only in the database (extra), and never overwrites or deletes anything.

Installed on this bench: `ci-test.local` (test site) and `ai-erpnext.local` (DocTypes synced for this app only; see docs/implementation_plan.md).

#### Tests

Unit tests (no site needed), from the bench directory:

```bash
env/bin/python -m unittest business_health_checkup.tests.test_scoring business_health_checkup.tests.test_workbook_data business_health_checkup.tests.test_analysis business_health_checkup.tests.test_planning business_health_checkup.tests.test_charts
```

All tests, on a **test site** that has the app installed (they create records and roll them back):

```bash
bench --site ci-test.local run-tests --app business_health_checkup
bench --site ci-test.local run-tests --module business_health_checkup.tests.test_permissions
bench --site ci-test.local run-tests --module business_health_checkup.tests.test_results
bench --site ci-test.local run-tests --module business_health_checkup.tests.test_actions
bench --site ci-test.local run-tests --module business_health_checkup.tests.test_action_permissions
bench --site ci-test.local run-tests --module business_health_checkup.tests.test_management
bench --site ci-test.local run-tests --module business_health_checkup.tests.test_management_permissions
```

Do not run the integration tests on a working site.

#### Development

- Formatting and linting: `ruff` (tabs, line length 110) via `pre-commit` (`cd apps/business_health_checkup && pre-commit install`).
- All scoring goes through `scoring.py`, called only from `assessments.py`. Controllers, reports, APIs and form scripts must not re-implement a formula or trust a score sent by the browser.
- Reports read assessments only through `reporting.permitted_assessments` (or a permission-checked service), never with `frappe.get_all` on assessments; actions only through `frappe.get_list`.
- The Management Report and Owner Dashboard read data only through `management.py`, which checks read permission; BHC records cannot be shared or given share links.
- Improvement actions are created only through `actions.create_actions` or an action insert, which copy the gap from the source assessment on the server; never trust a priority, phase or date sent by the browser.
- `workbook_v1/` is source data. If the workbook changes, extract it into a new folder (e.g. `workbook_v2/`) and import it as a new scoring-model version instead of editing values, so existing assessments stay reproducible.
- DocType JSON can be edited in the desk only with `developer_mode`; `ai-erpnext.local` has it off, so edit the JSON files and bump `modified`.

#### License

MIT
