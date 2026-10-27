"""Improvement actions (the workbook's ACTION PLAN) for gaps of finalised assessments.

Gap, recommendation and action are kept apart:

- A **gap** is a stored response of a finalised assessment with gap points > 0. Its priority was scored with the
  assessment's own scoring model and is part of the frozen assessment.
- Its **recommendation** is the question's recommendation as copied into that assessment.
- An **action** exists only when an authorised user creates one for the gap (provisional answer to Q-07: the
  workbook lists every gap as an action row; here nothing is created automatically, not even on finalising).

The workbook has one ACTION PLAN row per question, so there is one action per (assessment, question); the unique
`source_key` makes a retried request find the existing action instead of creating a second one.

Everything that describes the gap -- business, question text, answer, priority, 90-day phase, suggested dates,
recommendation, KPI, risk -- is copied from the source assessment on the server when the action is created;
values sent by a caller are replaced and can never be changed afterwards. Suggested dates are fixed with it: the
source assessment is frozen, so they never need recalculating.
"""

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, today

from business_health_checkup import permissions, planning
from business_health_checkup.assessments import stored_rules

ACTION = "BHC Improvement Action"
SOURCE_FIELDS = (
	"assessment",
	"question",
	"business",
	"assessment_date",
	"scoring_model",
	"scoring_model_version",
	"source_key",
	"question_code",
	"department",
	"question_text",
	"answer",
	"criticality",
	"weight",
	"gap_points",
	"gap_rank",
	"priority",
	"phase",
	"suggested_start_date",
	"suggested_due_date",
	"recommendation",
	"kpi",
	"business_risk",
)
# Taking an action out of Completed rewrites its completion record. Provisional (Q-24): BHC Manager and the
# unrestricted System Manager only; the old values stay in the version history (track_changes).
REOPEN_ROLES = frozenset({"BHC Manager"})


def source_key(assessment: str, question_code: str) -> str:
	return f"{assessment}|{question_code}"


def get_source_assessment(name: str):
	"""The finalised assessment an action may come from, readable by the current user."""
	if not name or not frappe.db.exists("BHC Assessment", name):
		frappe.throw(_("Source assessment {0} not found").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("BHC Assessment", name)
	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("Improvement actions can only be created from a finalised assessment"))
	return doc


def gap_rows(assessment) -> dict:
	"""Stored responses with a gap, by question ID, in gap rank order."""
	rows = [r for r in assessment.responses if flt(r.gap_points) > 0]
	return {r.question_code: r for r in sorted(rows, key=lambda r: (r.gap_rank or 0, r.idx or 0))}


def source_values(assessment, row, rules) -> dict:
	assessment_date = getdate(assessment.assessment_date) if assessment.assessment_date else None
	start, due = (
		planning.suggested_dates(row.priority, assessment_date, rules) if row.priority else (None, None)
	)
	return {
		"assessment": assessment.name,
		"question": row.question or row.question_code,
		"business": assessment.business,
		"assessment_date": assessment.assessment_date,
		"scoring_model": assessment.scoring_model,
		"scoring_model_version": assessment.scoring_model_version,
		"source_key": source_key(assessment.name, row.question_code),
		"question_code": row.question_code,
		"department": row.department,
		"question_text": row.question_text,
		"answer": row.answer,
		"criticality": row.criticality,
		"weight": row.weight,
		"gap_points": row.gap_points,
		"gap_rank": row.gap_rank,
		"priority": row.priority,
		"phase": rules.priority_phase.get(row.priority, "") if row.priority else "",
		"suggested_start_date": start,
		"suggested_due_date": due,
		"recommendation": row.recommendation,
		"kpi": row.kpi,
		"business_risk": row.business_risk,
	}


def fill_from_source(doc) -> None:
	"""Copy the gap from the source assessment (called before insert; caller values are replaced)."""
	assessment = get_source_assessment(doc.assessment)
	code = doc.question
	row = next((r for r in assessment.responses if r.question_code == code), None)
	if not row:
		frappe.throw(_("Question {0} is not part of assessment {1}").format(code, assessment.name))
	if flt(row.gap_points) <= 0:
		frappe.throw(_("Question {0} has no gap in assessment {1}").format(code, assessment.name))
	values = source_values(assessment, row, stored_rules(assessment))
	doc.update(values)
	# business_name is a fetch_from field, already filled from the caller's `business` by link validation.
	doc.business_name = assessment.business_name
	if not doc.action_description:
		doc.action_description = row.recommendation
	if doc.flags.use_suggested_dates:
		doc.start_date = doc.start_date or values["suggested_start_date"]
		doc.target_date = doc.target_date or values["suggested_due_date"]


def _same(a, b) -> bool:
	if isinstance(a, int | float) or isinstance(b, int | float):
		return abs(flt(a) - flt(b)) < 1e-6
	return cstr(a or "") == cstr(b or "")


def check_source_unchanged(doc) -> None:
	before = doc.get_doc_before_save()
	if not before:
		return
	for field in SOURCE_FIELDS:
		if not _same(doc.get(field), before.get(field)):
			frappe.throw(
				_("{0} comes from the source assessment and cannot be changed").format(
					_(doc.meta.get_label(field))
				)
			)


