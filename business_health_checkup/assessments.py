"""Assessment snapshot, scoring and comparison on top of scoring.py.

This is the only place where BHC Assessment documents meet the scoring engine. All scores are produced by
`scoring.score_assessment` from the assessment's own question snapshot (its response rows) and the rules of the
scoring model it links; nothing here re-implements a workbook formula, and nothing reads the question master
except `build_snapshot`, when an assessment is first created.
"""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime

from business_health_checkup import analysis, scoring
from business_health_checkup.business_health_checkup.doctype.bhc_scoring_model.bhc_scoring_model import (
	get_default_scoring_model,
)

# Response fields copied from the master when an assessment is created; they never change afterwards.
SNAPSHOT_FIELDS = (
	"idx",
	"question",
	"question_code",
	"department",
	"seq",
	"sub_category",
	"question_text",
	"criticality",
	"weight",
	"recommendation",
	"kpi",
	"business_risk",
)
INPUT_FIELDS = ("answer", "evidence")
# Stored results are DECIMAL(21,9); recomputed floats agree to well within this.
TOLERANCE = 1e-6


def get_scoring_model(name: str):
	model = frappe.get_doc("BHC Scoring Model", name)
	if model.docstatus != 1:
		frappe.throw(_("Scoring Model {0} is not submitted").format(name))
	return model


def ensure_scoring_model(doc) -> None:
	if not doc.scoring_model:
		doc.scoring_model = get_default_scoring_model()
	if not doc.scoring_model:
		frappe.throw(_("No default Scoring Model; submit one and mark it as default"))


def build_snapshot(doc) -> None:
	"""Fill `doc.responses` with every active question, in department and question order.

	Answers and evidence already on the document (an API call creating an assessment with answers) are kept by
	question ID; every other value comes from the master and the scoring model, never from the caller.
	"""
	rules = get_scoring_model(doc.scoring_model).get_rules()
	provided = {}
	for row in doc.get("responses") or []:
		code = row.question_code or row.question
		if not code or code in provided:
			frappe.throw(_("Each response must name a different question"))
		provided[code] = row

	order = dict(frappe.get_all("BHC Department", fields=["name", "display_order"], as_list=True))
	questions = frappe.get_all(
		"BHC Question",
		filters={"is_active": 1},
		fields=[
			"name",
			"department",
			"seq",
			"sub_category",
			"question",
			"criticality",
			"recommendation",
			"kpi",
			"business_risk",
		],
	)
	if not questions:
		frappe.throw(_("There are no active questions to assess"))
	questions.sort(key=lambda q: (order.get(q.department, 0), q.seq, q.name))
	if unknown := set(provided) - {q.name for q in questions}:
		frappe.throw(_("Unknown or inactive questions: {0}").format(", ".join(sorted(unknown))))

	doc.set("responses", [])
	for q in questions:
		if q.criticality not in rules.criticality_weight:
			frappe.throw(_("Question {0} has a criticality the scoring model does not know").format(q.name))
		given = provided.get(q.name)
		doc.append(
			"responses",
			{
				"question": q.name,
				"question_code": q.name,
				"department": q.department,
				"seq": q.seq,
				"sub_category": q.sub_category,
				"question_text": q.question,
				"criticality": q.criticality,
				"weight": rules.criticality_weight[q.criticality],
				"recommendation": q.recommendation,
				"kpi": q.kpi,
				"business_risk": q.business_risk,
				"answer": given.answer if given else None,
				"evidence": given.evidence if given else None,
			},
		)


def check_snapshot_unchanged(doc) -> None:
	"""Refuse any change to the question snapshot: rows added, removed, reordered or edited."""
	before = doc.get_doc_before_save()
	if not before:
		return
	old = {row.name: row for row in before.responses}
	new = {row.name: row for row in doc.responses}
	if set(old) != set(new):
		frappe.throw(_("Questions cannot be added to or removed from an assessment"))
	for name, row in new.items():
		for field in SNAPSHOT_FIELDS:
			if _differs(row.get(field), old[name].get(field)):
				frappe.throw(
					_("Question {0}: {1} is part of the assessment snapshot and cannot be changed").format(
						old[name].question_code, field
					)
				)


