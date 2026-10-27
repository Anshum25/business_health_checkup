# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

"""90 DAY PLAN (and the ACTION PLAN!A4:G4 counters) for the improvement actions the user may read.

Rows are BHC Improvement Actions, in the workbook's order: by source assessment, then gap rank (HIGH, MEDIUM, LOW
phase, then points lost). Phase and suggested dates are the ones copied from the source assessment and its
scoring model. Unlike the workbook's Start / Due columns, which show the agreed date or else the suggested one,
suggested and agreed dates are separate columns here, and only an agreed Target Date can make an action overdue
(ACTION PLAN!Q8).
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from business_health_checkup import planning

ACTION = "BHC Improvement Action"
EQUAL_FILTERS = ("business", "assessment", "department", "priority", "phase", "responsible_user", "status")
FIELDS = [
	"name",
	"business",
	"business_name",
	"assessment",
	"assessment_date",
	"gap_rank",
	"phase",
	"priority",
	"department",
	"question_code",
	"question_text",
	"action_description",
	"responsible",
	"responsible_user",
	"suggested_start_date",
	"suggested_due_date",
	"start_date",
	"target_date",
	"status",
	"completed_on",
	"kpi",
	"target_measure",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.get("status") and filters.status not in planning.STATUSES:
		frappe.throw(_("Unknown status filter"))
	conditions = [[field, "=", filters[field]] for field in EQUAL_FILTERS if filters.get(field)]
	if filters.get("responsible"):
		conditions.append(["responsible", "like", f"%{filters.responsible}%"])
	if filters.get("target_from") or filters.get("target_to"):
		# A date range only selects actions with an agreed target date (Frappe would otherwise compare a blank
		# date as the lowest possible date and list unscheduled actions under "Target Date To").
		conditions.append(["target_date", "is", "set"])
	if filters.get("target_from"):
		conditions.append(["target_date", ">=", filters.target_from])
	if filters.get("target_to"):
		conditions.append(["target_date", "<=", filters.target_to])

	# frappe.get_list applies the Assigned Users rule (permissions.action_query_conditions).
	actions = frappe.get_list(ACTION, filters=conditions, fields=FIELDS, limit_page_length=0)
	source_status = dict(
		frappe.get_list(
			"BHC Assessment",
			filters={"name": ["in", list({a.assessment for a in actions})]},
			fields=["name", "status"],
			as_list=True,
			limit_page_length=0,
		)
		if actions
		else []
	)
	today = getdate(nowdate())
	data = []
	for a in sorted(actions, key=lambda a: (-ordinal(a.assessment_date), a.assessment, a.gap_rank or 0)):
		target = getdate(a.target_date) if a.target_date else None
		overdue = planning.is_overdue(a.status, target, today)
		if filters.get("overdue_only") and not overdue:
			continue
		data.append(
			{
				**a,
				"action": a.name,
				"source_status": source_status.get(a.assessment),
				"overdue": _("Yes") if overdue else "",
			}
		)
	return get_columns(), data, None, get_chart(data), get_summary(data, today, filters)


def ordinal(value):
	return getdate(value).toordinal() if value else 0


def get_columns():
	def col(fieldname, label, fieldtype="Data", width=110, options=None):
		c = {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "width": width}
		if options:
			c["options"] = options
		return c

	return [
		col("business", "Business", "Link", 130, "BHC Business"),
		col("business_name", "Company Name", width=150),
		col("assessment", "Assessment", "Link", 150, "BHC Assessment"),
		col("assessment_date", "Assessment Date", "Date", 105),
		col("source_status", "Assessment Status", width=95),
		col("action", "Action", "Link", 150, ACTION),
		col("phase", "90-Day Phase (suggested)", width=120),
		col("priority", "Priority", width=80),
		col("gap_rank", "Gap No.", "Int", 65),
		col("department", "Department", "Link", 95, "BHC Department"),
		col("question_code", "Question ID", width=90),
		col("question_text", "Gap (Question)", "Small Text", 260),
		col("action_description", "Agreed Action", "Small Text", 280),
		col("responsible", "Responsible", width=130),
		col("responsible_user", "Responsible User", "Link", 140, "User"),
		col("suggested_start_date", "Suggested Start", "Date", 105),
		col("suggested_due_date", "Suggested Due", "Date", 105),
		col("start_date", "Start Date (agreed)", "Date", 115),
		col("target_date", "Target Date (agreed)", "Date", 120),
		col("status", "Status", width=95),
		col("completed_on", "Completed On", "Date", 105),
		col("overdue", "Overdue?", width=80),
		col("kpi", "KPI", "Small Text", 180),
		col("target_measure", "Target / Measure", "Small Text", 180),
	]


def get_summary(data, today, filters):
	"""ACTION PLAN!A4:G4 over the rows shown, plus actions without an agreed target date."""
	counters = planning.action_counters(
		[(r["status"], getdate(r["target_date"]) if r["target_date"] else None) for r in data], today
	)
	summary = [
		{"label": _("Total Actions"), "value": counters["total"], "datatype": "Int"},
		{"label": _("Open"), "value": counters["open"], "datatype": "Int", "indicator": "Red"},
		{
			"label": _("In Progress"),
			"value": counters["in_progress"],
			"datatype": "Int",
			"indicator": "Orange",
		},
		{"label": _("Completed"), "value": counters["completed"], "datatype": "Int", "indicator": "Green"},
		{"label": _("On Hold"), "value": counters["hold"], "datatype": "Int", "indicator": "Gray"},
		{"label": _("Overdue"), "value": counters["overdue"], "datatype": "Int", "indicator": "Red"},
		{"label": _("Completion %"), "value": counters["completion"] * 100, "datatype": "Percent"},
		{
			"label": _("No Agreed Target Date"),
			"value": sum(1 for r in data if not r["target_date"]),
			"datatype": "Int",
		},
	]
	if filters.get("assessment") and frappe.get_list(
		"BHC Assessment", filters={"name": filters.assessment, "docstatus": 1}, pluck="name"
	):
		gaps = frappe.get_all(
			"BHC Assessment Response",
			filters={
				"parent": filters.assessment,
				"parenttype": "BHC Assessment",
				"parentfield": "responses",
				"gap_points": [">", 0],
			},
			pluck="question_code",
		)
		with_action = set(
			frappe.get_list(ACTION, filters={"assessment": filters.assessment}, pluck="question_code")
		)
		summary.append(
			{
				"label": _("Gaps Without an Action"),
				"value": sum(1 for code in gaps if code not in with_action),
				"datatype": "Int",
			}
		)
	return summary


def get_chart(data):
	if not data:
		return None
	phases = list(dict.fromkeys(r["phase"] or _("No phase") for r in data))
	counts = {}
	for r in data:
		key = (r["phase"] or _("No phase"), r["status"])
		counts[key] = counts.get(key, 0) + 1
	return {
		"data": {
			"labels": phases,
			"datasets": [
				{"name": status, "values": [counts.get((phase, status), 0) for phase in phases]}
				for status in planning.STATUSES
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
		"colors": ["#e24c4c", "#f5a524", "#3bb273", "#a0a0a0"],
	}
