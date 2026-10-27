"""Phase 4: improvement actions, their lifecycle and history, and the 90 Day Plan report.

Expected values come from the workbook: the sample gaps (GAP ANALYSIS!A19:N22), SETTINGS!E20:I22 (phases, start
and due days) counted from the sample's assessment date 24-Oct-2026, and ACTION PLAN!A4:G4 / Q8.
Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_actions
"""

from datetime import date

import frappe
from frappe.desk.query_report import run
from frappe.utils import add_days, getdate, today

from business_health_checkup import actions, assessments
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS

ACTION = "BHC Improvement Action"
MANAGER = "bhc-action-manager@example.com"
CONSULTANT = "bhc-action-consultant@example.com"
OUTSIDER = "bhc-action-outsider@example.com"
ADMIN = "bhc-action-admin@example.com"
# Sample gaps in gap order with priority, phase and suggested start / due (day 0/30, 31/60)
SAMPLE_GAPS = [
	("STR-03", "HIGH", "0-30 Days", date(2026, 10, 24), date(2026, 11, 23)),
	("STR-02", "MEDIUM", "31-60 Days", date(2026, 11, 24), date(2026, 12, 23)),
	("KPI-10", "MEDIUM", "31-60 Days", date(2026, 11, 24), date(2026, 12, 23)),
	("KPI-11", "MEDIUM", "31-60 Days", date(2026, 11, 24), date(2026, 12, 23)),
]


