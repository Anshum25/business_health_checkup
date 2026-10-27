"""The workbook's MANAGEMENT REPORT and OWNER DASHBOARD, built from stored results only.

Nothing here scores anything: figures come from the assessment's stored results and snapshot, the department
rows of assessments.department_rows (workbook rank, coverage), assessments.get_comparison (previous / change),
the improvement actions and planning.py. Opening the report or the dashboard writes nothing.

Both entry points check that the current user may read the assessment, so every route that renders them --
print view, PDF, a document share key, a direct API call -- is held to the Assigned Users rule.

Cell references: docs/workbook_audit.md §11. The section limits are the workbook's (open question Q-15).
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import flt, getdate

from business_health_checkup import charts, planning
from business_health_checkup.assessments import department_rows, get_comparison, stored_rules

ACTION = "BHC Improvement Action"
# MANAGEMENT REPORT limits, as written in its formulas (Q-15)
STRENGTHS = 3  # B45:B47 = ranks 10, 9, 8 of 10 departments
PRIORITY_AREAS = 3  # B64:B66 = ranks 1, 2, 3
TOP_GAPS = 10  # A51:A60
TOP_ACTIONS = 15  # A70:A84
ROADMAP_RANKS = 5  # B101:B105 = ranks 1-5 below the growth threshold
ROADMAP_STEPS = 3  # D101 "first three steps"
# Score colours by maturity band, lowest first (INSTRUCTIONS!C18, OWNER DASHBOARD!A20).
BAND_COLORS = ("#f8696b", "#ffb366", "#ffe066", "#a9d18e", "#63be7b")
NOT_ASSESSED_COLOR = "#e5e7eb"
KPI_NOT_AVAILABLE = "The Owner's 10-number KPIs are not recorded in the system yet (open question Q-10)."


def load_assessment(name: str):
	if not name or not frappe.db.exists("BHC Assessment", name):
		frappe.throw(_("Assessment {0} not found").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("BHC Assessment", name)
	doc.check_permission("read")
	return doc


def percent_text(value) -> str:
	"""Excel TEXT(x, "0%") of a stored percentage (half away from zero)."""
	return f"{Decimal(str(flt(value))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)}%"


def change_text(points) -> str:
	"""Excel TEXT(x, "+0%;-0%;0%") of a difference in percentage points."""
	rounded = Decimal(str(flt(points))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
	return f"+{rounded}" if rounded > 0 else f"{rounded}"


def _bands(model):
	bands = sorted(model.maturity_bands, key=lambda b: flt(b.lower_bound))
	return [(flt(b.lower_bound), b.label, b.short_label or b.label) for b in bands]


def _band_index(score_percent, bands) -> int:
	fraction = flt(score_percent) / 100
	return max((i for i, (lower, _label, _short) in enumerate(bands) if fraction >= lower), default=0)


def _color(row_assessed, score_percent, bands) -> str:
	if not row_assessed:
		return NOT_ASSESSED_COLOR
	return BAND_COLORS[min(_band_index(score_percent, bands), len(BAND_COLORS) - 1)]


def _department_meta(codes) -> dict:
	"""Chart label, business risk and growth recommendations from the BHC Department master (current values;
	the assessment does not keep a copy of them, Q-27)."""
	meta = {
		d.name: {"label": d.chart_label or d.department_name, "business_risk": d.business_risk, "steps": []}
		for d in frappe.get_all(
			"BHC Department",
			filters={"name": ["in", codes]},
			fields=["name", "department_name", "chart_label", "business_risk"],
		)
	}
	for rec in frappe.get_all(
		"BHC Growth Recommendation",
		filters={"parenttype": "BHC Department", "parent": ["in", codes]},
		fields=["parent", "seq", "recommendation"],
		order_by="seq asc",
	):
		meta[rec.parent]["steps"].append(rec.recommendation)
	return meta


def _context(doc):
	"""What both views share: department rows, comparison, scoring model bands, actions, department meta."""
	model = frappe.get_doc("BHC Scoring Model", doc.scoring_model)
	rules = stored_rules(doc)
	bands = _bands(model)
	departments = department_rows(doc)
	meta = _department_meta([d["department"] for d in departments])
	comparison = get_comparison(doc.name)
	previous = {d["department"]: d for d in comparison["departments"]}
	actions = frappe.get_list(
		ACTION,
		filters={"assessment": doc.name},
		fields=["name", "question_code", "action_description", "responsible", "target_date", "status"],
		limit_page_length=0,
	)
	short = {label: short_label for _lower, label, short_label in bands}
	for d in departments:
		p = previous.get(d["department"], {})
		d["label"] = meta.get(d["department"], {}).get("label") or d["department_name"]
		d["short_maturity"] = short.get(d["maturity"], d["maturity"]) if d["assessed"] else None
		d["previous_score"] = p.get("previous_score")
		d["difference"] = p.get("difference")
		d["comparable"] = p.get("comparable")
		d["color"] = _color(d["assessed"], d["score_percent"], bands)
		d["score_text"] = percent_text(d["score_percent"])
		d["previous_text"] = percent_text(d["previous_score"]) if d["previous_score"] is not None else ""
		d["change_text"] = change_text(d["difference"]) if d["difference"] is not None else ""
	return {
		"model": model,
		"rules": rules,
		"bands": bands,
		"departments": departments,
		"meta": meta,
		"comparison": comparison,
		"actions": actions,
	}


def _header(doc, business) -> dict:
	consultant = frappe.db.get_value("User", doc.consultant, "full_name") if doc.consultant else None
	return {
		"assessment": doc.name,
		"assessment_label": doc.assessment_label,
		"assessment_date": doc.assessment_date,
		"assessment_date_text": getdate(doc.assessment_date).strftime("%d %B %Y")
		if doc.assessment_date
		else "",
		"status": doc.status,
		"docstatus": doc.docstatus,
		"scoring_model_version": doc.scoring_model_version,
		"company": business.business_name,
		"industry": business.industry,
		"consultant": consultant,
		"consultancy_firm": business.consultancy_firm,
	}


def _change_sentence(doc, comparison) -> str:
	"""MANAGEMENT REPORT!B13 second part."""
	if not comparison["previous"]:
		if doc.sequence_no == 1:
			return _("This is the baseline assessment.")
		return _("No previous assessment is linked to this assessment.")
	overall = comparison["overall"]
	if overall["difference"] is None:
		return _(
			"Change since previous assessment: not available (one of the two has no applicable answers)."
		)
	sentence = _("Change since previous assessment: {0} percentage points.").format(
		change_text(overall["difference"])
	)
	if not overall["comparable"]:
		sentence += " " + _("Not directly comparable: {0}.").format("; ".join(overall["limitations"]))
	return sentence


def _department_chart_items(departments):
	return [(d["label"], d["score_percent"], d["assessed"]) for d in departments]


@frappe.whitelist()
def get_management_report(name: str) -> dict:
	"""MANAGEMENT REPORT sections 1-10 for one assessment (docs/workbook_audit.md §11.2)."""
	doc = load_assessment(name)
	business = frappe.get_doc("BHC Business", doc.business)
	ctx = _context(doc)
	departments, rules, meta = ctx["departments"], ctx["rules"], ctx["meta"]
	by_rank = sorted(departments, key=lambda d: d["workbook_rank"])
	header = _header(doc, business)

	responses = sorted(doc.responses, key=lambda r: r.idx or 0)
	gaps = sorted((r for r in responses if flt(r.gap_points) > 0), key=lambda r: r.gap_rank or 0)
	actions = {a.question_code: a for a in ctx["actions"]}
	assessment_date = getdate(doc.assessment_date) if doc.assessment_date else None
	names = {d["department"]: d["department_name"] for d in departments}

	action_plan = []
	for r in gaps[:TOP_ACTIONS]:
		action = actions.get(r.question_code)
		_start, suggested_due = (
			planning.suggested_dates(r.priority, assessment_date, rules) if r.priority else (None, None)
		)
		agreed_due = getdate(action.target_date) if action and action.target_date else None
		action_plan.append(
			{
				"no": r.gap_rank,
				"department": names.get(r.department, r.department),
				"question_code": r.question_code,
				"recommendation": r.recommendation,
				"phase": rules.priority_phase.get(r.priority, "") if r.priority else "",
				"action": action.name if action else None,
				"agreed_action": action.action_description if action else None,
				"action_status": action.status if action else None,
				# G70: the responsible person, "(to be assigned)" when blank
				"responsible": (
					action.responsible if action and action.responsible else _("(to be assigned)")
				),
				# H70: the agreed target date, else the suggested due date
				"due_date": agreed_due or suggested_due,
				"due_date_text": (agreed_due or suggested_due).strftime("%d-%b-%Y")
				if (agreed_due or suggested_due)
				else "",
				"due_is_agreed": bool(agreed_due),
			}
		)

	critical = [r for r in responses if r.criticality == "Critical"]
	threshold = rules.growth_plan_threshold
	below = [d for d in departments if threshold is not None and flt(d["score_percent"]) / 100 < threshold]
	roadmap = [
		{**d, "steps": meta.get(d["department"], {}).get("steps", [])[:ROADMAP_STEPS]}
		for d in by_rank[:ROADMAP_RANKS]
		if threshold is not None and flt(d["score_percent"]) / 100 < threshold
	]
	reassess = getdate(doc.suggested_reassessment_date) if doc.suggested_reassessment_date else None

	return {
		"header": header,
		"profile": {
			"company": business.business_name,
			"contact": business.contact_person
			+ (f" ({business.designation})" if business.designation else "")
			if business.contact_person
			else "",
			"industry": business.industry,
			"location": business.location,
			"employees": business.number_of_employees,
			"annual_turnover_lakh": business.annual_turnover_lakh,
		},
		"overall": {
			"score": doc.overall_score,
			"score_text": percent_text(doc.overall_score),
			"maturity": doc.overall_maturity,
			"answered": f"{doc.answered_questions} / {doc.total_questions}",
			"gaps": f"{doc.high_gaps} / {doc.medium_gaps} / {doc.low_gaps}",
			"position": _("Current position: {0} scores {1} - maturity level {2}.").format(
				business.business_name, percent_text(doc.overall_score), doc.overall_maturity
			)
			+ " "
			+ _change_sentence(doc, ctx["comparison"]),
		},
		"departments": departments,
		"strengths": list(reversed(by_rank[-STRENGTHS:])),
		"critical_practices": _("Critical-weight practices fully in place: {0} of {1} answered").format(
			sum(1 for r in critical if r.answer == "YES"), sum(1 for r in critical if r.answer)
		),
		"critical_gaps": [
			{
				"no": r.gap_rank,
				"department": names.get(r.department, r.department),
				"question_code": r.question_code,
				"question": r.question_text,
				"priority": r.priority,
				"recommendation": r.recommendation,
				"business_risk": r.business_risk,
			}
			for r in gaps[:TOP_GAPS]
		],
		"total_gaps": len(gaps),
		"priority_areas": [
			{**d, "business_risk": meta.get(d["department"], {}).get("business_risk")}
			for d in by_rank[:PRIORITY_AREAS]
		],
		"action_plan": action_plan,
		"kpi": {"available": False, "reason": _(KPI_NOT_AVAILABLE)},
		"roadmap": roadmap,
		"roadmap_summary": (
			_("Departments in growth programme: {0} of {1}.").format(len(below), len(departments))
			if below
			else _(
				"No department is below the growth threshold - focus on the Action Plan gaps and on sustaining strengths."
			)
		),
		"remarks": doc.consultant_remarks,
		"next_reassessment": (
			_("Next re-assessment recommended: {0} (after completion of the 90-day plan).").format(
				reassess.strftime("%d-%b-%Y")
			)
			if reassess
			else ""
		),
		"charts": {
			"radar": charts.radar_chart(_department_chart_items(departments)),
			"bar": charts.bar_chart(_department_chart_items(departments)),
		},
	}


@frappe.whitelist()
def get_owner_dashboard(name: str) -> dict:
	"""OWNER DASHBOARD for one assessment (docs/workbook_audit.md §11.3)."""
	doc = load_assessment(name)
	business = frappe.get_doc("BHC Business", doc.business)
	ctx = _context(doc)
	today = getdate()
	counters = planning.action_counters(
		[(a.status, getdate(a.target_date) if a.target_date else None) for a in ctx["actions"]], today
	)
	gap_count = sum(1 for r in doc.responses if flt(r.gap_points) > 0)
	overall = ctx["comparison"]["overall"] or {}
	trend = frappe.get_list(
		"BHC Assessment",
		filters={"business": doc.business, "docstatus": ["<", 2]},
		fields=[
			"name",
			"assessment_label",
			"assessment_date",
			"status",
			"overall_score",
			"answered_questions",
		],
		order_by="assessment_date asc, creation asc",
		limit_page_length=0,
	)
	return {
		"header": _header(doc, business),
		"cards": {
			"score": doc.overall_score,
			"score_text": percent_text(doc.overall_score),
			"maturity": doc.overall_maturity,
			"answered": f"{doc.answered_questions} / {doc.total_questions}",
			"high_gaps": doc.high_gaps,
			"medium_gaps": doc.medium_gaps,
			"low_gaps": doc.low_gaps,
			# M5 = ActOpen + ActInProg + ActHold, O5 = ActDone (ActPct), over the actions created so far
			"actions_open": counters["open"] + counters["in_progress"] + counters["hold"],
			"actions_completed": f"{counters['completed']} ({percent_text(counters['completion'] * 100)})",
			"actions_overdue": counters["overdue"],
			"gaps_with_action": f"{len(ctx['actions'])} / {gap_count}",
		},
		"heat_map": ctx["departments"],
		"overall_row": {
			"score": doc.overall_score,
			"maturity": doc.overall_maturity,
			"previous_score": overall.get("previous_score"),
			"difference": overall.get("difference"),
			"comparable": overall.get("comparable"),
			"limitations": overall.get("limitations") or [],
			"previous_text": percent_text(overall["previous_score"])
			if overall.get("previous_score") is not None
			else "",
			"change_text": change_text(overall["difference"])
			if overall.get("difference") is not None
			else "",
			"total_gaps": doc.total_gaps,
			"color": _color(doc.max_points > 0, doc.overall_score, ctx["bands"]),
		},
		"previous": ctx["comparison"]["previous"],
		"limitations": ctx["comparison"]["limitations"],
		"trend": [
			{
				**t,
				# B24: "-" when nothing was answered in that assessment
				"score_text": percent_text(t.overall_score) if t.answered_questions else "-",
				"current": t.name == doc.name,
			}
			for t in trend
		],
		"kpi": {"available": False, "reason": _(KPI_NOT_AVAILABLE)},
		"charts": {
			"bar": charts.bar_chart(_department_chart_items(ctx["departments"])),
			"radar": charts.radar_chart(_department_chart_items(ctx["departments"])),
			"trend": charts.trend_chart(
				[
					(t.assessment_label or t.name, t.overall_score if t.answered_questions else None)
					for t in trend
				]
			),
		},
	}


def management_report_for_print(name: str) -> dict:
	"""Jinja method used by the "BHC Management Report" print format (same checks as the API)."""
	return get_management_report(name)
