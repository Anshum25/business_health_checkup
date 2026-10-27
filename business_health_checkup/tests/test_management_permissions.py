"""Access to the Management Report and the Owner Dashboard: every server path (API, print view, print render,
share link, page) follows the Assigned Users rule, and nothing of another business leaks into counts, charts or
the trend.

Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_management_permissions
"""

import frappe
from frappe.www.printview import get_html_and_style

from business_health_checkup import actions, management
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS

PRINT_FORMAT = "BHC Management Report"
CONSULTANT_A = "bhc-mr-consultant-a@example.com"
MANAGER_A = "bhc-mr-manager-a@example.com"
CONSULTANT_B = "bhc-mr-consultant-b@example.com"
UNASSIGNED = "bhc-mr-unassigned@example.com"
NO_ROLE = "bhc-mr-no-role@example.com"
ADMIN = "bhc-mr-admin@example.com"


class TestManagementAccess(fixtures.BHCTestCase):
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
		actions.create_actions(cls.final_b.name, ["STR-03", "STR-02"])

	@classmethod
	def finalised(cls, business):
		doc = fixtures.make_assessment(business, SAMPLE_ANSWERS)
		doc.submit()
		return doc

	def as_user(self, user):
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")

	def denied(self, name):
		for label, call in (
			# checked before anything is read, not only by the comparison further in
			("load", lambda: management.load_assessment(name)),
			("report", lambda: management.get_management_report(name)),
			("dashboard", lambda: management.get_owner_dashboard(name)),
			("print view", lambda: get_html_and_style("BHC Assessment", name, print_format=PRINT_FORMAT)),
			("print render", lambda: frappe.get_print("BHC Assessment", name, print_format=PRINT_FORMAT)),
		):
			with self.subTest(label):
				with self.assertRaises(frappe.PermissionError) as caught:
					call()
				self.assertNotIn("Castings", str(caught.exception))

	def test_assigned_users_see_their_business(self):
		for user in (CONSULTANT_A, MANAGER_A):
			with self.subTest(user):
				self.as_user(user)
				report = management.get_management_report(self.final_a.name)
				self.assertEqual(report["profile"]["company"], "Alpha Forgings Pvt Ltd")
				dashboard = management.get_owner_dashboard(self.final_a.name)
				self.assertEqual([t["name"] for t in dashboard["trend"]], [self.final_a.name])
				self.assertEqual(
					dashboard["cards"]["gaps_with_action"], "0 / 4"
				)  # B's two actions are not counted
				blob = frappe.as_json([report, dashboard])
				self.assertNotIn("Beta Castings", blob)
				self.assertNotIn(self.final_b.name, blob)
				html = get_html_and_style("BHC Assessment", self.final_a.name, print_format=PRINT_FORMAT)[
					"html"
				]
				self.assertIn("Alpha Forgings Pvt Ltd", html)

	def test_another_business_is_denied(self):
		self.as_user(CONSULTANT_A)
		self.denied(self.final_b.name)

	def test_unassigned_and_role_less_users_are_denied(self):
		for user in (UNASSIGNED, NO_ROLE):
			with self.subTest(user):
				self.as_user(user)
				self.denied(self.final_a.name)

	def test_forged_identifiers(self):
		self.as_user(CONSULTANT_A)
		for name in ("BHC-ASM-1999-99999", f"{self.final_a.name}' or '1'='1"):
			with self.subTest(name):
				with self.assertRaises(frappe.DoesNotExistError):
					management.get_owner_dashboard(name)

	def test_share_links_cannot_be_created(self):
		for doctype, name in (("BHC Assessment", self.final_a.name), ("BHC Business", self.business_a)):
			with self.subTest(doctype):
				with self.assertRaises(frappe.PermissionError):
					frappe.get_doc(doctype, name).get_document_share_key()
		self.assertFalse(frappe.db.exists("Document Share Key", {"reference_docname": self.final_a.name}))

	def test_page_roles(self):
		page = frappe.get_doc("Page", "bhc-owner-dashboard")
		for user, allowed in (
			(CONSULTANT_A, True),
			(MANAGER_A, True),
			(UNASSIGNED, True),
			(NO_ROLE, False),
			(ADMIN, True),
		):
			with self.subTest(user):
				self.as_user(user)
				self.assertEqual(bool(page.is_permitted()), allowed)

	def test_system_manager_sees_every_business(self):
		self.as_user(ADMIN)
		self.assertEqual(
			management.get_owner_dashboard(self.final_b.name)["cards"]["gaps_with_action"], "2 / 4"
		)
		self.assertIn(
			"Beta Castings", management.get_management_report(self.final_b.name)["profile"]["company"]
		)
