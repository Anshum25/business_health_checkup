# Open questions for the manager

These decisions are not settled by the workbook (`Business_Health_Checkup_System.xlsx`). Until they are answered, the system follows the workbook where it is explicit and leaves the rest unbuilt. References like W-01 point to [workbook_audit.md](workbook_audit.md) §8.

Each question lists what the workbook does today, the realistic options, and what the answer changes. Options are not recommendations unless marked.

## Status after Phase 5 (2026-10-27)

**No question has been answered yet**: no answer is recorded in this file, the Phase 2–5 briefs, or any other project document. Phases 2–5 were built so that none of the blocking questions is decided by the code: where something had to work, the least-privilege or workbook-parity behaviour below is in place, isolated in one spot, and easy to change.

| Q | Status | What the system does now (provisional) | What an answer changes |
|---|---|---|---|
| Q-01 | open | Masters imported from `Business_Health_Checkup_System.xlsx` (sha256 `e3424382…0e22fc`); every record keeps its source cell. | A different “(2)” file → re-extract into `workbook_v2/`, import as a new scoring model + question changes; existing assessments keep v1. |
| Q-02 | open | Nothing uses IOC/MSE. | Possibly a new field or report. |
| Q-03 | open | Two roles exist without deciding who holds them: **BHC Consultant** (capture) and **BHC Manager** (may also finalise). Both see only assigned businesses. | Role assignment only, or wider manager visibility (Q-18). |
| Q-04 | open | Workbook parity, made visible: unassessed departments keep score 0, maturity “Not Assessed”, growth status “PRIORITY - GROWTH PLAN”, and the **workbook rank** (SCORE CALCULATION!U5, 1 = weakest, so they rank as weakest). Every place that shows a rank or score also shows **Coverage** (“Not assessed (no answers)”, “Not assessed (all N/A)”, “Partly answered”, “Fully answered”), and the form/report grey out a not-assessed 0 %. No alternative ranking was invented. Finalising does not require completeness. | Option (a): `rank_departments` would skip unassessed departments (one call site, `assessments.department_rows`) and growth status would be blank for them; option (c): a check in `before_submit`. |
| Q-05 | open | Growth status shown as the workbook label only (“Growth Plan Status (workbook)” in the form and Department Results report); no decision is recorded and nothing is started from it. | Possibly a growth-decision child table (data_model §7). |
| Q-06 | open | No workflow. Draft → Finalised (submit). Submit permission: BHC Manager and System Manager. Cancel/amend: System Manager only. | A Frappe Workflow with a review state, or giving BHC Consultant submit permission (Role Permission Manager, no code). |
| Q-07 | open | **Option (c)-like, provisional**: a gap is not an action. An action is created only when a user with access to the business selects gaps of a *finalised* assessment (*Create → Improvement Actions* on the form, or an action form); nothing is pre-selected and nothing is created on finalising. One action per (assessment, question), as ACTION PLAN has one row per question (unique `source_key`; a retry returns the existing action). ACTION PLAN counters are computed over actions; “Gaps Without an Action” is shown separately. | Option (a) would add one call in `BHCAssessment.on_submit` (`actions.create_actions` for every gap); (b) would pre-tick all gaps in the dialog. |
| Q-08 | open | **Workbook-specified part built**: the one printable report, MANAGEMENT REPORT, is the print format *BHC Management Report* on BHC Assessment (print view and PDF); OWNER DASHBOARD is the desk page *BHC Owner Dashboard*; the earlier on-screen views are the Phase 3–4 reports. No report-type selection, distribution, e-mail or scheduling (the workbook has none). | Other formats, a report chooser or distribution rules would be additions. |
| Q-09 | open | Only users with a BHC role on an assigned business can enter answers; there is no portal or client login. | Client accounts would need their own role and the same assignment check. |
| Q-10 | open | Not built. `kpi_watch_tolerance` is stored on the scoring model only. | BHC KPI Review (Phase 6). |
| Q-11 | open | `previous_assessment` is chosen by the user (or set by *Create → Re-assessment*); it must be a finalised assessment of the same business, not dated later. The comparison (service + *BHC Assessment Comparison* report) shows stored scores side by side and a **difference in percentage points only when both sides have applicable answers** (the workbook’s S5 = H5 − R5 would show a change against an unanswered 0); a **Comparable** flag is No when the scoring rules, the question snapshot or the assessed state differ, with the reasons listed. No result is labelled as an improvement or a decline. Suggested re-assessment date = date + 90, display only. | How a change should be read or labelled; whether the workbook’s “change against 0” is wanted. |
| Q-12 | open | Scoring models: System Manager only (create, submit, set default); masters (departments, questions): System Manager only. | Grant BHC Manager write/submit on those DocTypes (Role Permission Manager). |
| Q-13 | open | No Customer link; business profile not copied per assessment. | Add an optional Link field (and `required_apps = ["erpnext"]`); optional profile snapshot fields. |
| Q-14 | open | **Option (c), provisional**: `responsible` is free text (as in ACTION PLAN K) and `responsible_user` an optional system user, who must be enabled and already able to see the business (Assigned Users or System Manager). Naming someone never gives access; there is no action-owner role, so owners without a BHC role and assignment cannot update their actions. | (a) would add a BHC Action Owner role and a permission rule “responsible_user = me” (permissions.py); (b) would drop `responsible_user`. |
| Q-15 | open | **Workbook limits kept** in the Management Report: top 10 gaps, top 15 actions, 3 strengths, 3 priority areas, 5 roadmap rows with 3 steps each (constants in `management.py`, each citing its cells); each section points to the full report. The on-screen reports show everything. | Changing a constant (or removing the limit) per section. |
| Q-16 | open | Workbook parity: N/A counts as answered for completion and is excluded from the score. No reason required. | Possibly make evidence mandatory for N/A. |
| Q-17 | open | Evidence is stored per answer per assessment (text). No attachments built. | Attachment field/handling. |
| Q-18 | open | **Fail closed**: a user sees a business and its assessments only if listed in its Assigned Users, which only a System Manager can edit; no assignment = nothing visible. Sharing and “Assign To” cannot grant access. System Manager sees everything. | Manager-sees-all (one line in `permissions.py`), team-based assignment, or client logins. |

