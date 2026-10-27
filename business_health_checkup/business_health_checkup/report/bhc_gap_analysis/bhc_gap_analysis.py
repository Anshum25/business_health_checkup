# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

"""GAP ANALYSIS (workbook rows 18-218 and summary B4:F4) for the assessments the user may read.

Rows are the stored responses with a gap (gap points > 0), in the stored gap rank. Question text, criticality,
weight, recommendation, KPI and risk are the assessment's own snapshot; the 90-day phase comes from the scoring
model the assessment links. Nothing is recalculated from today's masters. The last two columns show the
improvement action created for a gap, if any; a gap without one is still only a gap (Q-07).
"""

import frappe
from frappe import _

from business_health_checkup.reporting import permitted_assessments

RESPONSE_FILTERS = ("department", "criticality", "priority", "answer")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	assessments = permitted_assessments(
		filters,
		["name", "business", "business_name", "assessment_date", "status", "scoring_model", "overall_score"],
	)
	if not assessments:
		return columns, [], None, None, get_summary([], None)

	conditions = {
		"parenttype": "BHC Assessment",
		"parentfield": "responses",
		"parent": ["in", [a.name for a in assessments]],
		"gap_points": [">", 0],
	}
	conditions.update({key: filters[key] for key in RESPONSE_FILTERS if filters.get(key)})
	responses = frappe.get_all(
		"BHC Assessment Response",
		filters=conditions,
		fields=[
			"parent",
			"gap_rank",
			"department",
			"question_code",
			"question_text",
			"criticality",
			"weight",
			"answer",
			"earned_points",
			"max_points",
			"gap_points",
			"priority",
			"recommendation",
			"kpi",
			"business_risk",
		],
	)

	actions = {
		(a.assessment, a.question_code): a
		for a in frappe.get_list(
			"BHC Improvement Action",
			filters={"assessment": ["in", [a.name for a in assessments]]},
			fields=["name", "assessment", "question_code", "status"],
			limit_page_length=0,
		)
	}
	by_name = {a.name: a for a in assessments}
	position = {a.name: i for i, a in enumerate(assessments)}
	phases = {}
	data = []
	for r in sorted(responses, key=lambda r: (position[r.parent], r.gap_rank)):
		a = by_name[r.parent]
		action = actions.get((r.parent, r.question_code))
		if a.scoring_model not in phases:
			phases[a.scoring_model] = (
				frappe.get_doc("BHC Scoring Model", a.scoring_model).get_rules().priority_phase
			)
		data.append(
			{
				**r,
				"assessment": r.parent,
				"business": a.business,
				"business_name": a.business_name,
				"assessment_date": a.assessment_date,
				"status": a.status,
				"phase": phases[a.scoring_model].get(r.priority, ""),
				"improvement_action": action.name if action else None,
				"action_status": action.status if action else None,
			}
		)
	single = assessments[0] if len(assessments) == 1 else None
	return columns, data, None, get_chart(data), get_summary(data, single)


def get_columns():
	def col(fieldname, label, fieldtype="Data", width=120, options=None):
		c = {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "width": width}
		if options:
			c["options"] = options
		return c

	return [
		col("business", "Business", "Link", 140, "BHC Business"),
		col("business_name", "Company Name", width=160),
		col("assessment", "Assessment", "Link", 150, "BHC Assessment"),
		col("assessment_date", "Assessment Date", "Date", 110),
		col("status", "Status", width=90),
		col("gap_rank", "Gap No.", "Int", 70),
		col("department", "Department", "Link", 100, "BHC Department"),
		col("question_code", "Question ID", width=90),
		col("question_text", "Question", "Small Text", 320),
		col("criticality", "Criticality", width=90),
		col("weight", "Weightage", "Float", 85),
		col("answer", "Answer", width=95),
		col("earned_points", "Score (points)", "Float", 95),
		col("max_points", "Max (points)", "Float", 90),
		col("gap_points", "Gap (points)", "Float", 90),
		col("priority", "Priority", width=80),
		col("recommendation", "Recommendation", "Small Text", 320),
		col("kpi", "KPI", "Small Text", 200),
		col("business_risk", "Business Risk if Unresolved", "Small Text", 320),
		col("phase", "90-Day Phase", width=100),
		col("improvement_action", "Improvement Action", "Link", 150, "BHC Improvement Action"),
		col("action_status", "Action Status", width=95),
	]


def get_summary(data, single_assessment):
	"""GAP ANALYSIS!B4:G4: total gaps (rows with a priority), HIGH, MEDIUM, LOW, points lost, overall score."""
	priorities = [r["priority"] for r in data]
	summary = [
		{"label": _("Total Gaps"), "value": sum(1 for p in priorities if p), "datatype": "Int"},
		{"label": _("HIGH"), "value": priorities.count("HIGH"), "datatype": "Int", "indicator": "Red"},
		{"label": _("MEDIUM"), "value": priorities.count("MEDIUM"), "datatype": "Int", "indicator": "Orange"},
		{"label": _("LOW"), "value": priorities.count("LOW"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Points Lost"), "value": sum(r["gap_points"] for r in data), "datatype": "Float"},
	]
	if single_assessment:
		summary.append(
			{"label": _("Overall Score"), "value": single_assessment.overall_score, "datatype": "Percent"}
		)
	return summary


def get_chart(data):
	if not data:
		return None
	departments = list(dict.fromkeys(r["department"] for r in data))
	counts = {(r["department"], r["priority"]): 0 for r in data}
	for r in data:
		counts[(r["department"], r["priority"])] += 1
	return {
		"data": {
			"labels": departments,
			"datasets": [
				{"name": p, "values": [counts.get((d, p), 0) for d in departments]}
				for p in ("HIGH", "MEDIUM", "LOW")
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
		"colors": ["#e24c4c", "#f5a524", "#3bb273"],
	}
