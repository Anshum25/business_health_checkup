"""Import the verified workbook package (workbook_v1/) into the BHC masters.

	bench --site <site> execute business_health_checkup.setup.importer.import_workbook_v1
	bench --site <site> execute business_health_checkup.setup.importer.import_workbook_v1 --kwargs "{'dry_run': True}"

The whole package is validated before anything is written. Records are matched by their stable codes (department
code, question ID; the scoring model by the workbook's SHA-256). A missing record is created; an existing one
that differs from the package is reported as a conflict and left as it is; records that exist only in the
database are reported as extra and left as they are. Running it again therefore changes nothing.
"""

import json
from collections import Counter
from pathlib import Path

import frappe
from frappe import _

from business_health_checkup import scoring
from business_health_checkup.business_health_checkup.doctype.bhc_scoring_model.bhc_scoring_model import (
	get_default_scoring_model,
	rules_hash,
)

FILES = ("rules.json", "departments.json", "questions.json")
DEPARTMENT_FIELDS = (
	"department_name",
	"chart_label",
	"display_order",
	"sheet_name",
	"business_risk",
	"source_reference",
	"business_risk_reference",
)
QUESTION_FIELDS = (
	"department",
	"seq",
	"sub_category",
	"question",
	"criticality",
	"recommendation",
	"kpi",
	"business_risk",
	"is_active",
	"source_reference",
)


class PackageError(frappe.ValidationError):
	pass


def load_package(folder: Path | str = scoring.WORKBOOK_DATA) -> dict:
	folder = Path(folder)
	package = {name: json.loads((folder / name).read_text()) for name in FILES}
	if problems := validate_package(package):
		raise PackageError("Workbook package is invalid:\n" + "\n".join(problems))
	return package


def validate_package(package: dict) -> list[str]:
	"""Duplicates, broken links and missing required values in the package files."""
	problems = []
	if len({package[name]["_source"]["sha256"] for name in FILES}) != 1:
		problems.append("the files come from different workbooks")

	departments = package["departments.json"]["departments"]
	questions = package["questions.json"]["questions"]
	rules = package["rules.json"]

	for key, values in (
		("department code", [d.get("code") for d in departments]),
		("department order", [d.get("order") for d in departments]),
		("question ID", [q.get("question_id") for q in questions]),
		("department + seq", [(q.get("department"), q.get("seq")) for q in questions]),
	):
		problems += [f"duplicate {key}: {v}" for v, n in Counter(values).items() if n > 1]

	for d in departments:
		problems += [
			f"department {d.get('code')}: missing {f}" for f in ("code", "name", "order") if not d.get(f)
		]
		seqs = [r.get("seq") for r in d.get("growth_recommendations", [])]
		if len(set(seqs)) != len(seqs) or not all(
			r.get("recommendation") for r in d["growth_recommendations"]
		):
			problems.append(f"department {d.get('code')}: growth recommendations need unique seq and text")

	codes = {d.get("code") for d in departments}
	weights = {c["criticality"] for c in rules["criticality_weights"]}
	for q in questions:
		qid = q.get("question_id")
		problems += [
			f"question {qid}: missing {f}"
			for f in ("question_id", "department", "seq", "question", "criticality")
			if not q.get(f)
		]
		if q.get("department") not in codes:
			problems.append(f"question {qid}: unknown department {q.get('department')}")
		elif not str(qid).startswith(f"{q['department']}-"):
			problems.append(f"question {qid}: ID does not start with its department code")
		if q.get("criticality") not in weights:
			problems.append(f"question {qid}: unknown criticality {q.get('criticality')}")

	model = frappe.get_doc(scoring_model_values(rules))
	problems += [f"rules: {p}" for p in model.get_problems()]
	return problems


def source_reference(package: dict) -> str:
	source = package["rules.json"]["_source"]
	return f"{source['workbook']} sha256:{source['sha256']}"


def department_values(d: dict) -> dict:
	return {
		"doctype": "BHC Department",
		"department_code": d["code"],
		"department_name": d["name"],
		"chart_label": d.get("label"),
		"display_order": d["order"],
		"sheet_name": d.get("sheet"),
		"business_risk": d.get("business_risk"),
		"source_reference": d.get("cell"),
		"business_risk_reference": d.get("business_risk_cell"),
		"growth_recommendations": [
			{"seq": r["seq"], "recommendation": r["recommendation"], "source_reference": r.get("cell")}
			for r in d.get("growth_recommendations", [])
		],
	}


def question_values(q: dict) -> dict:
	return {
		"doctype": "BHC Question",
		"question_code": q["question_id"],
		"department": q["department"],
		"seq": q["seq"],
		"sub_category": q.get("sub_category"),
		"question": q["question"],
		"criticality": q["criticality"],
		"recommendation": q.get("recommendation"),
		"kpi": q.get("kpi"),
		"business_risk": q.get("business_risk"),
		"is_active": 1,
		"source_reference": q.get("source_row"),
	}