| Q-19 | open (new) | When both assessments are scored with the same rules and questions but **different questions were answered** (e.g. more questions answered the second time), the difference is still marked Comparable and the limitation “Different questions were answered (other than N/A)” is listed. | Whether such a difference should count as not comparable. |
| Q-20 | open (new) | Reports include Draft and Finalised assessments by default (the Status filter narrows them); Cancelled ones only on request, because their amendment repeats the same answers. | Whether drafts (provisional answers) should be left out of reports by default. |
| Q-21 | open (new, low impact) | The workbook’s department rank breaks ties with `+ROW()/1000000` (W-09), reproduced exactly. With the workbook weights this only orders equal scores by department; it would only misorder nearly equal scores if a future scoring model used much larger weights. | Whether to rank strictly by score with ties in department order, should weights ever change. |
| Q-22 | open (new) | Department growth recommendations (RECOMMENDATION MASTER, 7 per department, shown by BUSINESS GROWTH PLAN below 60 %) are not actions; only question gaps are, because ACTION PLAN holds only question rows. The growth status stays a label. | A second action source (department + recommendation seq). |
| Q-23 | open (new) | Statuses are the workbook’s four (Open, In Progress, Completed, Hold). There is no Cancelled / Not required status; a mistaken action can be put on Hold or deleted by a System Manager (deletion keeps no history). | Whether a “Cancelled” or “Not required” status is needed. |
| Q-24 | open (new) | Anyone with access can complete an action; **taking an action out of Completed** (which clears its completion date) is limited to BHC Manager and System Manager. The completion date is set by the system on the day the status becomes Completed and cannot be typed; old values stay in the version log. No evidence is required to complete (the workbook has only Remarks). | Who may complete or reopen; whether completion needs evidence or a reviewer. |
| Q-25 | open (new) | One action per gap. A second action for the same gap is refused. | Whether several actions per gap are allowed. |
| Q-26 | open (new) | Actions stay attached to their source assessment if a System Manager cancels it (the 90 Day Plan shows the source status); they are not moved to an amendment or to a re-assessment, and nothing is closed or cancelled automatically. A cancelled source with actions cannot be deleted. | Whether actions should follow an amendment, or a re-assessment should carry open actions over. |
| Q-27 | open (new) | The Management Report’s department risk (§6) and growth steps (§9), and the company profile (§1), are read from the current BHC Department / BHC Business records; the assessment keeps no copy of them (the workbook reads them live too). Scores, gaps, recommendations and risks of questions are the assessment’s own snapshot. | Whether to snapshot department risks / growth recommendations and the profile per assessment (W-20, Q-13). |
| Q-28 | open (new) | Unassessed departments appear in the Management Report’s Major Strengths, Priority Areas and Growth Roadmap exactly where the workbook rank puts them (workbook parity, W-01 / W-08), each marked “not assessed”. | Part of Q-04. |
| Q-29 | open (new) | Draft assessments can be printed (marked “not finalised”); cancelled ones follow Frappe’s Print Settings (not printable by default). Share links (Document Share Keys, e.g. the “view link” Frappe can add to e-mails) are refused for BHC records, so a printed report cannot be opened by someone outside the business’s Assigned Users. | Whether drafts may be printed; whether reports are ever sent to people without a login. |

