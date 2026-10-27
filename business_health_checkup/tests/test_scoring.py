"""Scoring engine against the formulas and cached results of Business_Health_Checkup_System.xlsx.

Expected values come from the workbook itself (SETTINGS, SCORE CALCULATION and GAP ANALYSIS as last calculated
by Excel), not from new rules. No site or database is needed; from the bench directory:

	env/bin/python -m unittest discover -s apps/business_health_checkup/business_health_checkup/tests -t apps/business_health_checkup

`bench --site <test site> run-tests --app business_health_checkup` runs them too.
"""

import json
import unittest
from datetime import date

from business_health_checkup import scoring
from business_health_checkup.scoring import NOT_ASSESSED, Question


def question_bank():
	data = json.loads((scoring.WORKBOOK_DATA / "questions.json").read_text())
	return [Question(q["question_id"], q["department"], q["criticality"]) for q in data["questions"]]


class TestWorkbookRules(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_answer_options(self):
		# SETTINGS!A5:B8 and the N/A note in SETTINGS!A9
		self.assertEqual(
			dict(self.rules.answer_fraction), {"YES": 1.0, "PARTIALLY": 0.5, "NO": 0.0, "N/A": 0.0}
		)
		self.assertEqual(self.rules.excluded_answers, {"N/A"})

	def test_criticality_weights(self):
		# SETTINGS!D5:E8
		self.assertEqual(
			dict(self.rules.criticality_weight), {"Critical": 10, "Important": 5, "Standard": 3, "Basic": 1}
		)

	def test_maturity_bands(self):
		# SETTINGS!A12:C16 (lower bounds only; column B is not used by any formula)
		self.assertEqual(
			self.rules.maturity_bands,
			(
				(0.0, "CRITICAL IMPROVEMENT REQUIRED"),
				(0.4, "DEVELOPING"),
				(0.6, "MANAGED"),
				(0.75, "STRONG MANAGEMENT"),
				(0.9, "ADVANCED"),
			),
		)

	def test_priority_rules(self):
		# SETTINGS!A19:C23 and E19:I22
		self.assertEqual(
			dict(self.rules.priority_matrix),
			{
				("Critical", "NO"): "HIGH",
				("Critical", "PARTIALLY"): "MEDIUM",
				("Important", "NO"): "MEDIUM",
				("Important", "PARTIALLY"): "MEDIUM",
				("Standard", "NO"): "LOW",
				("Standard", "PARTIALLY"): "LOW",
				("Basic", "NO"): "LOW",
				("Basic", "PARTIALLY"): "LOW",
			},
		)
		self.assertEqual(dict(self.rules.priority_rank), {"HIGH": 3, "MEDIUM": 2, "LOW": 1})
		self.assertEqual(
			dict(self.rules.priority_phase),
			{"HIGH": "0-30 Days", "MEDIUM": "31-60 Days", "LOW": "61-90 Days"},
		)
		self.assertEqual(
			dict(self.rules.priority_offsets), {"HIGH": (0, 30), "MEDIUM": (31, 60), "LOW": (61, 90)}
		)

	def test_rules_do_not_follow_later_edits_of_their_source(self):
		data = json.loads((scoring.WORKBOOK_DATA / "rules.json").read_text())
		rules = scoring.Rules.from_dict(data)
		data["criticality_weights"][0]["weight"] = 20
		with self.assertRaises(TypeError):
			rules.criticality_weight["Critical"] = 20
		self.assertEqual(rules.criticality_weight["Critical"], 10)


class TestQuestionScore(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def score(self, criticality, answer):
		return scoring.score_question(Question("T-01", "STR", criticality), answer, self.rules)

	def test_each_answer_on_a_critical_question(self):
		cases = {
			"YES": (10, 10, 0, None),
			"PARTIALLY": (5, 10, 5, "MEDIUM"),
			"NO": (0, 10, 10, "HIGH"),
			"N/A": (0, 0, 0, None),
			None: (0, 0, 0, None),
			"": (0, 0, 0, None),
		}
		for answer, (earned, max_points, gap, priority) in cases.items():
			with self.subTest(answer=answer):
				r = self.score("Critical", answer)
				self.assertEqual(
					(r.earned, r.max_points, r.gap, r.priority), (earned, max_points, gap, priority)
				)

	def test_weights_and_priority_by_criticality(self):
		cases = {
			("Important", "NO"): (0, 5, "MEDIUM"),
			("Important", "PARTIALLY"): (2.5, 5, "MEDIUM"),
			("Standard", "NO"): (0, 3, "LOW"),
			("Standard", "PARTIALLY"): (1.5, 3, "LOW"),
			("Basic", "NO"): (0, 1, "LOW"),
			("Basic", "PARTIALLY"): (0.5, 1, "LOW"),
			("Basic", "YES"): (1, 1, None),
		}
		for (criticality, answer), (earned, max_points, priority) in cases.items():
			with self.subTest(criticality=criticality, answer=answer):
				r = self.score(criticality, answer)
				self.assertEqual((r.earned, r.max_points, r.priority), (earned, max_points, priority))

	def test_na_and_blank_count_differently_as_answered(self):
		self.assertTrue(self.score("Critical", "N/A").answered)
		self.assertFalse(self.score("Critical", None).answered)

	def test_invalid_answer_is_rejected(self):
		# The workbook only offers the AnswerList dropdown; anything else is refused instead of scored.
		with self.assertRaises(ValueError):
			self.score("Critical", "MAYBE")

	def test_unknown_criticality_is_rejected(self):
		with self.assertRaises(ValueError):
			self.score("Urgent", "YES")


class TestMaturity(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_band_boundaries(self):
		cases = {
			0.0: "CRITICAL IMPROVEMENT REQUIRED",
			0.3999: "CRITICAL IMPROVEMENT REQUIRED",
			0.4: "DEVELOPING",
			0.5999: "DEVELOPING",
			0.6: "MANAGED",
			0.7499: "MANAGED",
			0.75: "STRONG MANAGEMENT",
			0.8999: "STRONG MANAGEMENT",
			0.9: "ADVANCED",
			1.0: "ADVANCED",
		}
		for score, label in cases.items():
			with self.subTest(score=score):
				self.assertEqual(scoring.maturity_label(score, self.rules), label)

	def test_band_uses_the_unrounded_score(self):
		# 199.5 / 499 = 0.3998, shown as "40%" by the 0% format, is still the lowest band.
		self.assertEqual(round(199.5 / 499, 2), 0.4)
		self.assertEqual(scoring.maturity_label(199.5 / 499, self.rules), "CRITICAL IMPROVEMENT REQUIRED")

	def test_score_below_every_band_is_rejected(self):
		with self.assertRaises(ValueError):
			scoring.maturity_label(-0.01, self.rules)


class TestAssessmentScore(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_workbook_sample_answers(self):
		# The workbook ships with five answers in Assessment 1 (STRATEGY!G7:G9, KPI!G16:G17). Expected values are
		# Excel's cached results: SCORE CALCULATION!C5:M6 and C15:M15, GAP ANALYSIS!C19:J22.
		answers = {"STR-01": "YES", "STR-02": "PARTIALLY", "STR-03": "NO", "KPI-10": "NO", "KPI-11": "NO"}
		result = scoring.score_assessment(question_bank(), answers, self.rules)

		strategy = result.departments["STR"]
		self.assertEqual(
			(strategy.questions, strategy.answered, strategy.earned, strategy.max_points), (15, 3, 8, 23)
		)
		self.assertAlmostEqual(strategy.score, 0.34782608695652173, places=15)
		self.assertAlmostEqual(strategy.completion, 0.2, places=15)
		self.assertEqual(strategy.maturity, "CRITICAL IMPROVEMENT REQUIRED")
		self.assertEqual((strategy.high, strategy.medium, strategy.low), (1, 1, 0))

		kpi = result.departments["KPI"]
		self.assertEqual((kpi.answered, kpi.earned, kpi.max_points, kpi.score), (2, 0, 10, 0))
		self.assertEqual(kpi.maturity, "CRITICAL IMPROVEMENT REQUIRED")
		self.assertEqual((kpi.high, kpi.medium, kpi.low), (0, 2, 0))

		for code in ("HR", "MKT", "SAL", "PUR", "PRD", "QA", "MNT", "INV"):
			with self.subTest(department=code):
				summary = result.departments[code]
				self.assertEqual((summary.answered, summary.score, summary.maturity), (0, 0, NOT_ASSESSED))
				self.assertFalse(summary.assessed)

		overall = result.overall
		self.assertEqual(
			(overall.questions, overall.answered, overall.earned, overall.max_points), (150, 5, 8, 33)
		)
		self.assertAlmostEqual(overall.score, 0.24242424242424243, places=15)
		self.assertAlmostEqual(overall.completion, 0.03333333333333333, places=15)
		self.assertEqual(overall.maturity, "CRITICAL IMPROVEMENT REQUIRED")
		self.assertEqual((overall.high, overall.medium, overall.low, overall.total_gaps), (1, 3, 0, 4))

		ranked = scoring.rank_gaps(result.questions, self.rules)
		self.assertEqual(
			[(r.question_id, r.priority, r.gap) for r in ranked],
			[
				("STR-03", "HIGH", 10),
				("STR-02", "MEDIUM", 5),
				("KPI-10", "MEDIUM", 5),
				("KPI-11", "MEDIUM", 5),
			],
		)
		self.assertEqual(sum(r.gap for r in result.questions), 25)  # GAP ANALYSIS!F4

	def test_na_and_unanswered_are_left_out_of_the_department_score(self):
		questions = [
			Question("A-01", "A", "Standard"),
			Question("A-02", "A", "Critical"),
			Question("A-03", "A", "Critical"),
			Question("A-04", "A", "Important"),
			Question("A-05", "A", "Important"),
		]
		answers = {"A-01": "YES", "A-02": "PARTIALLY", "A-03": "NO", "A-04": "N/A"}
		summary = scoring.score_assessment(questions, answers, self.rules).departments["A"]
		self.assertEqual((summary.earned, summary.max_points, summary.answered), (8, 23, 4))
		self.assertAlmostEqual(summary.score, 8 / 23)
		self.assertAlmostEqual(summary.completion, 4 / 5)

	def test_overall_score_is_weighted_by_applicable_points(self):
		questions = [
			Question("A-01", "A", "Critical"),
			*(Question(f"B-0{i}", "B", "Critical") for i in range(1, 4)),
		]
		answers = {"A-01": "YES", "B-01": "NO", "B-02": "NO", "B-03": "NO"}
		result = scoring.score_assessment(questions, answers, self.rules)
		self.assertEqual((result.departments["A"].score, result.departments["B"].score), (1.0, 0.0))
		self.assertAlmostEqual(result.overall.score, 10 / 40)  # not the 0.5 average of the two departments

	def test_unanswered_assessment(self):
		result = scoring.score_assessment(question_bank(), {}, self.rules)
		self.assertEqual((result.overall.score, result.overall.completion), (0, 0))
		self.assertEqual(result.overall.maturity, NOT_ASSESSED)
		self.assertEqual(result.overall.total_gaps, 0)
		self.assertEqual(scoring.rank_gaps(result.questions, self.rules), [])

	def test_all_not_applicable(self):
		questions = [Question("A-01", "A", "Critical"), Question("A-02", "A", "Basic")]
		summary = scoring.score_assessment(questions, {"A-01": "N/A", "A-02": "N/A"}, self.rules).overall
		self.assertEqual(
			(summary.answered, summary.completion, summary.max_points, summary.score), (2, 1, 0, 0)
		)
		self.assertEqual(summary.maturity, NOT_ASSESSED)

	def test_no_questions(self):
		result = scoring.score_assessment([], {}, self.rules)
		self.assertEqual((result.overall.questions, result.overall.completion), (0, 0))
		self.assertEqual(dict(result.departments), {})

	def test_score_depends_only_on_the_snapshot_passed_in(self):
		# A later change of a question's criticality in the master must not change an assessment that was scored
		# with its stored snapshot.
		answers = {"A-01": "PARTIALLY"}
		before = scoring.score_assessment([Question("A-01", "A", "Critical")], answers, self.rules)
		after_master_edit = scoring.score_assessment([Question("A-01", "A", "Standard")], answers, self.rules)
		again = scoring.score_assessment([Question("A-01", "A", "Critical")], answers, self.rules)
		self.assertEqual(before, again)
		self.assertNotEqual(before.overall.max_points, after_master_edit.overall.max_points)


class TestGapRanking(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_priority_then_points_lost_then_question_order(self):
		questions = [
			Question("Q-1", "A", "Standard"),  # NO -> LOW, 3 points
			Question("Q-2", "A", "Important"),  # NO -> MEDIUM, 5 points
			Question("Q-3", "A", "Critical"),  # PARTIALLY -> MEDIUM, 5 points (ties Q-2, comes after it)
			Question("Q-4", "A", "Important"),  # PARTIALLY -> MEDIUM, 2.5 points
			Question("Q-5", "A", "Critical"),  # NO -> HIGH, 10 points
			Question("Q-6", "A", "Critical"),  # YES -> no gap
		]
		answers = {
			"Q-1": "NO",
			"Q-2": "NO",
			"Q-3": "PARTIALLY",
			"Q-4": "PARTIALLY",
			"Q-5": "NO",
			"Q-6": "YES",
		}
		result = scoring.score_assessment(questions, answers, self.rules)
		ranked = [r.question_id for r in scoring.rank_gaps(result.questions, self.rules)]
		self.assertEqual(ranked, ["Q-5", "Q-2", "Q-3", "Q-4", "Q-1"])


class TestSuggestedDates(unittest.TestCase):
	def test_offsets_from_the_assessment_date(self):
		rules = scoring.load_workbook_rules()
		assessed = date(2026, 10, 24)
		# SCORE CALCULATION!T26:U26 shows 24-Nov-2026 / 23-Dec-2026 for the MEDIUM gap on 24-Oct-2026.
		self.assertEqual(
			scoring.suggested_dates("HIGH", assessed, rules), (date(2026, 10, 24), date(2026, 11, 23))
		)
		self.assertEqual(
			scoring.suggested_dates("MEDIUM", assessed, rules), (date(2026, 11, 24), date(2026, 12, 23))
		)
		self.assertEqual(
			scoring.suggested_dates("LOW", assessed, rules), (date(2026, 12, 24), date(2027, 1, 22))
		)


class TestGrowthStatus(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_thresholds_from_settings(self):
		# SETTINGS!B27 and B28
		self.assertEqual((self.rules.growth_plan_threshold, self.rules.strength_threshold), (0.6, 0.75))

	def test_boundaries(self):
		cases = {
			0.5999: "PRIORITY - GROWTH PLAN",
			0.6: "MAINTAIN & IMPROVE",
			0.7499: "MAINTAIN & IMPROVE",
			0.75: "STRENGTH - LEVERAGE",
			1.0: "STRENGTH - LEVERAGE",
		}
		for score, status in cases.items():
			with self.subTest(score=score):
				self.assertEqual(scoring.growth_status(score, self.rules), status)

	def test_workbook_sample(self):
		# BUSINESS GROWTH PLAN!E8:E17 as cached: STR (34.8 %), KPI (0 %) and the eight departments without answers
		# (score 0) are all "PRIORITY - GROWTH PLAN" -- workbook behaviour kept on purpose, see W-01 / Q-04.
		answers = {"STR-01": "YES", "STR-02": "PARTIALLY", "STR-03": "NO", "KPI-10": "NO", "KPI-11": "NO"}
		result = scoring.score_assessment(question_bank(), answers, self.rules)
		statuses = {
			code: scoring.growth_status(s.score, self.rules) for code, s in result.departments.items()
		}
		self.assertEqual(set(statuses.values()), {"PRIORITY - GROWTH PLAN"})
		self.assertEqual(len(statuses), 10)

	def test_rules_without_thresholds(self):
		data = json.loads((scoring.WORKBOOK_DATA / "rules.json").read_text())
		del data["growth_plan_threshold"], data["strength_threshold"]
		rules = scoring.Rules.from_dict(data)
		self.assertIsNone(rules.growth_plan_threshold)
		with self.assertRaises(ValueError):
			scoring.growth_status(0.5, rules)


class TestDepartmentRanking(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_workbook_sample(self):
		# SCORE CALCULATION!U5:U14 as cached: KPI (0 %, assessed) is weakest, the eight unanswered departments
		# follow in sheet order, STR (34.8 %) is strongest.
		answers = {"STR-01": "YES", "STR-02": "PARTIALLY", "STR-03": "NO", "KPI-10": "NO", "KPI-11": "NO"}
		result = scoring.score_assessment(question_bank(), answers, self.rules)
		ranks = scoring.rank_departments([(code, s.score) for code, s in result.departments.items()])
		self.assertEqual(
			ranks,
			{
				"STR": 10,
				"KPI": 1,
				"HR": 2,
				"MKT": 3,
				"SAL": 4,
				"PUR": 5,
				"PRD": 6,
				"QA": 7,
				"MNT": 8,
				"INV": 9,
			},
		)

	def test_ties_follow_department_order(self):
		self.assertEqual(
			scoring.rank_departments([("A", 0.5), ("B", 0.5), ("C", 0.2)]), {"C": 1, "A": 2, "B": 3}
		)

	def test_tie_key_resolution_matches_the_workbook(self):
		# T = score + ROW()/1000000: a score only 4e-7 higher on an earlier row still ranks weaker (W-09).
		self.assertEqual(scoring.rank_departments([("A", 0.5000004), ("B", 0.5)]), {"A": 1, "B": 2})
		self.assertEqual(scoring.rank_departments([("A", 0.50001), ("B", 0.5)]), {"B": 1, "A": 2})

	def test_empty(self):
		self.assertEqual(scoring.rank_departments([]), {})


class TestRepeatedProblemArea(unittest.TestCase):
	def test_gap_analysis_h7(self):
		cases = {
			(3, 3): "YES - 3+ HIGH gaps: systemic weakness",
			(5, 12): "YES - 3+ HIGH gaps: systemic weakness",
			(2, 8): "YES - many gaps in one function",
			(0, 9): "YES - many gaps in one function",
			(2, 7): "",
			(0, 0): "",
		}
		for (high, total), expected in cases.items():
			with self.subTest(high=high, total=total):
				self.assertEqual(scoring.repeated_problem_area(high, total), expected)
