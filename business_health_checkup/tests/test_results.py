"""Phase 3: gap analysis, department results and ranking, results summary, re-assessment comparison.

Expected figures are worked out from the workbook (cached GAP ANALYSIS / SCORE CALCULATION values for its sample
answers) or by hand from the SETTINGS weights, never by calling the code under test twice.
Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_results
"""

import frappe
from frappe.desk.query_report import run

from business_health_checkup import assessments
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS

ORDER = ["STR", "KPI", "HR", "MKT", "SAL", "PUR", "PRD", "QA", "MNT", "INV"]
# SCORE CALCULATION!U5:U14 for the sample answers
SAMPLE_RANKS = {
	"KPI": 1,
	"HR": 2,
	"MKT": 3,
	"SAL": 4,
	"PUR": 5,
	"PRD": 6,
	"QA": 7,
	"MNT": 8,
	"INV": 9,
	"STR": 10,
}
# Re-assessment answers: STR-01 YES (Standard 3) + STR-02 YES (Critical 10) + STR-03 PARTIALLY (Critical 5)
# = 18 / 23; KPI-10 and KPI-11 NO again (0 / 10).
SECOND_ANSWERS = {"STR-01": "YES", "STR-02": "YES", "STR-03": "PARTIALLY", "KPI-10": "NO", "KPI-11": "NO"}


def report_rows(name, **filters):
	return run(name, filters=filters)["result"]


def department_codes(doctype_rows):
	return [r["department"] for r in doctype_rows]