def can_reopen(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return permissions.is_unrestricted(user) or bool(REOPEN_ROLES.intersection(frappe.get_roles(user)))


def validate_plan(doc) -> None:
	"""Agreed dates, responsible user and status (the ACTION PLAN inputs)."""
	for field in ("start_date", "target_date"):
		if doc.get(field) and not planning.is_valid_plan_date(getdate(doc.get(field))):
			frappe.throw(_("{0} must be after 1 January 2000").format(_(doc.meta.get_label(field))))
	if doc.start_date and doc.target_date and getdate(doc.target_date) < getdate(doc.start_date):
		frappe.throw(_("Target Date cannot be before Start Date"))

	if doc.responsible_user:
		validate_responsible_user(doc.responsible_user, doc.business)
		if not doc.responsible:
			doc.responsible = frappe.db.get_value("User", doc.responsible_user, "full_name")

	before = None if doc.is_new() else doc.get_doc_before_save()
	previous = before.status if before else None
	if doc.status == planning.COMPLETED:
		# The completion date is the day the action became Completed; callers cannot set or move it.
		doc.completed_on = before.completed_on if previous == planning.COMPLETED else today()
	else:
		if previous == planning.COMPLETED and not can_reopen():
			frappe.throw(
				_("Only a BHC Manager or System Manager can reopen a completed action"),
				frappe.PermissionError,
			)
		doc.completed_on = None


def validate_responsible_user(user: str, business: str) -> None:
	"""A responsible user must be an enabled user who can already see the business: naming someone as responsible
	never gives them access (access comes only from the business's Assigned Users)."""
	if not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("User {0} is disabled or does not exist").format(user))
	if not permissions.has_business_access(user, business):
		frappe.throw(
			_(
				"User {0} cannot access this business. Add them to its Assigned Users first; naming them as "
				"responsible does not give access."
			).format(user)
		)


@frappe.whitelist()
def get_eligible_gaps(assessment: str) -> list[dict]:
	"""Gaps of a finalised assessment, in gap rank order, with the action already created for each (if any)."""
	doc = get_source_assessment(assessment)
	rules = stored_rules(doc)
	existing = {
		a.question_code: a
		for a in frappe.get_list(
			ACTION,
			filters={"assessment": doc.name},
			fields=["name", "question_code", "status"],
			limit_page_length=0,
		)
	}
	gaps = []
	for code, row in gap_rows(doc).items():
		values = source_values(doc, row, rules)
		action = existing.get(code)
		gaps.append(
			{
				**{
					k: values[k]
					for k in ("question_code", "department", "question_text", "answer", "criticality")
				},
				**{k: values[k] for k in ("gap_points", "gap_rank", "priority", "phase", "recommendation")},
				"suggested_start_date": values["suggested_start_date"],
				"suggested_due_date": values["suggested_due_date"],
				"action": action.name if action else None,
				"action_status": action.status if action else None,
			}
		)
	return gaps


@frappe.whitelist()
def create_actions(
	assessment: str,
	questions,
	responsible: str | None = None,
	responsible_user: str | None = None,
	use_suggested_dates: bool | int | str = 0,
) -> list[dict]:
	"""Create actions for the selected gaps of a finalised assessment; existing ones are returned, not repeated.

	Every selected question is checked before anything is written, and the inserts run inside a savepoint, so a
	failing request creates nothing and can simply be retried. `use_suggested_dates` copies the suggested dates
	into the agreed Start / Target dates only when the user asks for it.
	"""
	questions = frappe.parse_json(questions) if isinstance(questions, str) else questions
	if not isinstance(questions, list) or not questions:
		frappe.throw(_("Select at least one gap"))
	codes = list(dict.fromkeys(cstr(q) for q in questions))
	doc = get_source_assessment(assessment)
	gaps = gap_rows(doc)
	if invalid := [code for code in codes if code not in gaps]:
		frappe.throw(_("Not gaps of assessment {0}: {1}").format(doc.name, ", ".join(invalid)))
	existing = dict(
		frappe.get_all(
			ACTION,
			filters={"assessment": doc.name, "question_code": ["in", codes]},
			fields=["question_code", "name"],
			as_list=True,
		)
	)

	frappe.db.savepoint("bhc_create_actions")
	try:
		results = []
		for code in codes:
			if code in existing:
				results.append({"question_code": code, "action": existing[code], "created": False})
				continue
			action = frappe.get_doc(
				{
					"doctype": ACTION,
					"assessment": doc.name,
					"question": code,
					"responsible": responsible,
					"responsible_user": responsible_user,
				}
			)
			action.flags.use_suggested_dates = frappe.utils.sbool(use_suggested_dates)
			action.insert()
			results.append({"question_code": code, "action": action.name, "created": True})
	except Exception:
		frappe.db.rollback(save_point="bhc_create_actions")
		raise
	return results


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def gap_question_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link query for an action's Gap (Question): gaps of the chosen assessment that have no action yet."""
	assessment = (filters or {}).get("assessment")
	if not assessment:
		return []
	txt = (txt or "").lower()
	rows = [
		(g["question_code"], g["priority"], (g["question_text"] or "")[:100])
		for g in get_eligible_gaps(assessment)
		if not g["action"] and txt in f"{g['question_code']} {g['question_text']}".lower()
	]
	return rows[start : start + page_len]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def responsible_user_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link query for Responsible User: enabled users assigned to the action's business."""
	business = (filters or {}).get("business")
	if not business or not frappe.has_permission("BHC Business", "read", doc=business):
		return []
	users = frappe.get_all(
		"BHC Business User",
		filters={"parent": business, "parenttype": "BHC Business", "parentfield": "assigned_users"},
		pluck="user",
	)
	txt = (txt or "").lower()
	rows = [
		(u.name, u.full_name)
		for u in frappe.get_all(
			"User", filters={"name": ["in", users], "enabled": 1}, fields=["name", "full_name"]
		)
		if txt in f"{u.name} {u.full_name}".lower()
	]
	return rows[start : start + page_len]
