"""BHC Assessment: snapshot, scoring through the engine, lifecycle, history and re-assessment.

Expected figures are the workbook's own cached results for its sample answers, not engine output.
Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_assessment
"""

import frappe
from frappe.utils import getdate

from business_health_checkup import assessments
from business_health_checkup.business_health_checkup.doctype.bhc_scoring_model.bhc_scoring_model import (
	get_default_scoring_model,
)
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS, department, response

WORKBOOK_WEIGHTS = {"Critical": 10, "Important": 5, "Standard": 3, "Basic": 1}  # SETTINGS!D5:E8
NOT_ASSESSED_CODES = ("HR", "MKT", "SAL", "PUR", "PRD", "QA", "MNT", "INV")


class AssessmentTestCase(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()
		cls.business = fixtures.make_business("Assessment Test Ltd")
		cls.other_business = fixtures.make_business("Other Test Ltd")


class TestSnapshot(AssessmentTestCase):
	def test_new_assessment_copies_every_active_question(self):
		doc = fixtures.make_assessment(self.business)
		self.assertEqual(len(doc.responses), 150)
		self.assertEqual(
			(doc.responses[0].question_code, doc.responses[-1].question_code), ("STR-01", "INV-15")
		)
		self.assertEqual([r.idx for r in doc.responses], list(range(1, 151)))
		for row in doc.responses:
			master = frappe.db.get_value(
				"BHC Question",
				row.question_code,
				["question", "criticality", "department", "seq"],
				as_dict=True,
			)
			self.assertEqual(
				(row.question_text, row.criticality, row.department, row.seq),
				(master.question, master.criticality, master.department, master.seq),
			)
			self.assertEqual(row.weight, WORKBOOK_WEIGHTS[row.criticality])
			self.assertFalse(row.answer)
		self.assertEqual(doc.scoring_model, get_default_scoring_model())
		self.assertEqual(
			(doc.sequence_no, doc.assessment_label, doc.status), (1, "Assessment 1 - Baseline", "Draft")
		)

	def test_inactive_questions_are_left_out(self):
		frappe.db.set_value("BHC Question", "INV-15", "is_active", 0)
		doc = fixtures.make_assessment(self.business)
		self.assertEqual(len(doc.responses), 149)
		self.assertNotIn("INV-15", [r.question_code for r in doc.responses])
		frappe.db.set_value("BHC Question", "INV-15", "is_active", 1)

	def test_api_supplied_answers_are_kept_but_snapshot_comes_from_the_master(self):
		doc = frappe.get_doc(
			{
				"doctype": "BHC Assessment",
				"business": self.business,
				"assessment_date": fixtures.SAMPLE_DATE,
				"responses": [
					{"question_code": "STR-01", "answer": "YES", "question_text": "edited", "weight": 99}
				],
			}
		).insert()
		row = response(doc, "STR-01")
		self.assertEqual((row.answer, row.weight), ("YES", 3))  # STR-01 is Standard
		self.assertTrue(row.question_text.startswith("Does the company have a written Vision and Mission"))
		self.assertEqual(len(doc.responses), 150)

	def test_unknown_question_in_api_payload_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "BHC Assessment",
					"business": self.business,
					"assessment_date": fixtures.SAMPLE_DATE,
					"responses": [{"question_code": "ZZZ-01", "answer": "YES"}],
				}
			).insert()

	def test_snapshot_cannot_be_edited(self):
		doc = fixtures.make_assessment(self.business)
		edits = {
			"question text": lambda d: setattr(d.responses[0], "question_text", "edited"),
			"weight": lambda d: setattr(d.responses[1], "weight", 99),
			"criticality": lambda d: setattr(d.responses[2], "criticality", "Basic"),
			"recommendation": lambda d: setattr(d.responses[3], "recommendation", "edited"),
			"order": lambda d: (setattr(d.responses[0], "idx", 2), setattr(d.responses[1], "idx", 1)),
			"removed row": lambda d: d.responses.pop(),
			"added row": lambda d: d.append("responses", {"question_code": "STR-01", "answer": "YES"}),
		}
		for label, edit in edits.items():
			with self.subTest(label):
				doc.reload()
				edit(doc)
				with self.assertRaises(frappe.ValidationError):
					doc.save()

	def test_business_and_scoring_model_are_fixed(self):
		doc = fixtures.make_assessment(self.business)
		other_model = frappe.get_doc(fixtures.copy_model("Other")).insert()
		other_model.submit()
		for field, value in (("scoring_model", other_model.name), ("business", self.other_business)):
			with self.subTest(field):
				doc.reload()
				doc.set(field, value)
				with self.assertRaises(frappe.ValidationError):
					doc.save()