def check_amendment_snapshot(doc) -> None:
	"""An amendment corrects the same assessment: same scoring model, same questions as asked."""
	original = frappe.get_doc("BHC Assessment", doc.amended_from)
	if doc.scoring_model != original.scoring_model or doc.business != original.business:
		frappe.throw(_("An amendment must keep the business and scoring model of {0}").format(original.name))
	rows = sorted(doc.responses, key=lambda r: r.idx or 0)
	if len(rows) != len(original.responses):
		frappe.throw(_("An amendment must keep the questions of {0}").format(original.name))
	for row, old in zip(rows, original.responses, strict=True):
		for field in SNAPSHOT_FIELDS:
			if field != "idx" and _differs(row.get(field), old.get(field)):
				frappe.throw(_("An amendment must keep the questions of {0}").format(original.name))


def _differs(a, b) -> bool:
	if isinstance(a, int | float) or isinstance(b, int | float):
		return abs(flt(a) - flt(b)) > TOLERANCE
	return (a or None) != (b or None)


def compute(doc, model=None):
	"""Score the stored snapshot with the linked scoring model. Pure: `doc` is not changed."""
	model = model or get_scoring_model(doc.scoring_model)
	rules = model.get_rules()
	rows = sorted(doc.responses, key=lambda r: r.idx or 0)
	codes = [row.question_code for row in rows]
	if len(set(codes)) != len(codes):
		frappe.throw(_("The assessment lists a question more than once"))
	for row in rows:
		if abs(flt(row.weight) - rules.criticality_weight.get(row.criticality, -1)) > TOLERANCE:
			frappe.throw(
				_("Question {0}: stored weight does not match scoring model {1}").format(
					row.question_code, model.name
				)
			)
	questions = [scoring.Question(row.question_code, row.department, row.criticality) for row in rows]
	try:
		result = scoring.score_assessment(questions, {row.question_code: row.answer for row in rows}, rules)
	except ValueError as e:
		frappe.throw(str(e), title=_("Invalid Answer"))
	ranks = {r.question_id: i for i, r in enumerate(scoring.rank_gaps(result.questions, rules), 1)}
	return model, rules, rows, result, ranks


def calculate(doc) -> None:
	"""Write the engine's results onto a draft assessment (called from validate)."""
	model, rules, rows, result, ranks = compute(doc)
	for row, r in zip(rows, result.questions, strict=True):
		row.update(_question_values(r, ranks))
	doc.set(
		"department_results", [_department_values(code, s, rules) for code, s in result.departments.items()]
	)
	doc.update(_overall_values(result.overall))
	doc.scoring_model_version = model.version_label
	doc.rules_hash = model.rules_hash
	doc.calculated_on = now_datetime()
	doc.suggested_reassessment_date = add_days(doc.assessment_date, 90) if doc.assessment_date else None


def _question_values(r, ranks) -> dict:
	return {
		"earned_points": r.earned,
		"max_points": r.max_points,
		"gap_points": r.gap,
		"priority": r.priority or "",
		"gap_rank": ranks.get(r.question_id, 0),
	}


def _department_values(code, s, rules) -> dict:
	return {
		"department": code,
		"department_name": frappe.get_cached_value("BHC Department", code, "department_name"),
		"questions": s.questions,
		"answered": s.answered,
		"completion_percent": s.completion * 100,
		"earned_points": s.earned,
		"max_points": s.max_points,
		"score_percent": s.score * 100,
		"maturity": s.maturity,
		"assessed": int(s.assessed),
		"high_gaps": s.high,
		"medium_gaps": s.medium,
		"low_gaps": s.low,
		"total_gaps": s.total_gaps,
		"growth_status": scoring.growth_status(s.score, rules),
	}


def _overall_values(s) -> dict:
	return {
		"total_questions": s.questions,
		"answered_questions": s.answered,
		"completion_percent": s.completion * 100,
		"earned_points": s.earned,
		"max_points": s.max_points,
		"overall_score": s.score * 100,
		"overall_maturity": s.maturity,
		"high_gaps": s.high,
		"medium_gaps": s.medium,
		"low_gaps": s.low,
		"total_gaps": s.total_gaps,
	}