def scoring_model_values(rules: dict, reference: str | None = None) -> dict:
	return {
		"doctype": "BHC Scoring Model",
		"version_label": "Workbook v1",
		"source_reference": reference,
		"description": "Rules of the SETTINGS sheet of the source workbook, imported unchanged.",
		"answer_scores": [
			{
				"answer": o["answer"],
				"score_fraction": o["score_fraction"],
				"excluded": int(o["excluded"]),
				"source_reference": o.get("cell"),
			}
			for o in rules["answer_options"]
		],
		"criticality_weights": [
			{"criticality": c["criticality"], "weight": c["weight"], "source_reference": c.get("cell")}
			for c in rules["criticality_weights"]
		],
		"maturity_bands": [
			{
				"lower_bound": b["lower_bound"],
				"upper_bound_display": b.get("upper_bound_display"),
				"label": b["label"],
				"short_label": b.get("short_label"),
				"meaning": b.get("meaning"),
				"source_reference": b.get("cell"),
			}
			for b in rules["maturity_bands"]
		],
		"priority_matrix": [
			{
				"criticality": p["criticality"],
				"answer": p["answer"],
				"priority": p["priority"],
				"source_reference": p.get("cell"),
			}
			for p in rules["priority_matrix"]
		],
		"priority_rules": [
			{
				"priority": p["priority"],
				"rank_score": p["rank_score"],
				"phase": p["phase"],
				"start_offset_days": p["start_offset_days"],
				"due_offset_days": p["due_offset_days"],
				"source_reference": p.get("cell"),
			}
			for p in rules["priority_rules"]
		],
		"growth_plan_threshold": rules["growth_plan_threshold"]["value"],
		"strength_threshold": rules["strength_threshold"]["value"],
		"kpi_watch_tolerance": rules["kpi_watch_tolerance"]["value"],
	}


def _differences(doc, values: dict, fields, table=None, table_fields=()) -> list[str]:
	diffs = [f for f in fields if (doc.get(f) or None) != (values.get(f) or None)]
	if table:
		existing = [tuple(row.get(f) or None for f in table_fields) for row in doc.get(table)]
		wanted = [tuple(row.get(f) or None for f in table_fields) for row in values[table]]
		if existing != wanted:
			diffs.append(table)
	return diffs


def _new_report() -> dict:
	return {"created": [], "unchanged": [], "conflicts": {}, "extra": []}


def import_workbook_v1(dry_run: bool = False, folder: str | None = None) -> dict:
	"""Create what is missing from the package; report everything else. Returns the report."""
	package = load_package(folder or scoring.WORKBOOK_DATA)
	report = {"source": source_reference(package), "dry_run": bool(dry_run)}

	departments = report["departments"] = _new_report()
	for d in package["departments.json"]["departments"]:
		values = department_values(d)
		if not frappe.db.exists("BHC Department", d["code"]):
			departments["created"].append(d["code"])
			if not dry_run:
				frappe.get_doc(values).insert(ignore_permissions=True)
			continue
		doc = frappe.get_doc("BHC Department", d["code"])
		diffs = _differences(
			doc, values, DEPARTMENT_FIELDS, "growth_recommendations", ("seq", "recommendation")
		)
		if diffs:
			departments["conflicts"][d["code"]] = diffs
		else:
			departments["unchanged"].append(d["code"])
	source_codes = {d["code"] for d in package["departments.json"]["departments"]}
	departments["extra"] = sorted(set(frappe.get_all("BHC Department", pluck="name")) - source_codes)

	questions = report["questions"] = _new_report()
	for q in package["questions.json"]["questions"]:
		values = question_values(q)
		if not frappe.db.exists("BHC Question", q["question_id"]):
			questions["created"].append(q["question_id"])
			if not dry_run:
				frappe.get_doc(values).insert(ignore_permissions=True)
			continue
		diffs = _differences(frappe.get_doc("BHC Question", q["question_id"]), values, QUESTION_FIELDS)
		if diffs:
			questions["conflicts"][q["question_id"]] = diffs
		else:
			questions["unchanged"].append(q["question_id"])
	source_ids = {q["question_id"] for q in package["questions.json"]["questions"]}
	questions["extra"] = sorted(set(frappe.get_all("BHC Question", pluck="name")) - source_ids)

	report["scoring_model"] = _import_scoring_model(package, dry_run)
	return report


def _import_scoring_model(package: dict, dry_run: bool) -> dict:
	reference = source_reference(package)
	values = scoring_model_values(package["rules.json"], reference)
	wanted_hash = rules_hash(frappe.get_doc(values).as_rules_dict())
	existing = frappe.get_all(
		"BHC Scoring Model",
		filters={"source_reference": reference, "docstatus": ("<", 2)},
		fields=["name", "docstatus", "rules_hash"],
		order_by="creation asc",
	)
	if existing:
		model = existing[0]
		if model.rules_hash != wanted_hash:
			return {"status": "conflict", "name": model.name, "reason": "rules differ from the package"}
		if model.docstatus != 1:
			return {"status": "conflict", "name": model.name, "reason": "imported model is not submitted"}
		return {"status": "unchanged", "name": model.name}
	if dry_run:
		return {"status": "would create"}

	doc = frappe.get_doc(values).insert(ignore_permissions=True)
	make_default = not get_default_scoring_model()
	doc.is_default = int(make_default)
	doc.flags.ignore_permissions = True
	doc.submit()
	return {"status": "created", "name": doc.name, "default": make_default}


def print_summary(report: dict) -> None:
	for key in ("departments", "questions"):
		part = report[key]
		print(
			_("{0}: {1} created, {2} unchanged, {3} conflicts, {4} extra").format(
				key,
				len(part["created"]),
				len(part["unchanged"]),
				len(part["conflicts"]),
				len(part["extra"]),
			)
		)
	print(_("scoring model: {0}").format(report["scoring_model"]))
