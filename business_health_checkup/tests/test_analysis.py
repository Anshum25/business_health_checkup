"""Coverage labels and comparison (analysis.py), with hand-made stored values. No site needed:

env/bin/python -m unittest business_health_checkup.tests.test_analysis
"""

import copy
import unittest

from business_health_checkup import analysis


def question(code, department, answer, earned, max_points, criticality="Critical", weight=10, text=None):
	return {
		"question_code": code,
		"department": department,
		"question_text": text or f"Question {code}?",
		"criticality": criticality,
		"weight": weight,
		"answer": answer,
		"earned_points": earned,
		"max_points": max_points,
	}


def department(code, questions, answered, na, earned, max_points):
	return {
		"department": code,
		"department_name": f"Dept {code}",
		"questions": questions,
		"answered": answered,
		"not_applicable": na,
		"earned_points": earned,
		"max_points": max_points,
		"score_percent": earned / max_points * 100 if max_points else 0,
		"assessed": max_points > 0,
	}


def assessment(name, responses, rules_hash="v1", status="Finalised"):
	codes = sorted({r["department"] for r in responses})
	departments = []
	for code in codes:
		rows = [r for r in responses if r["department"] == code]
		departments.append(
			department(
				code,
				len(rows),
				sum(1 for r in rows if r["answer"]),
				sum(1 for r in rows if r["answer"] == "N/A"),
				sum(r["earned_points"] for r in rows),
				sum(r["max_points"] for r in rows),
			)
		)
	earned = sum(d["earned_points"] for d in departments)
	max_points = sum(d["max_points"] for d in departments)
	return {
		"name": name,
		"assessment_date": "2026-10-24",
		"status": status,
		"scoring_model": rules_hash,
		"scoring_model_version": rules_hash,
		"rules_hash": rules_hash,
		"overall_score": earned / max_points * 100 if max_points else 0,
		"earned_points": earned,
		"max_points": max_points,
		"questions": len(responses),
		"answered": sum(1 for r in responses if r["answer"]),
		"not_applicable": sum(1 for r in responses if r["answer"] == "N/A"),
		"departments": departments,
		"responses": responses,
	}


def by_department(result):
	return {d["department"]: d for d in result["departments"]}


class TestCoverageState(unittest.TestCase):
	def test_states(self):
		self.assertEqual(analysis.coverage_state(15, 0, 0), analysis.NOT_ASSESSED_NO_ANSWERS)
		self.assertEqual(analysis.coverage_state(15, 3, 3), analysis.NOT_ASSESSED_ALL_NA)
		self.assertEqual(analysis.coverage_state(15, 3, 1), analysis.PARTLY_ANSWERED)
		self.assertEqual(analysis.coverage_state(15, 15, 2), analysis.FULLY_ANSWERED)
		self.assertEqual(analysis.coverage_state(0, 0, 0), analysis.NOT_ASSESSED_NO_ANSWERS)


