"""Phase 5: Management Report (print format) and Owner Dashboard, against the workbook's cached results for its
sample answers (MANAGEMENT REPORT!A2, B13, B17:F26, B45:G47, A51:H60, B64:E66, A70:H84, B101:D106, B113;
OWNER DASHBOARD!A5:O5, A9:F19, A24:D27).

Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_management
"""

import frappe
from frappe.www.printview import get_html_and_style

from business_health_checkup import actions, assessments, management
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS

ACTION = "BHC Improvement Action"
PRINT_FORMAT = "BHC Management Report"
SECOND_ANSWERS = {"STR-01": "YES", "STR-02": "YES", "STR-03": "PARTIALLY", "KPI-10": "NO", "KPI-11": "NO"}
COUNTED = ("BHC Assessment", "BHC Assessment Response", "BHC Improvement Action", "BHC Business", "Version")


class ManagementTestCase(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()
		cls.business = fixtures.make_business("Alpha Forgings Pvt Ltd")
		frappe.db.set_value("BHC Business", cls.business, "consultancy_firm", "Advice Consultancy")

	def finalised(self, answers=SAMPLE_ANSWERS):
		doc = fixtures.make_assessment(self.business, answers)
		doc.submit()
		return doc

	def snapshot(self):
		return (
			{d: frappe.db.count(d) for d in COUNTED},
			frappe.db.sql("select name, modified from `tabBHC Assessment` order by name"),
			frappe.db.sql("select name, modified from `tabBHC Improvement Action` order by name"),
		)


class TestManagementReport(ManagementTestCase):
	def test_workbook_sample(self):
		doc = self.finalised()
		r = management.get_management_report(doc.name)

		h = r["header"]
		self.assertEqual((h["consultant"], h["consultancy_firm"]), ("Administrator", "Advice Consultancy"))
		self.assertEqual(
			(h["assessment_label"], h["assessment_date_text"]), ("Assessment 1 - Baseline", "24 October 2026")
		)
		self.assertEqual(r["profile"]["company"], "Alpha Forgings Pvt Ltd")

		# §2 B11:H11 and B13
		o = r["overall"]
		self.assertEqual(
			(o["score_text"], o["maturity"], o["answered"], o["gaps"]),
			("24%", "CRITICAL IMPROVEMENT REQUIRED", "5 / 150", "1 / 3 / 0"),
		)
		self.assertEqual(
			o["position"],
			"Current position: Alpha Forgings Pvt Ltd scores 24% - maturity level CRITICAL IMPROVEMENT REQUIRED. "
			"This is the baseline assessment.",
		)

		# §3 B17:F26: STR "Critical" (MatShort), unassessed "-" (stored 0 %, shown as not assessed)
		departments = {d["department"]: d for d in r["departments"]}
		self.assertEqual(
			(
				departments["STR"]["label"],
				departments["STR"]["score_text"],
				departments["STR"]["short_maturity"],
			),
			("Strategy", "35%", "Critical"),
		)
		self.assertEqual(
			(departments["KPI"]["short_maturity"], departments["KPI"]["assessed"]), ("Critical", True)
		)
		self.assertEqual((departments["HR"]["short_maturity"], departments["HR"]["assessed"]), (None, False))
		self.assertEqual({d["previous_text"] for d in r["departments"]}, {""})

		# §4 B45:D47 = ranks 10, 9, 8 and G45
		self.assertEqual([d["department"] for d in r["strengths"]], ["STR", "INV", "MNT"])
		self.assertEqual([d["assessed"] for d in r["strengths"]], [True, False, False])
		self.assertEqual(r["critical_practices"], "Critical-weight practices fully in place: 0 of 2 answered")

		# §5 A51:H54
		self.assertEqual(
			[(g["no"], g["question_code"], g["priority"]) for g in r["critical_gaps"]],
			[
				(1, "STR-03", "HIGH"),
				(2, "STR-02", "MEDIUM"),
				(3, "KPI-10", "MEDIUM"),
				(4, "KPI-11", "MEDIUM"),
			],
		)
		self.assertTrue(r["critical_gaps"][0]["business_risk"].startswith("Nobody knows in July"))

		# §6 B64:E66 = ranks 1, 2, 3
		self.assertEqual(
			[(d["department"], d["total_gaps"]) for d in r["priority_areas"]],
			[("KPI", 2), ("HR", 0), ("MKT", 0)],
		)
		self.assertTrue(
			r["priority_areas"][0]["business_risk"].startswith("Without KPIs and a monthly review")
		)

		# §7 A70:H73: no action yet -> recommendation, "(to be assigned)", suggested due date
		first = r["action_plan"][0]
		self.assertEqual(
			(first["question_code"], first["phase"], first["responsible"], first["due_date_text"]),
			("STR-03", "0-30 Days", "(to be assigned)", "23-Nov-2026"),
		)
		self.assertEqual((first["action"], first["due_is_agreed"]), (None, False))
		self.assertEqual(r["action_plan"][1]["due_date_text"], "23-Dec-2026")

		# §8: not recorded in the system
		self.assertFalse(r["kpi"]["available"])

		# §9 B101:B105 (ranks 1-5, all below 0.6) with the first three steps of D101, and B106
		self.assertEqual([d["department"] for d in r["roadmap"]], ["KPI", "HR", "MKT", "SAL", "PUR"])
		self.assertEqual(
			r["roadmap"][0]["steps"],
			[
				"Define 3-6 KPIs per department with formula, source, frequency and owner",
				"Set a numeric target for every KPI for the current year",
				"Build the owner's one-page 10-number dashboard",
			],
		)
		self.assertEqual(r["roadmap_summary"], "Departments in growth programme: 10 of 10.")

		# §10 B113
		self.assertEqual(
			r["next_reassessment"],
			"Next re-assessment recommended: 22-Jan-2027 (after completion of the 90-day plan).",
		)
		self.assertIn("<svg", r["charts"]["radar"])
		self.assertIn("not assessed", r["charts"]["bar"])

	def test_actions_are_shown_apart_from_recommendations(self):
		doc = self.finalised()
		created = actions.create_actions(doc.name, ["STR-03"], responsible="Plant head")
		action = frappe.get_doc(ACTION, created[0]["action"])
		action.update({"action_description": "Monthly target review", "target_date": "2026-11-10"})
		action.save()
		rows = {a["question_code"]: a for a in management.get_management_report(doc.name)["action_plan"]}
		self.assertEqual(
			(
				rows["STR-03"]["agreed_action"],
				rows["STR-03"]["responsible"],
				rows["STR-03"]["due_date_text"],
				rows["STR-03"]["due_is_agreed"],
			),
			("Monthly target review", "Plant head", "10-Nov-2026", True),
		)
		self.assertTrue(rows["STR-03"]["recommendation"].startswith("Fix the annual turnover target"))
		self.assertEqual((rows["STR-02"]["action"], rows["STR-02"]["due_is_agreed"]), (None, False))

	def test_change_against_the_previous_assessment(self):
		first = self.finalised()
		second = assessments.make_reassessment(first.name)
		second.assessment_date = "2027-01-22"
		second.insert()
		fixtures.set_answers(second, SECOND_ANSWERS)
		second.save()
		r = management.get_management_report(second.name)
		# 18/33 - 8/33 = +30.3 points
		self.assertTrue(
			r["overall"]["position"].endswith("Change since previous assessment: +30 percentage points.")
		)
		departments = {d["department"]: d for d in r["departments"]}
		self.assertEqual(
			(departments["STR"]["previous_text"], departments["STR"]["change_text"]), ("35%", "+43")
		)
		self.assertEqual((departments["KPI"]["change_text"], departments["HR"]["change_text"]), ("0", ""))
		self.assertIn(
			"Status: Draft", frappe.get_print("BHC Assessment", second.name, print_format=PRINT_FORMAT)
		)

	def test_no_answers(self):
		doc = fixtures.make_assessment(self.business)
		r = management.get_management_report(doc.name)
		self.assertEqual(
			(r["overall"]["score_text"], r["overall"]["maturity"], r["overall"]["answered"]),
			("0%", "Not Assessed", "0 / 150"),
		)
		self.assertEqual((r["critical_gaps"], r["action_plan"], r["total_gaps"]), ([], [], 0))
		self.assertEqual({d["assessed"] for d in r["departments"]}, {False})
		self.assertEqual(r["critical_practices"], "Critical-weight practices fully in place: 0 of 0 answered")

	def test_cancelled_assessment(self):
		doc = self.finalised()
		doc.cancel()
		self.assertEqual(management.get_management_report(doc.name)["header"]["status"], "Cancelled")

	def test_print_format_renders_the_sections(self):
		doc = self.finalised()
		html = get_html_and_style("BHC Assessment", doc.name, print_format=PRINT_FORMAT, no_letterhead=1)[
			"html"
		]
		for text in (
			"MANAGEMENT REPORT",
			"1. COMPANY PROFILE",
			"10. CONSULTANT REMARKS",
			"Alpha Forgings Pvt Ltd",
			"This is the baseline assessment.",
			"Critical-weight practices fully in place: 0 of 2 answered",
			"Departments in growth programme: 10 of 10.",
			"(to be assigned)",
			"(suggested)",
			"not assessed",
			"<svg",
			"Signature",
		):
			self.assertIn(text, html)
		self.assertNotIn("not finalised", html)

	def test_text_is_escaped_in_the_print(self):
		frappe.db.set_value("BHC Business", self.business, "location", "<script>alert(1)</script>")
		doc = self.finalised()
		doc.db_set("consultant_remarks", "<img src=x onerror=alert(1)>")
		html = frappe.get_print("BHC Assessment", doc.name, print_format=PRINT_FORMAT)
		self.assertNotIn("<script>alert(1)</script>", html)
		self.assertNotIn("<img src=x", html)
		self.assertIn("&lt;script&gt;", html)

	def test_viewing_writes_nothing(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		before = self.snapshot()
		management.get_management_report(doc.name)
		management.get_owner_dashboard(doc.name)
		frappe.get_print("BHC Assessment", doc.name, print_format=PRINT_FORMAT)
		self.assertEqual(self.snapshot(), before)


class TestOwnerDashboard(ManagementTestCase):
	def test_workbook_sample(self):
		doc = self.finalised()
		d = management.get_owner_dashboard(doc.name)
		c = d["cards"]
		# A5:K5
		self.assertEqual(
			(c["score_text"], c["maturity"], c["answered"]),
			("24%", "CRITICAL IMPROVEMENT REQUIRED", "5 / 150"),
		)
		self.assertEqual((c["high_gaps"], c["medium_gaps"], c["low_gaps"]), (1, 3, 0))
		# M5 / O5 over created actions: none yet
		self.assertEqual(
			(c["actions_open"], c["actions_completed"], c["gaps_with_action"]), (0, "0 (0%)", "0 / 4")
		)
		heat = {r["department"]: r for r in d["heat_map"]}
		self.assertEqual(
			(heat["STR"]["score_text"], heat["STR"]["short_maturity"], heat["STR"]["total_gaps"]),
			("35%", "Critical", 2),
		)
		self.assertEqual(
			(heat["HR"]["assessed"], heat["HR"]["color"]), (False, management.NOT_ASSESSED_COLOR)
		)
		self.assertEqual(heat["STR"]["color"], management.BAND_COLORS[0])  # below 40 %
		self.assertEqual((d["overall_row"]["total_gaps"], d["overall_row"]["previous_text"]), (4, ""))
		self.assertEqual(
			[(t["name"], t["score_text"], t["answered_questions"]) for t in d["trend"]],
			[(doc.name, "24%", 5)],
		)
		self.assertFalse(d["kpi"]["available"])
		self.assertTrue(all(d["charts"][k] for k in ("bar", "radar", "trend")))

	def test_action_cards(self):
		doc = self.finalised()
		created = actions.create_actions(doc.name, ["STR-03", "STR-02"])
		done = frappe.get_doc(ACTION, created[0]["action"])
		done.status = "Completed"
		done.save()
		late = frappe.get_doc(ACTION, created[1]["action"])
		late.target_date = frappe.utils.add_days(frappe.utils.today(), -1)
		late.save()
		c = management.get_owner_dashboard(doc.name)["cards"]
		self.assertEqual(
			(c["actions_open"], c["actions_completed"], c["actions_overdue"], c["gaps_with_action"]),
			(1, "1 (50%)", 1, "2 / 4"),
		)

	def test_trend_and_unanswered_reassessment(self):
		first = self.finalised()
		second = assessments.make_reassessment(first.name)
		second.assessment_date = "2027-01-22"
		second.insert()
		d = management.get_owner_dashboard(second.name)
		# B24: "-" for an assessment with nothing answered; it is not drawn in the trend line
		self.assertEqual(
			[(t["name"], t["score_text"], t["current"]) for t in d["trend"]],
			[(first.name, "24%", False), (second.name, "-", True)],
		)
		self.assertNotIn("Assessment 2", d["charts"]["trend"])
		self.assertEqual(d["overall_row"]["change_text"], "")  # nothing applicable answered now: no change
		self.assertIn(
			"Nothing applicable was answered in the current assessment", d["overall_row"]["limitations"]
		)

	def test_unknown_assessment(self):
		with self.assertRaises(frappe.DoesNotExistError):
			management.get_owner_dashboard("BHC-ASM-1999-99999")
		with self.assertRaises(frappe.DoesNotExistError):
			management.get_management_report("")
