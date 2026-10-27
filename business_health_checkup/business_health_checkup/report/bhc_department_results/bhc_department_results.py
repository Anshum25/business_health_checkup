# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

"""Department results of the assessments the user may read (SCORE CALCULATION!A5:U14, GAP ANALYSIS rows 7-16,
BUSINESS GROWTH PLAN!A8:E17), from stored results only.

"Rank (workbook)" is SCORE CALCULATION!U5: 1 = weakest, and a department with no applicable answer takes part
with its score of 0, exactly as in the workbook. Whether it should (Q-04) is open, so the Coverage column says
whether a department was assessed at all; a stored 0 % next to "Not assessed" is not a measured score.
"""

import frappe
from frappe import _

from business_health_checkup.analysis import COVERAGE_STATES
from business_health_checkup.assessments import department_rows
from business_health_checkup.reporting import permitted_assessments

SORT_BY_RANK = "Rank (weakest first)"
SORT_BY_DEPARTMENT = "Department order"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.get("coverage") and filters.coverage not in COVERAGE_STATES:
		frappe.throw(_("Unknown coverage filter"))
	assessments = permitted_assessments(
		filters, ["name", "business", "business_name", "assessment_date", "status"]
	)
	data = []
	for a in assessments:
		rows = department_rows(frappe.get_doc("BHC Assessment", a.name))
		if filters.get("sort_by", SORT_BY_RANK) == SORT_BY_RANK:
			rows.sort(key=lambda r: r["workbook_rank"])
		for row in rows:
			if filters.get("department") and row["department"] != filters.department:
				continue
			if filters.get("coverage") and row["coverage"] != filters.coverage:
				continue
			data.append(
				{
					**row,
					**{k: a[k] for k in ("business", "business_name", "assessment_date", "status")},
					"assessment": a.name,
				}
			)
	return get_columns(), data, None, None, get_summary(data, len(assessments))


def get_columns():
	def col(fieldname, label, fieldtype="Data", width=100, options=None):
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
		col("workbook_rank", "Rank (workbook)", "Int", 90),
		col("department", "Department", "Link", 90, "BHC Department"),
		col("department_name", "Department Name", width=190),
		col("coverage", "Coverage", width=170),
		col("questions", "Questions", "Int", 80),
		col("answered", "Answered", "Int", 80),
		col("not_applicable", "N/A", "Int", 60),
		col("unanswered", "Unanswered", "Int", 90),
		col("completion_percent", "Completion %", "Percent", 100),
		col("earned_points", "Earned", "Float", 80),
		col("max_points", "Max (applicable)", "Float", 110),
		col("score_percent", "Score", "Percent", 90),
		col("maturity", "Maturity Level", width=200),
		col("high_gaps", "HIGH", "Int", 60),
		col("medium_gaps", "MEDIUM", "Int", 75),
		col("low_gaps", "LOW", "Int", 60),
		col("total_gaps", "Total Gaps", "Int", 85),
		col("growth_status", "Growth Plan Status (workbook)", width=200),
		col("repeated_problem_area", "Repeated Problem Area?", width=230),
	]


def get_summary(data, assessment_count):
	assessed = sum(1 for r in data if r["assessed"])
	return [
		{"label": _("Assessments"), "value": assessment_count, "datatype": "Int"},
		{"label": _("Department Rows"), "value": len(data), "datatype": "Int"},
		{"label": _("Assessed"), "value": assessed, "datatype": "Int", "indicator": "Blue"},
		{"label": _("Not Assessed"), "value": len(data) - assessed, "datatype": "Int", "indicator": "Gray"},
	]