class ActionTestCase(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()
		fixtures.make_user(MANAGER, "BHC Manager")
		fixtures.make_user(CONSULTANT, "BHC Consultant")
		fixtures.make_user(OUTSIDER, "BHC Consultant")
		fixtures.make_user(ADMIN, "System Manager")
		cls.business = fixtures.make_business("Action Test Ltd", [MANAGER, CONSULTANT])
		cls.other_business = fixtures.make_business("Other Action Ltd", [OUTSIDER])

	def as_user(self, user):
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")

	def finalised(self, answers=SAMPLE_ANSWERS, date=fixtures.SAMPLE_DATE, business=None):
		doc = fixtures.make_assessment(business or self.business, answers, date=date)
		doc.submit()
		return doc

	def action(self, assessment, code):
		name = frappe.db.get_value(ACTION, {"assessment": assessment.name, "question_code": code})
		return frappe.get_doc(ACTION, name)

	def count(self, assessment):
		return frappe.db.count(ACTION, {"assessment": assessment.name})


class TestCreatingActions(ActionTestCase):
	def test_a_gap_is_not_an_action(self):
		doc = self.finalised()
		self.assertEqual(self.count(doc), 0)
		rows = run("BHC Gap Analysis", filters={"assessment": doc.name})["result"]
		self.assertEqual(len(rows), 4)
		self.assertEqual({r["improvement_action"] for r in rows}, {None})

	def test_eligible_gaps(self):
		doc = self.finalised()
		gaps = actions.get_eligible_gaps(doc.name)
		self.assertEqual(
			[
				(
					g["question_code"],
					g["priority"],
					g["phase"],
					g["suggested_start_date"],
					g["suggested_due_date"],
				)
				for g in gaps
			],
			SAMPLE_GAPS,
		)
		self.assertEqual({g["action"] for g in gaps}, {None})

	def test_create_selected_gaps(self):
		doc = self.finalised()
		results = actions.create_actions(doc.name, ["STR-03", "KPI-10"])
		self.assertEqual(
			[(r["question_code"], r["created"]) for r in results], [("STR-03", True), ("KPI-10", True)]
		)
		self.assertEqual(self.count(doc), 2)

		action = self.action(doc, "STR-03")
		row = fixtures.response(doc, "STR-03")
		self.assertEqual(
			(action.business, action.assessment, getdate(action.assessment_date), action.scoring_model),
			(self.business, doc.name, date(2026, 10, 24), doc.scoring_model),
		)
		self.assertEqual(
			(action.question, action.question_code, action.department, action.question_text, action.answer),
			("STR-03", "STR-03", "STR", row.question_text, "NO"),
		)
		self.assertEqual(
			(
				action.criticality,
				action.weight,
				action.gap_points,
				action.gap_rank,
				action.priority,
				action.phase,
			),
			("Critical", 10, 10, 1, "HIGH", "0-30 Days"),
		)
		self.assertEqual(
			(getdate(action.suggested_start_date), getdate(action.suggested_due_date)),
			(date(2026, 10, 24), date(2026, 11, 23)),
		)
		self.assertTrue(action.recommendation.startswith("Fix the annual turnover target"))
		self.assertEqual(action.kpi, "Turnover achievement % vs target")
		self.assertTrue(action.business_risk.startswith("Nobody knows in July"))
		self.assertEqual(action.action_description, action.recommendation)
		self.assertEqual(
			(action.start_date, action.target_date, action.status, action.completed_on),
			(None, None, "Open", None),
		)
		self.assertEqual(action.scoring_model_version, "Workbook v1")

		kpi = self.action(doc, "KPI-10")
		self.assertEqual((kpi.priority, kpi.phase, kpi.gap_rank), ("MEDIUM", "31-60 Days", 3))

	def test_low_priority_boundaries_and_confirmed_dates(self):
		doc = self.finalised({"STR-01": "NO"})  # Standard NO -> LOW
		actions.create_actions(doc.name, ["STR-01"], use_suggested_dates=1)
		action = self.action(doc, "STR-01")
		self.assertEqual((action.priority, action.phase), ("LOW", "61-90 Days"))
		self.assertEqual(
			(getdate(action.suggested_start_date), getdate(action.suggested_due_date)),
			(date(2026, 12, 24), date(2027, 1, 22)),  # day 61 and day 90
		)
		self.assertEqual(
			(getdate(action.start_date), getdate(action.target_date)), (date(2026, 12, 24), date(2027, 1, 22))
		)

	def test_suggested_dates_are_not_agreed_dates_unless_asked(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		actions.create_actions(doc.name, ["STR-02"], use_suggested_dates=1)
		self.assertEqual(
			(self.action(doc, "STR-03").start_date, self.action(doc, "STR-03").target_date), (None, None)
		)
		confirmed = self.action(doc, "STR-02")
		self.assertEqual(
			(getdate(confirmed.start_date), getdate(confirmed.target_date)),
			(date(2026, 11, 24), date(2026, 12, 23)),
		)

	def test_retry_returns_the_existing_action(self):
		doc = self.finalised()
		first = actions.create_actions(doc.name, ["STR-03"])
		again = actions.create_actions(doc.name, ["STR-03", "STR-02", "STR-03"])
		self.assertEqual(
			[(r["question_code"], r["created"]) for r in again], [("STR-03", False), ("STR-02", True)]
		)
		self.assertEqual(again[0]["action"], first[0]["action"])
		self.assertEqual(self.count(doc), 2)

	def test_a_second_action_for_the_same_gap_is_refused(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		with self.assertRaises(frappe.UniqueValidationError):
			frappe.get_doc({"doctype": ACTION, "assessment": doc.name, "question": "STR-03"}).insert()
		self.assertEqual(self.count(doc), 1)

	def test_invalid_selections_create_nothing(self):
		doc = self.finalised({**SAMPLE_ANSWERS, "STR-04": "N/A"})
		for label, questions in {
			"answered YES": ["STR-03", "STR-01"],
			"answered N/A": ["STR-04"],
			"unanswered": ["HR-01"],
			"unknown": ["ZZZ-99"],
			"nothing": [],
		}.items():
			with self.subTest(label):
				with self.assertRaises(frappe.ValidationError):
					actions.create_actions(doc.name, questions)
				self.assertEqual(self.count(doc), 0)

	def test_a_failure_part_way_creates_nothing_and_a_retry_works(self):
		doc = self.finalised()
		with self.assertRaises(frappe.ValidationError):
			actions.create_actions(doc.name, ["STR-03", "STR-02"], responsible_user=OUTSIDER)
		self.assertEqual(self.count(doc), 0)
		self.assertEqual(
			len(actions.create_actions(doc.name, ["STR-03", "STR-02"], responsible_user=CONSULTANT)), 2
		)

	def test_only_finalised_assessments(self):
		draft = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		with self.assertRaises(frappe.ValidationError):
			actions.create_actions(draft.name, ["STR-03"])
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": ACTION, "assessment": draft.name, "question": "STR-03"}).insert()
		cancelled = self.finalised()
		cancelled.cancel()
		with self.assertRaises(frappe.ValidationError):
			actions.create_actions(cancelled.name, ["STR-03"])
		with self.assertRaises(frappe.DoesNotExistError):
			actions.create_actions("BHC-ASM-1999-99999", ["STR-03"])

	def test_values_sent_by_the_caller_are_replaced(self):
		doc = self.finalised()
		action = frappe.get_doc(
			{
				"doctype": ACTION,
				"assessment": doc.name,
				"question": "STR-03",
				"business": self.other_business,
				"priority": "LOW",
				"phase": "anything",
				"question_text": "forged",
				"gap_rank": 99,
				"suggested_due_date": "2030-01-01",
				"source_key": "forged",
				"completed_on": "2020-01-01",
			}
		).insert()
		self.assertEqual(
			(
				action.business,
				action.priority,
				action.phase,
				action.gap_rank,
				getdate(action.suggested_due_date),
			),
			(self.business, "HIGH", "0-30 Days", 1, date(2026, 11, 23)),
		)
		self.assertEqual(action.question_text, fixtures.response(doc, "STR-03").question_text)
		self.assertEqual(action.business_name, "Action Test Ltd")
		self.assertEqual((action.source_key, action.completed_on), (f"{doc.name}|STR-03", None))

	def test_source_fields_cannot_be_edited(self):
		doc = self.finalised()
		other = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		action = self.action(doc, "STR-03")
		for field, value in {
			"priority": "LOW",
			"phase": "61-90 Days",
			"question_text": "edited",
			"recommendation": "edited",
			"suggested_due_date": "2027-01-01",
			"gap_rank": 7,
			"business": self.other_business,
			"assessment": other.name,
			"question": "STR-02",
		}.items():
			with self.subTest(field):
				action.reload()
				action.set(field, value)
				with self.assertRaises(frappe.ValidationError):
					action.save()

	def test_missing_assessment_date_gives_no_suggested_dates(self):
		doc = self.finalised()
		frappe.db.set_value("BHC Assessment", doc.name, "assessment_date", None, update_modified=False)
		actions.create_actions(doc.name, ["STR-03"], use_suggested_dates=1)
		action = self.action(doc, "STR-03")
		self.assertEqual((action.priority, action.phase), ("HIGH", "0-30 Days"))
		self.assertEqual(
			(action.suggested_start_date, action.suggested_due_date, action.start_date, action.target_date),
			(None, None, None, None),
		)


class TestPlanAndStatus(ActionTestCase):
	def new_action(self, code="STR-03"):
		doc = self.finalised()
		actions.create_actions(doc.name, [code])
		return self.action(doc, code)

	def test_agreed_dates(self):
		action = self.new_action()
		for start, target in (("2000-01-01", None), (None, "2000-01-01"), ("2026-11-10", "2026-11-09")):
			with self.subTest(start=start, target=target):
				action.reload()
				action.start_date, action.target_date = start, target
				with self.assertRaises(frappe.ValidationError):
					action.save()
		action.reload()
		action.start_date, action.target_date = "2000-01-02", "2000-01-02"
		action.save()
		self.assertEqual(getdate(action.target_date), date(2000, 1, 2))

	def test_status_values(self):
		action = self.new_action()
		action.status = "Cancelled"
		with self.assertRaises(frappe.ValidationError):
			action.save()

	def test_completion_date_is_set_by_the_server(self):
		action = self.new_action()
		action.status = "In Progress"
		action.save()
		self.assertIsNone(action.completed_on)
		action.status = "Completed"
		action.completed_on = "2020-01-01"
		action.save()
		self.assertEqual(getdate(action.completed_on), getdate(today()))
		# The original completion date stays when the completed action is edited later.
		frappe.db.set_value(ACTION, action.name, "completed_on", "2026-11-01", update_modified=False)
		action.reload()
		action.remarks = "Evidence filed"
		action.completed_on = today()
		action.save()
		self.assertEqual(getdate(action.completed_on), date(2026, 11, 1))
		action.status = "Hold"
		action.save()  # Administrator may reopen
		self.assertIsNone(action.completed_on)

	def test_reopening_needs_a_manager(self):
		action = self.new_action()
		self.as_user(CONSULTANT)
		action = frappe.get_doc(ACTION, action.name)
		action.status = "Completed"
		action.save()
		action.status = "In Progress"
		with self.assertRaises(frappe.PermissionError):
			action.save()
		frappe.set_user(MANAGER)
		action = frappe.get_doc(ACTION, action.name)
		action.status = "In Progress"
		action.save(ignore_version=False)  # Frappe skips version logs in tests unless asked
		self.assertIsNone(action.completed_on)
		frappe.set_user("Administrator")
		versions = frappe.get_all(
			"Version", filters={"ref_doctype": ACTION, "docname": action.name}, pluck="data"
		)
		self.assertEqual(len(versions), 1)
		changed = dict((field, (old, new)) for field, old, new in frappe.parse_json(versions[0])["changed"])
		self.assertEqual(changed["status"], ("Completed", "In Progress"))
		self.assertIsNotNone(changed["completed_on"][0])  # the old completion date is kept in the history

	def test_responsible_user(self):
		action = self.new_action()
		action.responsible_user = CONSULTANT
		action.save()
		self.assertEqual(action.responsible, frappe.db.get_value("User", CONSULTANT, "full_name"))
		for user in (OUTSIDER, "nobody@example.com"):
			with self.subTest(user):
				action.reload()
				action.responsible_user = user
				with self.assertRaises(frappe.ValidationError):
					action.save()
		frappe.db.set_value("User", MANAGER, "enabled", 0)
		action.reload()
		action.responsible_user = MANAGER
		with self.assertRaises(frappe.ValidationError):
			action.save()
		action.reload()
		action.responsible_user = ADMIN  # System Manager: sees every business
		action.save()

	def test_free_text_responsible_without_a_login(self):
		action = self.new_action()
		action.responsible = "Plant head, Unit 2"
		action.save()
		self.assertEqual((action.responsible, action.responsible_user), ("Plant head, Unit 2", None))


class TestHistory(ActionTestCase):
	def test_master_and_scoring_changes_leave_actions_alone(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		before = self.action(doc, "STR-03").as_dict()

		question = frappe.get_doc("BHC Question", "STR-03")
		question.question, question.recommendation, question.criticality = "Edited", "Edited", "Standard"
		question.save()
		values = fixtures.copy_model("Short phases")
		values["priority_rules"][0].update(phase="0-15 Days", due_offset_days=15)
		model = frappe.get_doc(values).insert()
		model.is_default = 1
		model.submit()

		after = self.action(doc, "STR-03")
		for field in (*actions.SOURCE_FIELDS, "action_description", "modified"):
			self.assertEqual(after.get(field), before[field], field)
		# A new action from the same (old) assessment still uses that assessment's scoring model.
		actions.create_actions(doc.name, ["STR-02"])
		self.assertEqual(self.action(doc, "STR-02").phase, "31-60 Days")

	def test_scoring_another_assessment_does_not_touch_actions(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		modified = frappe.db.get_value(ACTION, {"assessment": doc.name}, "modified")
		draft = fixtures.make_assessment(self.business, SAMPLE_ANSWERS)
		fixtures.set_answers(draft, {"STR-03": "YES"})
		draft.save()
		self.assertEqual(frappe.db.get_value(ACTION, {"assessment": doc.name}, "modified"), modified)

	def test_reassessment_copies_no_actions(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03", "STR-02"])
		done = self.action(doc, "STR-03")
		done.status = "Completed"
		done.save()
		second = assessments.make_reassessment(doc.name)
		second.assessment_date = "2027-01-22"
		second.insert()
		fixtures.set_answers(second, {"STR-03": "YES"})
		second.save()
		second.submit()
		self.assertEqual(self.count(second), 0)
		self.assertEqual(
			{
				(a.question_code, a.status)
				for a in frappe.get_all(
					ACTION, filters={"assessment": doc.name}, fields=["question_code", "status"]
				)
			},
			{("STR-03", "Completed"), ("STR-02", "Open")},
		)
		self.assertEqual(getdate(self.action(doc, "STR-03").completed_on), getdate(today()))

	def test_actions_trace_to_their_source(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["KPI-11"])
		action = self.action(doc, "KPI-11")
		source = frappe.get_doc("BHC Assessment", action.assessment)
		row = fixtures.response(source, action.question_code)
		self.assertEqual(
			(row.question_text, row.priority, row.gap_rank),
			(action.question_text, action.priority, action.gap_rank),
		)
		self.assertEqual(action.question, row.question)

	def test_source_with_actions_cannot_be_deleted(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		doc.cancel()
		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("BHC Assessment", doc.name)
		self.assertEqual(self.count(doc), 1)


class TestNinetyDayPlan(ActionTestCase):
	def plan(self, **filters):
		return run("BHC 90 Day Plan", filters=filters)

	def summary(self, result):
		return {s["label"]: s["value"] for s in result["report_summary"]}

	def test_rows_follow_the_workbook_order(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["KPI-11", "STR-02", "STR-03", "KPI-10"])
		result = self.plan(assessment=doc.name)
		rows = result["result"]
		self.assertEqual(
			[
				(
					r["question_code"],
					r["priority"],
					r["phase"],
					getdate(r["suggested_start_date"]),
					getdate(r["suggested_due_date"]),
				)
				for r in rows
			],
			SAMPLE_GAPS,
		)
		self.assertEqual(
			{(r["start_date"], r["target_date"], r["overdue"]) for r in rows}, {(None, None, "")}
		)
		summary = self.summary(result)
		self.assertEqual(
			(
				summary["Total Actions"],
				summary["Open"],
				summary["Completed"],
				summary["Overdue"],
				summary["Completion %"],
			),
			(4, 4, 0, 0, 0),
		)
		self.assertEqual((summary["No Agreed Target Date"], summary["Gaps Without an Action"]), (4, 0))

	def test_overdue_only_from_an_agreed_target_date(self):
		# Dated 2025-01-01: every suggested due date is long past, but no action has an agreed target yet.
		doc = self.finalised(date="2025-01-01")
		actions.create_actions(doc.name, ["STR-03", "STR-02", "KPI-10", "KPI-11"])
		self.assertEqual(self.summary(self.plan(assessment=doc.name))["Overdue"], 0)

		updates = {
			"STR-03": {"target_date": add_days(today(), -1)},  # past, open -> overdue
			"STR-02": {"target_date": today()},  # due today -> not yet
			"KPI-10": {"target_date": add_days(today(), -1), "status": "Completed"},  # completed -> never
		}
		for code, values in updates.items():
			action = self.action(doc, code)
			action.update(values)
			action.save()
		rows = {r["question_code"]: r for r in self.plan(assessment=doc.name)["result"]}
		self.assertEqual(
			{code: bool(r["overdue"]) for code, r in rows.items()},
			{"STR-03": True, "STR-02": False, "KPI-10": False, "KPI-11": False},
		)
		summary = self.summary(self.plan(assessment=doc.name))
		self.assertEqual((summary["Overdue"], summary["Completed"], summary["Completion %"]), (1, 1, 25))
		self.assertEqual(
			[r["question_code"] for r in self.plan(assessment=doc.name, overdue_only=1)["result"]], ["STR-03"]
		)

	def test_filters(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03", "STR-02", "KPI-10", "KPI-11"])
		kpi = self.action(doc, "KPI-10")
		kpi.update(
			{
				"responsible": "Plant head, Unit 2",
				"responsible_user": CONSULTANT,
				"target_date": "2026-12-15",
				"status": "In Progress",
			}
		)
		kpi.save()
		cases = {
			"priority": ({"priority": "HIGH"}, ["STR-03"]),
			"phase": ({"phase": "31-60 Days"}, ["STR-02", "KPI-10", "KPI-11"]),
			"department": ({"department": "KPI"}, ["KPI-10", "KPI-11"]),
			"status": ({"status": "In Progress"}, ["KPI-10"]),
			"responsible": ({"responsible": "unit 2"}, ["KPI-10"]),
			"responsible user": ({"responsible_user": CONSULTANT}, ["KPI-10"]),
			"target from": ({"target_from": "2026-12-15"}, ["KPI-10"]),
			"target to": ({"target_to": "2026-12-14"}, []),
			"target range": ({"target_from": "2026-12-01", "target_to": "2026-12-31"}, ["KPI-10"]),
			"business": ({"business": self.business}, ["STR-03", "STR-02", "KPI-10", "KPI-11"]),
		}
		for label, (filters, expected) in cases.items():
			with self.subTest(label):
				rows = self.plan(assessment=doc.name, **filters)["result"]
				self.assertEqual([r["question_code"] for r in rows], expected)
		with self.assertRaises(frappe.ValidationError):
			self.plan(status="Cancelled")

	def test_gaps_without_an_action_and_other_views(self):
		doc = self.finalised()
		actions.create_actions(doc.name, ["STR-03"])
		self.assertEqual(self.summary(self.plan(assessment=doc.name))["Gaps Without an Action"], 3)
		gaps = {
			r["question_code"]: r for r in run("BHC Gap Analysis", filters={"assessment": doc.name})["result"]
		}
		self.assertEqual(gaps["STR-03"]["improvement_action"], self.action(doc, "STR-03").name)
		self.assertEqual(
			(gaps["STR-03"]["action_status"], gaps["STR-02"]["improvement_action"]), ("Open", None)
		)
		self.assertEqual(
			assessments.get_results_summary(doc.name)["actions"],
			{"gaps": 4, "total": 1, "by_status": {"Open": 1}},
		)