class ResultsTestCase(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()
		cls.business = fixtures.make_business("Results Test Ltd")

	def questions_of(self, department):
		return frappe.get_all(
			"BHC Question",
			filters={"department": department, "is_active": 1},
			fields=["name", "criticality"],
			order_by="seq",
		)

	def finalised_sample(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		doc.submit()
		return doc

	def reassess(self, previous, answers):
		doc = assessments.make_reassessment(previous.name)
		doc.assessment_date = "2027-01-22"
		doc.insert()
		fixtures.set_answers(doc, answers)
		doc.save()
		return doc


class TestGapAnalysisReport(ResultsTestCase):
	def test_workbook_sample(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		result = run("BHC Gap Analysis", filters={"assessment": doc.name})
		rows = result["result"]
		# GAP ANALYSIS!A19:N22
		self.assertEqual(
			[
				(r["gap_rank"], r["question_code"], r["answer"], r["priority"], r["gap_points"], r["phase"])
				for r in rows
			],
			[
				(1, "STR-03", "NO", "HIGH", 10, "0-30 Days"),
				(2, "STR-02", "PARTIALLY", "MEDIUM", 5, "31-60 Days"),
				(3, "KPI-10", "NO", "MEDIUM", 5, "31-60 Days"),
				(4, "KPI-11", "NO", "MEDIUM", 5, "31-60 Days"),
			],
		)
		first = rows[0]
		self.assertEqual(
			(
				first["criticality"],
				first["weight"],
				first["earned_points"],
				first["max_points"],
				first["kpi"],
			),
			("Critical", 10, 0, 10, "Turnover achievement % vs target"),
		)
		self.assertTrue(first["recommendation"].startswith("Fix the annual turnover target"))
		self.assertTrue(first["business_risk"].startswith("Nobody knows in July"))
		self.assertEqual(
			(first["business"], first["assessment"], first["status"]), (self.business, doc.name, "Draft")
		)
		# GAP ANALYSIS!B4:G4
		summary = {s["label"]: s["value"] for s in result["report_summary"]}
		self.assertEqual(
			(
				summary["Total Gaps"],
				summary["HIGH"],
				summary["MEDIUM"],
				summary["LOW"],
				summary["Points Lost"],
			),
			(4, 1, 3, 0, 25),
		)
		self.assertAlmostEqual(summary["Overall Score"], 24.242424242, places=6)

	def test_filters(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		cases = {
			"priority": ({"priority": "HIGH"}, ["STR-03"]),
			"department": ({"department": "KPI"}, ["KPI-10", "KPI-11"]),
			"criticality": ({"criticality": "Critical"}, ["STR-03", "STR-02"]),
			"answer": ({"answer": "PARTIALLY"}, ["STR-02"]),
			"status draft": ({"status": "Draft"}, ["STR-03", "STR-02", "KPI-10", "KPI-11"]),
			"status finalised": ({"status": "Finalised"}, []),
			"business": ({"business": self.business}, ["STR-03", "STR-02", "KPI-10", "KPI-11"]),
		}
		for label, (filters, expected) in cases.items():
			with self.subTest(label):
				rows = report_rows("BHC Gap Analysis", assessment=doc.name, **filters)
				self.assertEqual([r["question_code"] for r in rows], expected)

	def test_yes_na_and_unanswered_are_not_gaps(self):
		doc = fixtures.make_assessment(self.business, {"STR-01": "YES", "STR-02": "N/A"})
		self.assertEqual(report_rows("BHC Gap Analysis", assessment=doc.name), [])
		summary = run("BHC Gap Analysis", filters={"assessment": doc.name})["report_summary"]
		self.assertEqual({s["label"]: s["value"] for s in summary}["Total Gaps"], 0)

	def test_cancelled_assessments_only_on_request(self):
		doc = self.finalised_sample()
		doc.cancel()
		self.assertEqual(report_rows("BHC Gap Analysis", business=self.business), [])
		self.assertEqual(len(report_rows("BHC Gap Analysis", business=self.business, status="Cancelled")), 4)

	def test_finalised_gaps_keep_their_snapshot_and_phase(self):
		doc = self.finalised_sample()
		question = frappe.get_doc("BHC Question", "STR-03")
		question.recommendation = "Edited later"
		question.criticality = "Standard"
		question.save()
		values = fixtures.copy_model("Short phases")
		values["priority_rules"][0]["phase"] = "0-15 Days"
		model = frappe.get_doc(values).insert()
		model.is_default = 1
		model.submit()

		first = report_rows("BHC Gap Analysis", assessment=doc.name)[0]
		self.assertEqual(
			(first["question_code"], first["criticality"], first["weight"]), ("STR-03", "Critical", 10)
		)
		self.assertTrue(first["recommendation"].startswith("Fix the annual turnover target"))
		self.assertEqual(first["phase"], "0-30 Days")

	def test_running_the_report_creates_nothing(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		count = frappe.db.count("BHC Assessment Response")
		modified = frappe.db.get_value("BHC Assessment", doc.name, "modified")
		first = report_rows("BHC Gap Analysis", assessment=doc.name)
		self.assertEqual(first, report_rows("BHC Gap Analysis", assessment=doc.name))
		self.assertEqual(frappe.db.count("BHC Assessment Response"), count)
		self.assertEqual(frappe.db.get_value("BHC Assessment", doc.name, "modified"), modified)


class TestDepartmentResults(ResultsTestCase):
	def test_workbook_rank_and_coverage(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		rows = report_rows("BHC Department Results", assessment=doc.name)
		self.assertEqual(department_codes(rows), sorted(SAMPLE_RANKS, key=SAMPLE_RANKS.get))
		self.assertEqual({r["department"]: r["workbook_rank"] for r in rows}, SAMPLE_RANKS)
		by_code = {r["department"]: r for r in rows}
		self.assertEqual(
			(by_code["STR"]["coverage"], by_code["STR"]["answered"], by_code["STR"]["unanswered"]),
			("Partly answered", 3, 12),
		)
		# KPI is assessed at 0 %; HR has no answers. Both store 0 %, but only the coverage tells them apart.
		self.assertEqual((by_code["KPI"]["score_percent"], by_code["KPI"]["assessed"]), (0, True))
		self.assertEqual((by_code["HR"]["score_percent"], by_code["HR"]["assessed"]), (0, False))
		self.assertEqual(by_code["KPI"]["coverage"], "Partly answered")
		self.assertEqual(by_code["HR"]["coverage"], "Not assessed (no answers)")
		self.assertEqual(by_code["HR"]["maturity"], "Not Assessed")
		self.assertEqual(by_code["HR"]["growth_status"], "PRIORITY - GROWTH PLAN")  # workbook parity, W-01

		in_order = report_rows("BHC Department Results", assessment=doc.name, sort_by="Department order")
		self.assertEqual(department_codes(in_order), ORDER)

	def test_all_unanswered_ranks_in_department_order(self):
		doc = fixtures.make_assessment(self.business)
		rows = report_rows("BHC Department Results", assessment=doc.name, sort_by="Department order")
		self.assertEqual([r["workbook_rank"] for r in rows], list(range(1, 11)))
		self.assertEqual({r["coverage"] for r in rows}, {"Not assessed (no answers)"})

	def test_na_full_and_repeated_problem_area(self):
		hr = self.questions_of("HR")
		mkt = self.questions_of("MKT")
		qa = self.questions_of("QA")
		answers = {q.name: "N/A" for q in hr}
		answers |= {q.name: "YES" for q in mkt}
		answers |= {q.name: "NO" for q in qa}  # QA has 6 Critical questions -> 6 HIGH gaps
		inv = self.questions_of("INV")
		answers |= {q.name: "NO" for q in inv if q.criticality != "Critical"}  # 12 MEDIUM/LOW gaps, no HIGH
		doc = fixtures.make_assessment(self.business, answers)
		by_code = {r["department"]: r for r in report_rows("BHC Department Results", assessment=doc.name)}

		self.assertEqual(
			(by_code["HR"]["coverage"], by_code["HR"]["not_applicable"], by_code["HR"]["applicable"]),
			("Not assessed (all N/A)", 15, 0),
		)
		self.assertEqual((by_code["HR"]["assessed"], by_code["HR"]["maturity"]), (False, "Not Assessed"))
		self.assertEqual(
			(by_code["MKT"]["coverage"], by_code["MKT"]["score_percent"], by_code["MKT"]["maturity"]),
			("Fully answered", 100, "ADVANCED"),
		)
		self.assertEqual(by_code["MKT"]["growth_status"], "STRENGTH - LEVERAGE")
		self.assertEqual(by_code["QA"]["high_gaps"], sum(1 for q in qa if q.criticality == "Critical"))
		self.assertEqual(by_code["QA"]["repeated_problem_area"], "YES - 3+ HIGH gaps: systemic weakness")
		self.assertEqual(by_code["INV"]["high_gaps"], 0)
		self.assertEqual(by_code["INV"]["repeated_problem_area"], "YES - many gaps in one function")
		self.assertEqual(by_code["MKT"]["repeated_problem_area"], "")

		not_assessed = report_rows(
			"BHC Department Results", assessment=doc.name, coverage="Not assessed (all N/A)"
		)
		self.assertEqual(department_codes(not_assessed), ["HR"])
		self.assertEqual(
			department_codes(report_rows("BHC Department Results", assessment=doc.name, department="QA")),
			["QA"],
		)
		with self.assertRaises(frappe.ValidationError):
			run("BHC Department Results", filters={"assessment": doc.name, "coverage": "Anything"})

	def test_results_summary(self):
		first = self.finalised_sample()
		second = self.reassess(first, SECOND_ANSWERS)
		summary = assessments.get_results_summary(first.name)
		self.assertEqual(
			(summary["answered"], summary["not_applicable"], summary["unanswered"], summary["questions"]),
			(5, 0, 145, 150),
		)
		self.assertEqual((summary["high_gaps"], summary["medium_gaps"], summary["low_gaps"]), (1, 3, 0))
		self.assertEqual(summary["coverage"], "Partly answered")
		self.assertEqual({d["department"]: d["workbook_rank"] for d in summary["departments"]}, SAMPLE_RANKS)
		self.assertEqual([r.name for r in summary["reassessments"]], [second.name])
		self.assertIsNone(summary["previous"])
		self.assertEqual(assessments.get_results_summary(second.name)["previous"].name, first.name)


class TestComparison(ResultsTestCase):
	def assert_untouched(self, docs, action):
		before = {
			d.name: frappe.db.get_value("BHC Assessment", d.name, ["modified", "overall_score"]) for d in docs
		}
		result = action()
		after = {
			d.name: frappe.db.get_value("BHC Assessment", d.name, ["modified", "overall_score"]) for d in docs
		}
		self.assertEqual(before, after)
		return result

	def test_same_rules_and_questions(self):
		first = self.finalised_sample()
		second = self.reassess(first, SECOND_ANSWERS)
		comparison = self.assert_untouched([first, second], lambda: assessments.get_comparison(second.name))
		self.assertTrue(comparison["same_scoring_rules"])
		self.assertEqual(comparison["question_changes"], {"added": [], "removed": [], "changed": {}})
		self.assertEqual(
			(comparison["previous"]["name"], comparison["current"]["name"]), (first.name, second.name)
		)

		departments = {d["department"]: d for d in comparison["departments"]}
		strategy = departments["STR"]
		self.assertAlmostEqual(strategy["previous_score"], 800 / 23, places=6)
		self.assertAlmostEqual(strategy["current_score"], 1800 / 23, places=6)
		self.assertAlmostEqual(strategy["difference"], 1000 / 23, places=6)  # percentage points
		self.assertEqual((strategy["previous_max_points"], strategy["current_max_points"]), (23, 23))
		self.assertTrue(strategy["comparable"])
		# KPI: 0 % on both sides, both assessed -> a real zero difference
		self.assertEqual((departments["KPI"]["difference"], departments["KPI"]["comparable"]), (0, True))
		# HR: never answered -> no difference at all, not a 0-point change
		self.assertIsNone(departments["HR"]["difference"])
		self.assertFalse(departments["HR"]["comparable"])
		self.assertEqual(departments["HR"]["current_coverage"], "Not assessed (no answers)")

		overall = comparison["overall"]
		self.assertAlmostEqual(overall["previous_score"], 800 / 33, places=6)
		self.assertAlmostEqual(overall["current_score"], 1800 / 33, places=6)
		self.assertAlmostEqual(overall["difference"], 1000 / 33, places=6)
		self.assertTrue(overall["comparable"])

		# Stored history is unchanged and a repeat gives the same answer.
		first.reload()
		self.assertAlmostEqual(first.overall_score, 800 / 33, places=6)
		self.assertEqual(comparison, assessments.get_comparison(second.name))

	def test_different_scoring_version(self):
		first = self.finalised_sample()
		v2 = frappe.get_doc(fixtures.copy_model("Test v2", Critical=20)).insert()
		v2.is_default = 1
		v2.submit()
		second = self.reassess(first, SECOND_ANSWERS)
		self.assertEqual(second.scoring_model, v2.name)
		self.assertNotEqual(first.scoring_model, second.scoring_model)
		comparison = assessments.get_comparison(second.name)
		self.assertFalse(comparison["same_scoring_rules"])
		self.assertIn("Workbook v1 vs Test v2", comparison["limitations"][0])
		# Every Critical question now weighs 20 instead of 10, which the snapshot comparison reports.
		self.assertEqual(comparison["question_changes"]["changed"]["STR-02"], ["weight"])
		self.assertNotIn("STR-01", comparison["question_changes"]["changed"])  # Standard: still 3
		strategy = next(d for d in comparison["departments"] if d["department"] == "STR")
		# v2: 3 + 20 + 10 = 33 of 3 + 20 + 20 = 43
		self.assertAlmostEqual(strategy["current_score"], 3300 / 43, places=6)
		self.assertAlmostEqual(strategy["previous_score"], 800 / 23, places=6)  # stored v1 figure
		self.assertFalse(strategy["comparable"])
		self.assertIn("Scored with different scoring rules", strategy["limitations"])
		self.assertFalse(comparison["overall"]["comparable"])

	def test_changed_added_and_removed_questions(self):
		first = self.finalised_sample()
		question = frappe.get_doc("BHC Question", "STR-02")
		question.criticality = "Standard"
		question.save()
		frappe.get_doc(
			{
				"doctype": "BHC Question",
				"question_code": "QA-16",
				"department": "QA",
				"seq": 16,
				"question": "Is there a spare question?",
				"criticality": "Basic",
			}
		).insert()
		frappe.db.set_value("BHC Question", "INV-15", "is_active", 0)
		second = self.reassess(first, SECOND_ANSWERS)

		comparison = assessments.get_comparison(second.name)
		changes = comparison["question_changes"]
		self.assertEqual(
			(changes["added"], changes["removed"], changes["changed"]),
			(["QA-16"], ["INV-15"], {"STR-02": ["criticality", "weight"]}),
		)
		departments = {d["department"]: d for d in comparison["departments"]}
		self.assertFalse(departments["STR"]["comparable"])
		self.assertIn("STR-02 changed (criticality, weight)", departments["STR"]["limitations"])
		self.assertIn("QA-16 added", departments["QA"]["limitations"])
		self.assertIn("INV-15 removed", departments["INV"]["limitations"])
		self.assertTrue(departments["KPI"]["comparable"])  # untouched department, assessed on both sides
		self.assertFalse(comparison["overall"]["comparable"])
		self.assertIn(
			"Question set differs: 1 added, 1 removed, 1 changed", comparison["overall"]["limitations"]
		)
		states = {q["question_code"]: q["state"] for q in comparison["questions"]}
		self.assertEqual(
			(states["QA-16"], states["INV-15"], states["STR-01"]), ("Added", "Removed", "In both")
		)

	def test_cancelled_previous_and_no_previous(self):
		first = self.finalised_sample()
		second = self.reassess(first, SECOND_ANSWERS)
		first.cancel()
		comparison = assessments.get_comparison(second.name)
		self.assertIn("The previous assessment is Cancelled, not Finalised", comparison["limitations"])

		alone = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		comparison = assessments.get_comparison(alone.name)
		self.assertIsNone(comparison["previous"])
		self.assertEqual(comparison["departments"], [])
		result = run("BHC Assessment Comparison", filters={"assessment": alone.name})
		self.assertEqual(result["result"], [])
		self.assertIn("No previous assessment is linked", result["message"])

	def test_comparison_report(self):
		first = self.finalised_sample()
		second = self.reassess(first, SECOND_ANSWERS)
		result = run("BHC Assessment Comparison", filters={"assessment": second.name})
		rows = result["result"]
		self.assertEqual(rows[0]["department"], "ALL")
		self.assertAlmostEqual(rows[0]["difference"], 1000 / 33, places=6)
		self.assertEqual(department_codes(rows[1:]), ORDER)
		self.assertEqual(rows[1]["comparable"], "Yes")
		self.assertIn(first.name, result["message"])
		questions = run(
			"BHC Assessment Comparison", filters={"assessment": second.name, "view": "Questions"}
		)["result"]
		self.assertEqual(len(questions), 150)
		str02 = next(q for q in questions if q["question_code"] == "STR-02")
		self.assertEqual(
			(
				str02["previous_answer"],
				str02["current_answer"],
				str02["previous_points"],
				str02["current_points"],
			),
			("PARTIALLY", "YES", "5 / 10", "10 / 10"),
		)