The rest of this file is the original question list.

---

## A. Source and terminology

### Q-01 — Which workbook is authoritative?
The brief names `Business_Health_Checkup_System(2).xlsx`. Only `Business_Health_Checkup_System.xlsx` exists on the server (SHA-256 `e3424382…0e22fc`, 27 Oct 2026). The audit and the data in `workbook_v1/` come from that file.
- **Need:** confirm it, or provide the “(2)” file so the two can be compared.
- **Impact:** question texts, weights and rules in `workbook_v1/` would be re-extracted.

### Q-02 — What do “IOC” and “MSE” mean?
Neither term (nor “MSME”) appears anywhere in the workbook.
- **Need:** a definition, and whether they change the scope (e.g. a client category, a report, an industry segment).
- **Impact:** none on Phase 1; nothing has been built around them.

---

## B. Decisions and workflow

### Q-03 — Who is “the manager”, and what does the manager decide?
The workbook has only two roles in practice: the consultant who runs the facilitated review, and “Management”, who signs the Management Report next to the consultant (`MANAGEMENT REPORT!F114`). It has no approval step.
- **Need:** is the manager (a) someone in the consultancy who reviews the consultant’s work, (b) the client’s owner/MD, or (c) both?
- **Impact:** role design (see data_model.md §6) and whether a review state is needed (Q-06).

### Q-04 — How should a department with no applicable answers be treated?
The workbook labels it “Not Assessed” but gives it score 0, so it ranks as the weakest department, is flagged “PRIORITY - GROWTH PLAN”, can be printed as a “Major strength”, and is counted in “Departments in growth programme: n of 10” (W-01, W-08).
- **Options:** (a) exclude unassessed departments from ranking, growth status and strengths; (b) keep the workbook behaviour; (c) block finalising an assessment until every department has answers.
- **Impact:** department ranking, Business Growth Plan, Management Report §4/§6/§9. The scoring engine already reports `assessed = False` for these departments; ranking and growth status are not built until this is decided.

### Q-05 — Is the growth programme a decision or a recommendation?
The workbook states that every department scoring below 0.6 gets “GROWTH PROGRAMME REQUIRED” and its 7 standard recommendations (`BUSINESS GROWTH PLAN`, `INSTRUCTIONS!C9`). Nothing records whether management accepted it.
- **Options:** (a) show it as the workbook does, as an automatic label; (b) show it as a recommendation the manager accepts, adjusts or rejects, and record that decision; (c) other.
- **Impact:** whether the assessment stores a manager decision per department.

### Q-06 — Is there a review / approval step before results are final?
The workbook has none; results are live as answers are typed. Signature lines for Consultant and Management are printed at the end of the report.
- **Options:** (a) consultant finalises alone; (b) consultant submits, manager approves (and can send back); (c) consultant finalises, client management acknowledges.
- **Impact:** document workflow states and who may submit.

### Q-07 — Does every gap become an action?
ACTION PLAN lists every gap as an action row (blank status counts as Open); there is no way to accept, reject or defer a gap except filtering (workbook §6.2).
- **Options:** (a) create an action for every gap when the assessment is finalised (workbook behaviour); (b) the manager selects which gaps get actions (default all); (c) actions are only created on request.
- **Impact:** action creation logic and the “Total actions” / completion % figures.