def stored_result_differences(doc) -> list[str]:
	"""Re-run the engine on the stored snapshot and list every stored figure that disagrees (read-only)."""
	model, rules, rows, result, ranks = compute(doc)
	differences = []

	def check(label, stored, expected):
		if _differs(stored, expected):
			differences.append(f"{label}: stored {stored!r}, recomputed {expected!r}")

	if doc.rules_hash != model.rules_hash:
		differences.append(f"rules_hash: stored {doc.rules_hash!r}, model {model.rules_hash!r}")
	for row, r in zip(rows, result.questions, strict=True):
		for field, value in _question_values(r, ranks).items():
			check(f"{row.question_code} {field}", row.get(field), value)
	stored = {row.department: row for row in doc.department_results}
	if list(stored) != list(result.departments):
		differences.append("department results do not list the assessed departments")
	for code, s in result.departments.items():
		for field, value in _department_values(code, s, rules).items():
			if field not in ("department", "department_name") and code in stored:
				check(f"{code} {field}", stored[code].get(field), value)
	for field, value in _overall_values(result.overall).items():
		check(field, doc.get(field), value)
	return differences


def validate_previous_assessment(doc) -> None:
	if not doc.previous_assessment:
		return
	if doc.previous_assessment in (doc.name, doc.amended_from):
		frappe.throw(_("An assessment cannot be its own previous assessment"))
	prev = frappe.db.get_value(
		"BHC Assessment",
		doc.previous_assessment,
		["business", "docstatus", "assessment_date"],
		as_dict=True,
	)
	if not prev or prev.business != doc.business:
		frappe.throw(_("The previous assessment must belong to the same business"))
	if prev.docstatus != 1:
		frappe.throw(_("The previous assessment must be finalised"))
	if doc.assessment_date and getdate(prev.assessment_date) > getdate(doc.assessment_date):
		frappe.throw(_("The previous assessment cannot be dated after this one"))


def next_sequence_no(business: str) -> int:
	last = frappe.db.sql("select max(sequence_no) from `tabBHC Assessment` where business = %s", business)[0][
		0
	]
	return (last or 0) + 1


@frappe.whitelist()
def make_reassessment(source_name: str):
	"""A new draft assessment of the same business, linked to a finalised one. Nothing is copied but the business:
	the new assessment gets its own date, current questions, default scoring model and blank answers."""
	source = frappe.get_doc("BHC Assessment", source_name)
	source.check_permission("read")
	if source.docstatus != 1:
		frappe.throw(_("Only a finalised assessment can be re-assessed"))
	doc = frappe.new_doc("BHC Assessment")
	doc.business = source.business
	doc.previous_assessment = source.name
	doc.consultant = frappe.session.user
	doc.scoring_model = get_default_scoring_model()
	doc.check_permission("create")
	return doc


@frappe.whitelist()
def verify_results(name: str) -> dict:
	"""Whether the stored results are exactly what the engine gives for the stored snapshot and model."""
	doc = frappe.get_doc("BHC Assessment", name)
	doc.check_permission("read")
	differences = stored_result_differences(doc)
	return {"matches": not differences, "differences": differences}


def stored_rules(doc) -> scoring.Rules:
	"""Rules of the scoring model an assessment links, as stored (whatever its docstatus is now)."""
	return frappe.get_doc("BHC Scoring Model", doc.scoring_model).get_rules()


def department_rows(doc) -> list[dict]:
	"""Stored department results with the workbook rank, coverage and N/A counts. Read-only: every figure comes
	from the stored results and answers; the rank is SCORE CALCULATION!U5 applied to the stored scores in the
	stored department order."""
	excluded = stored_rules(doc).excluded_answers
	answers = sorted(doc.responses, key=lambda r: r.idx or 0)
	not_applicable = Counter(r.department for r in answers if r.answer in excluded)
	results = sorted(doc.department_results, key=lambda r: r.idx or 0)
	ranks = scoring.rank_departments([(r.department, flt(r.score_percent) / 100) for r in results])
	rows = []
	for r in results:
		na = not_applicable.get(r.department, 0)
		rows.append(
			{
				"department": r.department,
				"department_name": r.department_name,
				"workbook_rank": ranks[r.department],
				"coverage": analysis.coverage_state(r.questions, r.answered, na),
				"questions": r.questions,
				"answered": r.answered,
				"not_applicable": na,
				"applicable": r.answered - na,
				"unanswered": r.questions - r.answered,
				"completion_percent": r.completion_percent,
				"earned_points": r.earned_points,
				"max_points": r.max_points,
				"score_percent": r.score_percent,
				"maturity": r.maturity,
				"assessed": bool(r.assessed),
				"high_gaps": r.high_gaps,
				"medium_gaps": r.medium_gaps,
				"low_gaps": r.low_gaps,
				"total_gaps": r.total_gaps,
				"growth_status": r.growth_status,
				"repeated_problem_area": scoring.repeated_problem_area(r.high_gaps, r.total_gaps),
			}
		)
	return rows


