# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

"""An assessment next to its linked previous assessment (assessments.get_comparison), from stored results.

The difference is in percentage points and is shown only when both sides have applicable answers. "Comparable"
is No when the scoring rules or the questions differ, or a side was not assessed; the Limitations column says
why. No row is labelled as an improvement or a decline (open question Q-11).
"""

import frappe
from frappe import _
from frappe.utils import escape_html

from business_health_checkup.assessments import get_comparison

VIEW_DEPARTMENTS = "Departments"
VIEW_QUESTIONS = "Questions"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("assessment"):
		return [], [], _("Select an assessment that has a previous assessment."), None, None
	comparison = get_comparison(filters.assessment)
	message = get_message(comparison)
	if not comparison["previous"]:
		return [], [], message, None, None
	if filters.get("view") == VIEW_QUESTIONS:
		return question_columns(), question_rows(comparison), message, None, get_summary(comparison)
	return department_columns(), department_rows(comparison), message, None, get_summary(comparison)


def _col(fieldname, label, fieldtype="Data", width=110, options=None):
	c = {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "width": width}
	if options:
		c["options"] = options
	return c


def department_columns():
	return [
		_col("department", "Department", width=90),
		_col("department_name", "Department Name", width=190),
		_col("previous_score", "Previous Score", "Percent", 110),
		_col("current_score", "Current Score", "Percent", 110),
		_col("difference", "Difference (points of %)", "Float", 150),
		_col("previous_max_points", "Previous Max", "Float", 100),
		_col("current_max_points", "Current Max", "Float", 100),
		_col("previous_coverage", "Previous Coverage", width=170),
		_col("current_coverage", "Current Coverage", width=170),
		_col("comparable", "Comparable", width=95),
		_col("limitations", "Limitations", "Small Text", 360),
	]


def department_rows(comparison):
	overall = comparison["overall"]
	rows = [{**overall, "department": "ALL", "department_name": _("Overall Business Health")}]
	rows += comparison["departments"]
	return [_present(row) for row in rows]


def question_columns():
	return [
		_col("question_code", "Question ID", width=90),
		_col("department", "Department", width=90),
		_col("question_text", "Question", "Small Text", 300),
		_col("state", "In Assessments", width=110),
		_col("snapshot_changes", "Snapshot Changes", width=170),
		_col("previous_answer", "Previous Answer", width=110),
		_col("current_answer", "Current Answer", width=110),
		_col("previous_points", "Previous Earned / Max", width=140),
		_col("current_points", "Current Earned / Max", width=140),
		_col("comparable", "Comparable", width=95),
	]


def question_rows(comparison):
	def points(earned, max_points):
		return None if max_points is None else f"{earned or 0:g} / {max_points:g}"

	rows = []
	for q in comparison["questions"]:
		rows.append(
			{
				**q,
				"snapshot_changes": ", ".join(q["snapshot_changes"]),
				"previous_points": points(q["previous_earned_points"], q["previous_max_points"]),
				"current_points": points(q["current_earned_points"], q["current_max_points"]),
				"comparable": _("Yes") if q["comparable"] else _("No"),
			}
		)
	return rows


def _present(row):
	return {
		**row,
		"comparable": _("Yes") if row["comparable"] else _("No"),
		"limitations": "; ".join(row["limitations"]),
	}


def get_summary(comparison):
	overall = comparison["overall"]
	return [
		{"label": _("Previous Score"), "value": overall["previous_score"], "datatype": "Percent"},
		{"label": _("Current Score"), "value": overall["current_score"], "datatype": "Percent"},
		{
			"label": _("Difference (points of %)"),
			"value": overall["difference"] if overall["difference"] is not None else _("n/a"),
			"datatype": "Float" if overall["difference"] is not None else "Data",
		},
		{
			"label": _("Comparable"),
			"value": _("Yes") if overall["comparable"] else _("No"),
			"datatype": "Data",
			"indicator": "Blue" if overall["comparable"] else "Orange",
		},
	]


def get_message(comparison):
	current, previous = comparison["current"], comparison["previous"]
	lines = []
	if previous:
		for label, side in ((_("Previous"), previous), (_("Current"), current)):
			lines.append(
				"{0}: {1} ({2}, {3}), {4}".format(
					label,
					escape_html(side["name"]),
					escape_html(str(side["assessment_date"])),
					escape_html(side["status"] or ""),
					escape_html(side["scoring_model_version"] or side["scoring_model"] or ""),
				)
			)
	for limitation in comparison["limitations"]:
		lines.append(escape_html(limitation))
	return "<br>".join(lines)