### Q-08 — Which reports are required?
The workbook has one formal report (MANAGEMENT REPORT, printed) and on-screen views: Assessment Hub, Gap Analysis, Action Plan, 90-Day Plan, Business Growth Plan, Owner Dashboard (workbook §5).
- **Need:** confirm which of these are needed, which must be printable/PDF, and whether the manager chooses between report types (the brief mentions this; the workbook has no such choice).
- **Impact:** Phase 4 scope.

### Q-09 — Who enters answers?
The workbook assumes a facilitated review: the consultant enters answers with the client’s department heads (`INSTRUCTIONS!C3`). No self-service input exists.
- **Options:** (a) consultant only (no portal); (b) client users fill some departments themselves.
- **Impact:** (b) would need client user accounts with strict record isolation, possibly a portal. Not designed in until confirmed.

---

## C. Re-assessment and history

### Q-10 — Is KPI tracking in scope?
KPI CALCULATOR and the Owner’s 10-Number Dashboard hold one period of numbers, with no history and no link to an assessment (W-11, W-12). KPI MASTER (45 definitions) is reference only.
- **Options:** (a) out of scope for now; (b) a KPI record per business per period (month/quarter); (c) KPI values captured as part of each assessment.
- **Impact:** an extra DocType (`BHC KPI Review`, data_model.md §4.7) and its reports.

### Q-11 — Which assessment is “previous”, and is re-assessment always ~90 days?
The workbook compares with the assessment number just before the current one, even if that one was never answered (W-05). It recommends re-assessment at assessment date + 90 days and labels assessments 2–4 “Quarter 2–4”; it allows only 4 per workbook.
- **Options for “previous”:** (a) the latest *finalised* assessment of the same business before this one (suggested by the data model); (b) chosen by the consultant.
- **Need:** is the 90-day interval a fixed rule, a default suggestion, or just text on the report? Is the 4-assessment limit a requirement? (Assumed: no.)
- **Impact:** trend report, “change vs previous”, any reminder of due re-assessments (none is planned).

### Q-12 — Who may change scoring parameters, and how?
SETTINGS is unprotected and “changes flow automatically to every sheet”, which also rewrites past results (W-02).
- **Options:** (a) parameters fixed to the workbook values; (b) editable by an administrator, versioned, with each assessment keeping the version it was scored with (designed in data_model.md); (c) editable per client.
- **Also:** should the hard-coded thresholds — “repeated problem area” (3 HIGH / 8 gaps) and score colour limits — become editable (W-07)?

---

## D. Data details

### Q-13 — Should the assessed business be an ERPNext Customer?
The workbook’s Company Profile is a standalone record. In ERPNext the consultancy’s clients are normally Customers.
- **Options:** (a) separate `BHC Business` record, optionally linked to a Customer (suggested); (b) Custom Fields on Customer; (c) standalone with no link.
- **Also:** should employee count, turnover, customer count etc. be recorded per assessment (W-20)?

### Q-14 — Is “Responsible” a system user?
In ACTION PLAN it is free text.
- **Options:** (a) a system user, who can then update their own actions; (b) free text (name of a client employee without a login); (c) both (user optional, name always).
- **Impact:** whether an “action owner” role is needed.

### Q-15 — Are the report limits requirements?
Top 10 gaps, 15 actions, 3 strengths, 3 weakest, 5 growth rows, 50 actions per 90-day phase (W-10).
- **Need:** keep as is, or show everything?

### Q-16 — Does N/A count as “answered”?
Completion % counts N/A as answered; N/A is excluded from the score (W-17). `INSTRUCTIONS!C6` says “use sparingly”.
- **Need:** confirm; and whether N/A needs a mandatory reason (evidence/remarks).

### Q-17 — Evidence and remarks per assessment
The workbook keeps one remarks column for all four assessments (W-03). The data model stores evidence per answer per assessment.
- **Need:** confirm, and whether evidence attachments (photos, documents) are wanted.

### Q-18 — Who may see what?
The workbook has no access control (one file per company). In the system several clients share one database.
- **Need:** confirm that consultants see only the businesses assigned to them, managers see all, and that clients (if they get logins, Q-09) see only their own business.