def assessment_view(doc) -> dict:
	"""Stored results of one assessment in the plain layout analysis.compare expects."""
	departments = department_rows(doc)
	return {
		"name": doc.name,
		"assessment_date": str(doc.assessment_date) if doc.assessment_date else None,
		"status": doc.status,
		"scoring_model": doc.scoring_model,
		"scoring_model_version": doc.scoring_model_version,
		"rules_hash": doc.rules_hash,
		"overall_score": doc.overall_score,
		"earned_points": doc.earned_points,
		"max_points": doc.max_points,
		"questions": doc.total_questions,
		"answered": doc.answered_questions,
		"not_applicable": sum(d["not_applicable"] for d in departments),
		"departments": departments,
		"responses": [
			{
				"question_code": r.question_code,
				"department": r.department,
				"question_text": r.question_text,
				"criticality": r.criticality,
				"weight": r.weight,
				"answer": r.answer or None,
				"earned_points": r.earned_points,
				"max_points": r.max_points,
			}
			for r in sorted(doc.responses, key=lambda r: r.idx or 0)
		],
	}


@frappe.whitelist()
def get_results_summary(name: str) -> dict:
	"""Everything the assessment form's Results Summary shows, from stored values only."""
	doc = frappe.get_doc("BHC Assessment", name)
	doc.check_permission("read")
	departments = department_rows(doc)
	previous = None
	if doc.previous_assessment and frappe.has_permission(
		"BHC Assessment", "read", doc=doc.previous_assessment
	):
		previous = frappe.db.get_value(
			"BHC Assessment",
			doc.previous_assessment,
			["name", "assessment_date", "status", "overall_score", "overall_maturity"],
			as_dict=True,
		)
	return {
		"name": doc.name,
		"status": doc.status,
		"overall_score": doc.overall_score,
		"overall_maturity": doc.overall_maturity,
		"coverage": analysis.coverage_state(
			doc.total_questions, doc.answered_questions, sum(d["not_applicable"] for d in departments)
		),
		"questions": doc.total_questions,
		"answered": doc.answered_questions,
		"not_applicable": sum(d["not_applicable"] for d in departments),
		"unanswered": doc.total_questions - doc.answered_questions,
		"high_gaps": doc.high_gaps,
		"medium_gaps": doc.medium_gaps,
		"low_gaps": doc.low_gaps,
		"total_gaps": doc.total_gaps,
		"scoring_model_version": doc.scoring_model_version,
		"departments": departments,
		"previous": previous,
		"reassessments": frappe.get_list(
			"BHC Assessment",
			filters={"previous_assessment": doc.name},
			fields=["name", "assessment_date", "status", "overall_score"],
			order_by="assessment_date asc",
		),
		"actions": action_counts(doc),
	}


def action_counts(doc) -> dict:
	"""Improvement actions created for this assessment's gaps, by status (stored values only)."""
	statuses = frappe.get_list(
		"BHC Improvement Action", filters={"assessment": doc.name}, pluck="status", limit_page_length=0
	)
	return {
		"gaps": sum(1 for r in doc.responses if flt(r.gap_points) > 0),
		"total": len(statuses),
		"by_status": dict(Counter(statuses)),
	}


@frappe.whitelist()
def get_comparison(name: str) -> dict:
	"""Stored results of an assessment compared with its linked previous assessment (analysis.compare).

	Read-only: neither assessment is changed, and the previous one is never re-scored with today's masters or with
	the current assessment's scoring model.
	"""
	doc = frappe.get_doc("BHC Assessment", name)
	doc.check_permission("read")
	if not doc.previous_assessment:
		current = assessment_view(doc)
		return {
			"previous": None,
			"current": {
				k: current[k] for k in ("name", "assessment_date", "status", "scoring_model_version")
			},
			"limitations": [_("No previous assessment is linked")],
			"overall": None,
			"departments": [],
			"questions": [],
		}
	prev = frappe.get_doc("BHC Assessment", doc.previous_assessment)
	prev.check_permission("read")
	return analysis.compare(assessment_view(prev), assessment_view(doc))