class TestCompare(unittest.TestCase):
	def setUp(self):
		# A: 1 of 2 answered YES -> 100 %; B: NO -> 0 % (assessed); C: unanswered in the previous assessment.
		self.previous = assessment(
			"P",
			[
				question("A-01", "A", "YES", 10, 10),
				question("A-02", "A", None, 0, 0),
				question("B-01", "B", "NO", 0, 10),
				question("C-01", "C", None, 0, 0),
			],
		)
		self.current = assessment(
			"C",
			[
				question("A-01", "A", "PARTIALLY", 5, 10),
				question("A-02", "A", None, 0, 0),
				question("B-01", "B", "NO", 0, 10),
				question("C-01", "C", "YES", 10, 10),
			],
		)

	def test_same_rules_and_questions(self):
		result = analysis.compare(self.previous, self.current)
		self.assertTrue(result["same_scoring_rules"])
		self.assertEqual(result["question_changes"], {"added": [], "removed": [], "changed": {}})
		departments = by_department(result)
		self.assertEqual((departments["A"]["difference"], departments["A"]["comparable"]), (-50, True))
		# B is assessed on both sides: a zero difference is a real result.
		self.assertEqual((departments["B"]["difference"], departments["B"]["comparable"]), (0, True))
		# C was not assessed before: no difference, not comparable, and the reason is given.
		self.assertIsNone(departments["C"]["difference"])
		self.assertFalse(departments["C"]["comparable"])
		self.assertIn("Not assessed in the previous assessment", departments["C"]["limitations"])
		self.assertEqual(departments["C"]["previous_coverage"], analysis.NOT_ASSESSED_NO_ANSWERS)
		overall = result["overall"]
		self.assertAlmostEqual(overall["previous_score"], 50)  # 10 / 20
		self.assertAlmostEqual(overall["current_score"], 15 / 30 * 100)
		self.assertAlmostEqual(overall["difference"], 0)
		self.assertTrue(overall["comparable"])
		self.assertIn(
			"Different questions were answered (other than N/A) in the two assessments",
			overall["limitations"],
		)

	def test_unassessed_side_has_no_difference(self):
		empty = assessment("E", [question("A-01", "A", None, 0, 0), question("B-01", "B", "N/A", 0, 0)])
		result = analysis.compare(self.previous, empty)
		self.assertIsNone(result["overall"]["difference"])
		self.assertFalse(result["overall"]["comparable"])
		self.assertIsNone(by_department(result)["B"]["difference"])
		self.assertEqual(by_department(result)["B"]["current_coverage"], analysis.NOT_ASSESSED_ALL_NA)

	def test_different_scoring_rules(self):
		current = copy.deepcopy(self.current)
		current["rules_hash"] = current["scoring_model_version"] = "v2"
		result = analysis.compare(self.previous, current)
		self.assertFalse(result["same_scoring_rules"])
		self.assertEqual(result["limitations"], ["Scored with different scoring rules (v1 vs v2)"])
		department_a = by_department(result)["A"]
		self.assertEqual(department_a["difference"], -50)  # still shown, but flagged
		self.assertFalse(department_a["comparable"])
		self.assertFalse(result["overall"]["comparable"])
		self.assertFalse(any(q["comparable"] for q in result["questions"]))

	def test_added_removed_and_changed_questions(self):
		current = copy.deepcopy(self.current)
		current["responses"][1] = question("A-02", "A", None, 0, 0, criticality="Basic", weight=1)
		del current["responses"][3]  # C-01 removed
		current["responses"].append(question("B-02", "B", "YES", 10, 10))
		current = assessment("C", current["responses"])
		result = analysis.compare(self.previous, current)
		self.assertEqual(result["question_changes"]["added"], ["B-02"])
		self.assertEqual(result["question_changes"]["removed"], ["C-01"])
		self.assertEqual(result["question_changes"]["changed"], {"A-02": ["criticality", "weight"]})
		departments = by_department(result)
		self.assertFalse(departments["A"]["comparable"])
		self.assertIn("A-02 changed (criticality, weight)", departments["A"]["limitations"])
		self.assertFalse(departments["B"]["comparable"])
		self.assertIn("B-02 added", departments["B"]["limitations"])
		self.assertIn("Not in the current assessment", departments["C"]["limitations"])
		self.assertIsNone(departments["C"]["current_score"])
		states = {q["question_code"]: q["state"] for q in result["questions"]}
		self.assertEqual((states["B-02"], states["C-01"], states["A-01"]), ("Added", "Removed", "In both"))
		self.assertFalse(result["overall"]["comparable"])
		self.assertIn("Question set differs: 1 added, 1 removed, 1 changed", result["overall"]["limitations"])

	def test_previous_not_finalised(self):
		previous = copy.deepcopy(self.previous)
		previous["status"] = "Cancelled"
		result = analysis.compare(previous, self.current)
		self.assertIn("The previous assessment is Cancelled, not Finalised", result["limitations"])

	def test_inputs_are_not_changed_and_results_repeat(self):
		previous, current = copy.deepcopy(self.previous), copy.deepcopy(self.current)
		first = analysis.compare(previous, current)
		self.assertEqual((previous, current), (self.previous, self.current))
		self.assertEqual(first, analysis.compare(previous, current))

	def test_no_wording_judges_a_change(self):
		text = repr(analysis.compare(self.previous, self.current)).lower()
		for word in ("improv", "declin", "deteriorat", "better", "worse"):
			self.assertNotIn(word, text)
