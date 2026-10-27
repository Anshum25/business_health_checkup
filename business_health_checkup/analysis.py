"""Coverage labels and assessment comparison, free of Frappe (callers pass plain dicts of stored values).

Nothing here is a workbook formula and nothing here judges a result: coverage labels state facts about which
questions were answered, and `compare` reports stored scores side by side with a percentage-point difference
and the reasons a difference may not be comparable. Words like "improved" are deliberately absent; how a change
should be read is open question Q-11.

Assessment dicts (built by assessments.assessment_view from stored results) look like:

	{"name", "assessment_date", "status", "scoring_model", "scoring_model_version", "rules_hash",
	 "overall_score", "earned_points", "max_points", "questions", "answered", "not_applicable",
	 "departments": [{"department", "department_name", "questions", "answered", "not_applicable",
	                  "earned_points", "max_points", "score_percent", "assessed"}, ...],
	 "responses": [{"question_code", "department", "question_text", "criticality", "weight", "answer",
	                "earned_points", "max_points"}, ...]}
"""

NOT_ASSESSED_NO_ANSWERS = "Not assessed (no answers)"
NOT_ASSESSED_ALL_NA = "Not assessed (all N/A)"
PARTLY_ANSWERED = "Partly answered"
FULLY_ANSWERED = "Fully answered"
COVERAGE_STATES = (NOT_ASSESSED_NO_ANSWERS, NOT_ASSESSED_ALL_NA, PARTLY_ANSWERED, FULLY_ANSWERED)

# Snapshot fields that change what a question asks or how much it weighs; other copied text (recommendation,
# KPI, risk) does not affect the answer or the score.
COMPARED_FIELDS = ("department", "question_text", "criticality", "weight")
TOLERANCE = 1e-6


def coverage_state(questions: int, answered: int, not_applicable: int) -> str:
	"""Which questions of a department (or assessment) were answered; "Not assessed" means no applicable answer,
	i.e. the workbook's "Not Assessed" (applicable max = 0)."""
	if not answered:
		return NOT_ASSESSED_NO_ANSWERS
	if answered - not_applicable <= 0:
		return NOT_ASSESSED_ALL_NA
	if answered < questions:
		return PARTLY_ANSWERED
	return FULLY_ANSWERED


def _differs(a, b) -> bool:
	if isinstance(a, int | float) or isinstance(b, int | float):
		return abs((a or 0) - (b or 0)) > TOLERANCE
	return (a or None) != (b or None)


def _applicable(responses, department=None) -> set:
	return {
		r["question_code"]
		for r in responses
		if (r.get("max_points") or 0) > 0 and (department is None or r["department"] == department)
	}


def _header(a: dict) -> dict:
	keys = ("name", "assessment_date", "status", "scoring_model", "scoring_model_version", "rules_hash")
	return {k: a.get(k) for k in keys}


