"""Record-level isolation of improvement actions and the 90 Day Plan (permissions.action_* and the Assigned
Users rule): lists, direct document and API access, creation from gaps, sharing, and the report.

Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_action_permissions
"""

import frappe
import frappe.client
import frappe.share
from frappe.desk.form import assign_to
from frappe.desk.query_report import run

from business_health_checkup import actions
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS

ACTION = "BHC Improvement Action"
CONSULTANT_A = "bhc-act-consultant-a@example.com"
MANAGER_A = "bhc-act-manager-a@example.com"
CONSULTANT_B = "bhc-act-consultant-b@example.com"
UNASSIGNED = "bhc-act-unassigned@example.com"
NO_ROLE = "bhc-act-no-role@example.com"
ADMIN = "bhc-act-admin@example.com"


class TestActionIsolation(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()
		for user in (CONSULTANT_A, CONSULTANT_B, UNASSIGNED):
			fixtures.make_user(user, "BHC Consultant")
		fixtures.make_user(MANAGER_A, "BHC Manager")
		fixtures.make_user(NO_ROLE)
		fixtures.make_user(ADMIN, "System Manager")
		cls.business_a = fixtures.make_business("Alpha Forgings Pvt Ltd", [CONSULTANT_A, MANAGER_A])
		cls.business_b = fixtures.make_business("Beta Castings Pvt Ltd", [CONSULTANT_B])
		cls.final_a = cls.finalised(cls.business_a)
		cls.final_b = cls.finalised(cls.business_b)
		cls.action_a = actions.create_actions(cls.final_a.name, ["STR-03"])[0]["action"]
		cls.action_b = actions.create_actions(cls.final_b.name, ["STR-03"])[0]["action"]

	@classmethod
	def finalised(cls, business):
		doc = fixtures.make_assessment(business, SAMPLE_ANSWERS)
		doc.submit()
		return doc

	def as_user(self, user):
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_lists_follow_business_assignment(self):
		for user, expected in (
			(CONSULTANT_A, {self.action_a}),
			(MANAGER_A, {self.action_a}),
			(CONSULTANT_B, {self.action_b}),
			(UNASSIGNED, set()),
		):
			with self.subTest(user):
				self.as_user(user)
				self.assertEqual(set(frappe.get_list(ACTION, pluck="name")), expected)
				self.assertEqual(frappe.client.get_count(ACTION), len(expected))

	def test_direct_access_to_another_business_is_denied(self):
		self.as_user(CONSULTANT_A)
		with self.assertRaises(frappe.PermissionError) as caught:
			frappe.client.get(ACTION, self.action_b)
		self.assertNotIn("Beta Castings", str(caught.exception))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(ACTION, self.action_b).check_permission("read")
		self.assertFalse(frappe.has_permission(ACTION, "print", doc=self.action_b))
		self.assertFalse(frappe.client.get_value(ACTION, "status", {"name": self.action_b}))
		for field, value in (("status", "Completed"), ("responsible", "x"), ("target_date", "2026-12-31")):
			with self.subTest(field):
				with self.assertRaises(frappe.PermissionError):
					frappe.client.set_value(ACTION, self.action_b, field, value)

	def test_actions_cannot_be_created_for_another_business(self):
		self.as_user(CONSULTANT_A)
		with self.assertRaises(frappe.PermissionError):
			actions.create_actions(self.final_b.name, ["STR-02"])
		with self.assertRaises(frappe.PermissionError):
			actions.get_eligible_gaps(self.final_b.name)
		# A forged business pointing at business A does not help: the source assessment decides.
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": ACTION,
					"assessment": self.final_b.name,
					"question": "STR-02",
					"business": self.business_a,
				}
			).insert()
		forged = frappe.get_doc(
			{
				"doctype": ACTION,
				"assessment": self.final_b.name,
				"question": "STR-02",
				"business": self.business_a,
			}
		)
		self.assertFalse(frappe.has_permission(ACTION, "create", doc=forged, user=CONSULTANT_A))
		self.assertEqual(frappe.db.count(ACTION, {"assessment": self.final_b.name}), 1)
		with self.assertRaises(frappe.PermissionError):
			actions.gap_question_query(ACTION, "", "name", 0, 20, {"assessment": self.final_b.name})

	def test_assigned_users_manage_their_actions(self):
		self.as_user(CONSULTANT_A)
		created = actions.create_actions(self.final_a.name, ["STR-02"], responsible_user=MANAGER_A)
		action = frappe.get_doc(ACTION, created[0]["action"])
		action.update({"target_date": "2026-12-31", "status": "Completed", "remarks": "done"})
		action.save()
		frappe.set_user(MANAGER_A)
		action = frappe.get_doc(ACTION, action.name)
		action.status = "In Progress"  # managers may reopen
		action.save()
		self.assertEqual(frappe.db.get_value(ACTION, action.name, "status"), "In Progress")

	def test_only_administrators_delete_actions(self):
		for user in (CONSULTANT_A, MANAGER_A):
			with self.subTest(user):
				self.as_user(user)
				with self.assertRaises(frappe.PermissionError):
					frappe.delete_doc(ACTION, self.action_a)
		frappe.set_user(ADMIN)
		frappe.delete_doc(ACTION, self.action_a)
		self.assertFalse(frappe.db.exists(ACTION, self.action_a))

	def test_being_named_responsible_gives_no_access(self):
		frappe.db.set_value(ACTION, self.action_a, "responsible", UNASSIGNED)
		self.assertFalse(frappe.has_permission(ACTION, "read", doc=self.action_a, user=UNASSIGNED))
		action = frappe.get_doc(ACTION, self.action_a)
		action.responsible_user = UNASSIGNED
		with self.assertRaises(frappe.ValidationError):
			action.save()
		self.as_user(UNASSIGNED)
		self.assertEqual(frappe.get_list(ACTION), [])
		self.assertEqual(
			actions.responsible_user_query("User", "", "name", 0, 20, {"business": self.business_a}), []
		)

	def test_sharing_and_assign_to_cannot_grant_access(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.share.add(ACTION, self.action_b, UNASSIGNED, read=1)
		with self.assertRaises(frappe.PermissionError):
			assign_to.add({"assign_to": [UNASSIGNED], "doctype": ACTION, "name": self.action_b})
		self.assertFalse(frappe.has_permission(ACTION, "read", doc=self.action_b, user=UNASSIGNED))

	def test_90_day_plan_follows_business_assignment(self):
		self.as_user(CONSULTANT_A)
		rows = run("BHC 90 Day Plan", filters={})["result"]
		self.assertEqual({r["action"] for r in rows}, {self.action_a})
		for filters in ({"business": self.business_b}, {"assessment": self.final_b.name}):
			with self.subTest(filters):
				result = run("BHC 90 Day Plan", filters=filters)
				self.assertEqual(result["result"], [])
				summary = {s["label"]: s["value"] for s in result["report_summary"]}
				self.assertNotIn("Gaps Without an Action", summary)
		frappe.set_user(UNASSIGNED)
		self.assertEqual(run("BHC 90 Day Plan", filters={})["result"], [])

	def test_users_without_a_bhc_role_get_nothing(self):
		self.as_user(NO_ROLE)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(ACTION)
		with self.assertRaises(frappe.PermissionError):
			run("BHC 90 Day Plan", filters={})
		with self.assertRaises(frappe.PermissionError):
			actions.create_actions(self.final_a.name, ["STR-02"])
		self.assertFalse(frappe.has_permission(ACTION, "read", doc=self.action_a))

	def test_system_manager_sees_every_business(self):
		self.as_user(ADMIN)
		self.assertTrue({self.action_a, self.action_b} <= set(frappe.get_list(ACTION, pluck="name")))
		self.assertTrue(
			{self.action_a, self.action_b}
			<= {r["action"] for r in run("BHC 90 Day Plan", filters={})["result"]}
		)