class TestScoring(AssessmentTestCase):
	def test_workbook_sample(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)

		strategy = department(doc, "STR")  # SCORE CALCULATION!C5:M5
		self.assertEqual(
			(strategy.questions, strategy.answered, strategy.earned_points, strategy.max_points),
			(15, 3, 8, 23),
		)
		self.assertAlmostEqual(strategy.score_percent, 34.782608696, places=6)
		self.assertAlmostEqual(strategy.completion_percent, 20, places=6)
		self.assertEqual(strategy.maturity, "CRITICAL IMPROVEMENT REQUIRED")
		self.assertEqual((strategy.high_gaps, strategy.medium_gaps, strategy.low_gaps), (1, 1, 0))
		self.assertTrue(strategy.assessed)

		kpi = department(doc, "KPI")  # row 6
		self.assertEqual((kpi.answered, kpi.earned_points, kpi.max_points, kpi.score_percent), (2, 0, 10, 0))
		self.assertEqual((kpi.maturity, kpi.medium_gaps), ("CRITICAL IMPROVEMENT REQUIRED", 2))

		for code in NOT_ASSESSED_CODES:  # rows 7-14
			with self.subTest(code):
				row = department(doc, code)
				self.assertEqual((row.answered, row.max_points, row.score_percent), (0, 0, 0))
				self.assertEqual((row.maturity, row.assessed), ("Not Assessed", 0))
				# BUSINESS GROWTH PLAN treats the 0 as a score (W-01); kept for parity until Q-04 is decided.
				self.assertEqual(row.growth_status, "PRIORITY - GROWTH PLAN")

		self.assertEqual([r.department for r in doc.department_results], ["STR", "KPI", *NOT_ASSESSED_CODES])
		# SCORE CALCULATION!C15:M15
		self.assertEqual(
			(doc.total_questions, doc.answered_questions, doc.earned_points, doc.max_points), (150, 5, 8, 33)
		)
		self.assertAlmostEqual(doc.overall_score, 24.242424242, places=6)
		self.assertAlmostEqual(doc.completion_percent, 3.333333333, places=6)
		self.assertEqual(doc.overall_maturity, "CRITICAL IMPROVEMENT REQUIRED")
		self.assertEqual((doc.high_gaps, doc.medium_gaps, doc.low_gaps, doc.total_gaps), (1, 3, 0, 4))

		# GAP ANALYSIS!C19:J22
		ranked = sorted((r for r in doc.responses if r.gap_rank), key=lambda r: r.gap_rank)
		self.assertEqual(
			[(r.question_code, r.priority, r.gap_points) for r in ranked],
			[
				("STR-03", "HIGH", 10),
				("STR-02", "MEDIUM", 5),
				("KPI-10", "MEDIUM", 5),
				("KPI-11", "MEDIUM", 5),
			],
		)
		self.assertEqual((response(doc, "STR-02").earned_points, response(doc, "STR-02").max_points), (5, 10))
		self.assertEqual((response(doc, "STR-01").gap_points, response(doc, "STR-01").priority), (0, ""))

		self.assertEqual(
			doc.rules_hash, frappe.db.get_value("BHC Scoring Model", doc.scoring_model, "rules_hash")
		)
		self.assertEqual(doc.scoring_model_version, "Workbook v1")
		self.assertEqual(
			getdate(doc.suggested_reassessment_date), getdate("2027-01-22")
		)  # MANAGEMENT REPORT!B113

	def test_na_is_answered_but_excluded_and_blank_is_unanswered(self):
		doc = fixtures.make_assessment(self.business, {"STR-01": "N/A", "STR-02": "YES"})
		strategy = department(doc, "STR")
		self.assertEqual((strategy.answered, strategy.earned_points, strategy.max_points), (2, 10, 10))
		self.assertEqual(strategy.score_percent, 100)
		self.assertEqual(strategy.maturity, "ADVANCED")
		na, blank = response(doc, "STR-01"), response(doc, "STR-03")
		self.assertEqual((na.earned_points, na.max_points, na.priority), (0, 0, ""))
		self.assertEqual((blank.answer, blank.earned_points, blank.max_points), (None, 0, 0))

	def test_unanswered_assessment(self):
		doc = fixtures.make_assessment(self.business)
		self.assertEqual((doc.overall_score, doc.max_points, doc.overall_maturity), (0, 0, "Not Assessed"))
		self.assertEqual(doc.total_gaps, 0)

	def test_invalid_answer_is_rejected_and_a_retry_works(self):
		doc = fixtures.make_assessment(self.business)
		response(doc, "STR-01").answer = "MAYBE"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		doc.reload()
		self.assertFalse(response(doc, "STR-01").answer)
		response(doc, "STR-01").answer = "YES"
		doc.save()
		self.assertEqual(department(doc, "STR").earned_points, 3)

	def test_results_supplied_by_the_caller_are_replaced(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		response(doc, "STR-01").earned_points = 999
		response(doc, "STR-03").priority = "LOW"
		department(doc, "STR").score_percent = 100
		doc.overall_score = 100
		doc.overall_maturity = "ADVANCED"
		doc.save()
		doc.reload()
		self.assertEqual(
			(response(doc, "STR-01").earned_points, response(doc, "STR-03").priority), (3, "HIGH")
		)
		self.assertAlmostEqual(department(doc, "STR").score_percent, 34.782608696, places=6)
		self.assertAlmostEqual(doc.overall_score, 24.242424242, places=6)
		self.assertEqual(doc.overall_maturity, "CRITICAL IMPROVEMENT REQUIRED")

	def test_saving_again_gives_the_same_results(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		first = [
			(r.question_code, r.earned_points, r.max_points, r.priority, r.gap_rank) for r in doc.responses
		]
		doc.save()
		doc.reload()
		self.assertEqual(
			first,
			[(r.question_code, r.earned_points, r.max_points, r.priority, r.gap_rank) for r in doc.responses],
		)
		self.assertAlmostEqual(doc.overall_score, 24.242424242, places=6)
		self.assertEqual(assessments.stored_result_differences(doc), [])


class TestLifecycle(AssessmentTestCase):
	def test_finalise(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		doc.submit()
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status), (1, "Finalised"))
		self.assertEqual(assessments.verify_results(doc.name), {"matches": True, "differences": []})

	def test_finalised_assessment_cannot_be_edited(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		doc.submit()
		edits = {
			"answer": lambda d: setattr(response(d, "STR-01"), "answer", "NO"),
			"evidence": lambda d: setattr(response(d, "STR-01"), "evidence", "late"),
			"score": lambda d: setattr(d, "overall_score", 99),
			"date": lambda d: setattr(d, "assessment_date", "2026-01-01"),
			"remarks": lambda d: setattr(d, "consultant_remarks", "late"),
		}
		for label, edit in edits.items():
			with self.subTest(label):
				doc.reload()
				edit(doc)
				with self.assertRaises(frappe.UpdateAfterSubmitError):
					doc.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.client.set_value("BHC Assessment", doc.name, "overall_score", 99)

	def test_amendment_keeps_the_original_snapshot(self):
		doc = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		doc.submit()
		doc.cancel()
		self.assertEqual(frappe.db.get_value("BHC Assessment", doc.name, "status"), "Cancelled")
		amended = frappe.copy_doc(doc)
		amended.update({"amended_from": doc.name, "docstatus": 0})
		amended.insert()
		self.assertEqual((amended.scoring_model, amended.sequence_no), (doc.scoring_model, doc.sequence_no))
		self.assertEqual(
			[(r.question_code, r.question_text, r.weight, r.answer or None) for r in amended.responses],
			[(r.question_code, r.question_text, r.weight, r.answer or None) for r in doc.responses],
		)

		tampered = frappe.copy_doc(doc)
		tampered.update({"amended_from": doc.name, "docstatus": 0})
		tampered.responses[0].question_text = "edited"
		with self.assertRaises(frappe.ValidationError):
			tampered.insert()


class TestHistory(AssessmentTestCase):
	def test_master_changes_and_new_rules_leave_a_finalised_assessment_alone(self):
		first = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		first.submit()
		v1 = first.scoring_model

		question = frappe.get_doc("BHC Question", "STR-02")
		original_text = question.question
		question.criticality = "Standard"
		question.question = "Edited later"
		question.save()
		v2 = frappe.get_doc(fixtures.copy_model("Test v2", Critical=20)).insert()
		v2.is_default = 1
		v2.submit()

		first.reload()
		row = response(first, "STR-02")
		self.assertEqual((row.criticality, row.weight, row.question_text), ("Critical", 10, original_text))
		self.assertEqual((first.scoring_model, first.earned_points, first.max_points), (v1, 8, 33))
		self.assertAlmostEqual(first.overall_score, 24.242424242, places=6)
		self.assertEqual(assessments.verify_results(first.name)["matches"], True)

		second = fixtures.make_assessment(self.business, SAMPLE_ANSWERS, date="2027-01-22")
		self.assertEqual(second.scoring_model, v2.name)
		row = response(second, "STR-02")
		self.assertEqual((row.criticality, row.weight, row.question_text), ("Standard", 3, "Edited later"))
		self.assertEqual(response(second, "STR-03").weight, 20)
		# STR: YES on Standard STR-01 (3) + PARTIALLY on Standard STR-02 (1.5) + NO on Critical STR-03 (0 of 20)
		self.assertEqual(
			(department(second, "STR").earned_points, department(second, "STR").max_points), (4.5, 26)
		)

	def test_reassessment_is_a_separate_linked_record(self):
		first = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		first.submit()
		second = assessments.make_reassessment(first.name)
		second.assessment_date = "2027-01-22"
		second.insert()
		self.assertNotEqual(second.name, first.name)
		self.assertEqual((second.previous_assessment, second.business), (first.name, self.business))
		self.assertEqual(second.sequence_no, first.sequence_no + 1)
		self.assertEqual(len(second.responses), 150)
		self.assertFalse(any(r.answer for r in second.responses))
		self.assertNotEqual(
			{r.name for r in second.responses},
			{r.name for r in frappe.get_doc("BHC Assessment", first.name).responses},
		)
		first.reload()
		self.assertAlmostEqual(first.overall_score, 24.242424242, places=6)

		comparison = assessments.get_comparison(second.name)
		self.assertEqual(comparison["previous"]["name"], first.name)
		strategy = next(d for d in comparison["departments"] if d["department"] == "STR")
		self.assertAlmostEqual(strategy["previous_score"], 34.782608696, places=6)
		self.assertEqual((strategy["current_score"], strategy["current_assessed"]), (0, False))

	def test_reassessment_needs_a_finalised_source(self):
		draft = fixtures.make_assessment(self.business)
		with self.assertRaises(frappe.ValidationError):
			assessments.make_reassessment(draft.name)

	def test_previous_assessment_rules(self):
		finalised = fixtures.make_assessment(self.business)
		finalised.submit()
		other = fixtures.make_assessment(self.other_business)
		other.submit()
		draft = fixtures.make_assessment(self.business)
		cases = {
			"other business": (other.name, "2027-01-01"),
			"not finalised": (draft.name, "2027-01-01"),
			"dated later": (finalised.name, "2026-01-01"),
		}
		for label, (previous, date) in cases.items():
			with self.subTest(label):
				with self.assertRaises(frappe.ValidationError):
					fixtures.make_assessment(self.business, previous_assessment=previous, date=date)