def compare(previous: dict, current: dict) -> dict:
	"""Compare two assessments' stored results by department code and question code. Read-only."""
	prev_q = {r["question_code"]: r for r in previous["responses"]}
	cur_q = {r["question_code"]: r for r in current["responses"]}
	added = [code for code in cur_q if code not in prev_q]
	removed = [code for code in prev_q if code not in cur_q]
	changed = {}
	for code in cur_q:
		if code in prev_q:
			fields = [f for f in COMPARED_FIELDS if _differs(prev_q[code].get(f), cur_q[code].get(f))]
			if fields:
				changed[code] = fields

	same_rules = bool(previous.get("rules_hash")) and previous.get("rules_hash") == current.get("rules_hash")
	general = []
	if not same_rules:
		general.append(
			"Scored with different scoring rules ({0} vs {1})".format(
				previous.get("scoring_model_version") or previous.get("scoring_model"),
				current.get("scoring_model_version") or current.get("scoring_model"),
			)
		)
	if previous.get("status") != "Finalised":
		general.append(f"The previous assessment is {previous.get('status')}, not Finalised")

	touched = {}
	for code in added:
		touched.setdefault(cur_q[code]["department"], []).append(f"{code} added")
	for code in removed:
		touched.setdefault(prev_q[code]["department"], []).append(f"{code} removed")
	for code, fields in changed.items():
		for department in {prev_q[code]["department"], cur_q[code]["department"]}:
			touched.setdefault(department, []).append(f"{code} changed ({', '.join(fields)})")

	prev_d = {d["department"]: d for d in previous["departments"]}
	cur_d = {d["department"]: d for d in current["departments"]}
	order = list(cur_d) + [code for code in prev_d if code not in cur_d]
	departments = [
		_compare_department(
			code, prev_d.get(code), cur_d.get(code), same_rules, touched.get(code, []), previous, current
		)
		for code in order
	]

	overall_limitations = list(general)
	prev_assessed, cur_assessed = previous["max_points"] > 0, current["max_points"] > 0
	if not prev_assessed:
		overall_limitations.append("Nothing applicable was answered in the previous assessment")
	if not cur_assessed:
		overall_limitations.append("Nothing applicable was answered in the current assessment")
	if added or removed or changed:
		overall_limitations.append(
			f"Question set differs: {len(added)} added, {len(removed)} removed, {len(changed)} changed"
		)
	if (
		prev_assessed
		and cur_assessed
		and _applicable(previous["responses"]) != _applicable(current["responses"])
	):
		overall_limitations.append(
			"Different questions were answered (other than N/A) in the two assessments"
		)
	both = prev_assessed and cur_assessed
	overall = {
		"previous_score": previous["overall_score"],
		"current_score": current["overall_score"],
		"difference": current["overall_score"] - previous["overall_score"] if both else None,
		"previous_max_points": previous["max_points"],
		"current_max_points": current["max_points"],
		"previous_answered": previous["answered"],
		"current_answered": current["answered"],
		"previous_questions": previous["questions"],
		"current_questions": current["questions"],
		"previous_coverage": coverage_state(
			previous["questions"], previous["answered"], previous["not_applicable"]
		),
		"current_coverage": coverage_state(
			current["questions"], current["answered"], current["not_applicable"]
		),
		"comparable": both and same_rules and not (added or removed or changed),
		"limitations": overall_limitations,
	}

	questions = []
	for code in list(cur_q) + removed:
		p, c = prev_q.get(code), cur_q.get(code)
		state = "In both" if p and c else ("Added" if c else "Removed")
		questions.append(
			{
				"question_code": code,
				"department": (c or p)["department"],
				"question_text": (c or p).get("question_text"),
				"state": state,
				"snapshot_changes": changed.get(code, []),
				"previous_answer": p.get("answer") if p else None,
				"current_answer": c.get("answer") if c else None,
				"previous_earned_points": p.get("earned_points") if p else None,
				"previous_max_points": p.get("max_points") if p else None,
				"current_earned_points": c.get("earned_points") if c else None,
				"current_max_points": c.get("max_points") if c else None,
				"comparable": bool(p and c) and code not in changed and same_rules,
			}
		)

	return {
		"previous": _header(previous),
		"current": _header(current),
		"same_scoring_rules": same_rules,
		"question_changes": {"added": added, "removed": removed, "changed": changed},
		"limitations": general,
		"overall": overall,
		"departments": departments,
		"questions": questions,
	}


def _compare_department(code, p, c, same_rules, question_notes, previous, current) -> dict:
	limitations = []
	if p is None:
		limitations.append("Not in the previous assessment")
	elif not p["assessed"]:
		limitations.append("Not assessed in the previous assessment")
	if c is None:
		limitations.append("Not in the current assessment")
	elif not c["assessed"]:
		limitations.append("Not assessed in the current assessment")
	if not same_rules:
		limitations.append("Scored with different scoring rules")
	limitations += question_notes
	both = bool(p and c and p["assessed"] and c["assessed"])
	if both and _applicable(previous["responses"], code) != _applicable(current["responses"], code):
		limitations.append("Different questions were answered (other than N/A)")

	def side(d, key):
		return d.get(key) if d else None

	return {
		"department": code,
		"department_name": side(c, "department_name") or side(p, "department_name"),
		"previous_score": side(p, "score_percent"),
		"current_score": side(c, "score_percent"),
		"difference": c["score_percent"] - p["score_percent"] if both else None,
		"previous_max_points": side(p, "max_points"),
		"current_max_points": side(c, "max_points"),
		"previous_coverage": coverage_state(p["questions"], p["answered"], p["not_applicable"])
		if p
		else None,
		"current_coverage": coverage_state(c["questions"], c["answered"], c["not_applicable"]) if c else None,
		"previous_assessed": side(p, "assessed"),
		"current_assessed": side(c, "assessed"),
		"comparable": both and same_rules and not question_notes,
		"limitations": limitations,
	}
