"""Record-level isolation of businesses and assessments (business_health_checkup.permissions).

Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_permissions
"""

import frappe
import frappe.client
import frappe.desk.reportview
import frappe.desk.search
import frappe.share
from frappe.desk.form import assign_to
from frappe.desk.query_report import run

from business_health_checkup import assessments
from business_health_checkup.tests import fixtures
from business_health_checkup.tests.fixtures import SAMPLE_ANSWERS, response

CONSULTANT_A = "bhc-consultant-a@example.com"
CONSULTANT_B = "bhc-consultant-b@example.com"
UNASSIGNED = "bhc-consultant-none@example.com"
MANAGER_A = "bhc-manager-a@example.com"
NO_ROLE = "bhc-no-role@example.com"
ADMIN = "bhc-admin@example.com"
SECRET_A = "evidence only business A may see"
SECRET_B = "evidence only business B may see"


class TestRecordIsolation(fixtures.BHCTestCase):
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
		cls.assessment_a = cls.assessment_with_evidence(cls.business_a, SECRET_A)
		cls.assessment_b = cls.assessment_with_evidence(cls.business_b, SECRET_B)
		cls.final_b = fixtures.make_assessment(cls.business_b, SAMPLE_ANSWERS)
		cls.final_b.submit()
		reassessment = assessments.make_reassessment(cls.final_b.name)
		reassessment.assessment_date = "2027-01-22"
		cls.reassessment_b = reassessment.insert().name

	@classmethod
	def assessment_with_evidence(cls, business, evidence):
		doc = fixtures.make_assessment(business, SAMPLE_ANSWERS)
		response(doc, "STR-01").evidence = evidence
		doc.save()
		return doc.name

	def as_user(self, user):
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_assigned_users_see_only_their_business(self):
		for user, business in (
			(CONSULTANT_A, self.business_a),
			(MANAGER_A, self.business_a),
			(CONSULTANT_B, self.business_b),
		):
			with self.subTest(user):
				self.as_user(user)
				self.assertEqual(frappe.get_list("BHC Business", pluck="name"), [business])
				names = set(frappe.get_list("BHC Assessment", pluck="name"))
				self.assertEqual(
					{frappe.db.get_value("BHC Assessment", n, "business") for n in names}, {business}
				)

	def test_no_assignment_means_no_records(self):
		self.as_user(UNASSIGNED)
		self.assertEqual(frappe.get_list("BHC Business"), [])
		self.assertEqual(frappe.get_list("BHC Assessment"), [])
		self.assertEqual(frappe.client.get_count("BHC Assessment"), 0)
		self.assertEqual(
			frappe.get_list("BHC Assessment Response", parent_doctype="BHC Assessment", fields=["evidence"]),
			[],
		)
		for doctype, name in (
			("BHC Business", self.business_a),
			("BHC Business", self.business_b),
			("BHC Assessment", self.assessment_a),
			("BHC Assessment", self.final_b.name),
		):
			with self.subTest(name):
				self.assertFalse(frappe.has_permission(doctype, "read", doc=name))

	def test_direct_access_to_another_business_is_denied(self):
		self.as_user(CONSULTANT_A)
		for doctype, name in (("BHC Business", self.business_b), ("BHC Assessment", self.assessment_b)):
			with self.subTest(doctype):
				with self.assertRaises(frappe.PermissionError) as caught:
					frappe.client.get(doctype, name)
				self.assertNotIn("Beta Castings", str(caught.exception))
				with self.assertRaises(frappe.PermissionError):
					frappe.get_doc(doctype, name).check_permission("read")
				self.assertFalse(frappe.has_permission(doctype, "print", doc=name))
		self.assertFalse(
			frappe.client.get_value("BHC Assessment", "overall_score", {"name": self.assessment_b})
		)

	def test_response_rows_follow_the_parent(self):
		self.as_user(CONSULTANT_A)
		rows = frappe.get_list(
			"BHC Assessment Response", parent_doctype="BHC Assessment", fields=["parent", "evidence"], limit=0
		)
		self.assertTrue(rows)
		self.assertEqual({r.parent for r in rows}, {self.assessment_a})  # the only assessment of business A
		self.assertNotIn(SECRET_B, {r.evidence for r in rows})
		results = frappe.client.get_list(
			"BHC Assessment Department Result",
			parent="BHC Assessment",
			fields=["parent"],
			limit_page_length=0,
		)
		self.assertEqual({r.parent for r in results}, {self.assessment_a})

	def test_report_view_and_link_search_are_filtered(self):
		self.as_user(CONSULTANT_A)
		data = frappe.desk.reportview.execute(
			"BHC Assessment",
			fields=["`tabBHC Assessment`.name", "`tabBHC Assessment Response`.evidence"],
			limit_page_length=0,
		)
		self.assertEqual({d.name for d in data}, {self.assessment_a})
		self.assertNotIn(SECRET_B, {d.evidence for d in data})
		found = frappe.desk.search.search_link("BHC Business", "")
		self.assertEqual([r["value"] for r in found], [self.business_a])
		found = frappe.desk.search.search_link("BHC Assessment", "")
		self.assertEqual({r["value"] for r in found}, {self.assessment_a})

	def test_another_business_cannot_be_written(self):
		self.as_user(CONSULTANT_A)
		with self.assertRaises(frappe.PermissionError):
			frappe.client.set_value("BHC Assessment", self.assessment_b, "consultant_remarks", "x")
		with self.assertRaises(frappe.PermissionError):
			frappe.client.set_value("BHC Business", self.business_b, "location", "x")
		frappe.set_user("Administrator")
		payload = frappe.get_doc("BHC Assessment", self.assessment_b).as_dict()
		frappe.set_user(CONSULTANT_A)
		payload["responses"][0]["answer"] = "NO"
		with self.assertRaises(frappe.PermissionError):
			frappe.client.save(payload)
		with self.assertRaises(frappe.PermissionError):
			fixtures.make_assessment(self.business_b)

	def test_results_cannot_be_set_through_the_api(self):
		self.as_user(CONSULTANT_A)
		payload = frappe.get_doc("BHC Assessment", self.assessment_a).as_dict()
		payload["overall_score"] = 100
		payload["responses"][2]["earned_points"] = 10  # STR-03, answered NO
		saved = frappe.client.save(payload)
		self.assertAlmostEqual(saved["overall_score"], 24.242424242, places=6)
		self.assertEqual(saved["responses"][2]["earned_points"], 0)
		payload = frappe.get_doc("BHC Assessment", self.assessment_a).as_dict()
		payload["responses"][0]["answer"] = "ALWAYS"
		with self.assertRaises(frappe.ValidationError):
			frappe.client.save(payload)

	def test_consultant_cannot_finalise_or_change_masters(self):
		self.as_user(CONSULTANT_A)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("BHC Assessment", self.assessment_a).submit()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(fixtures.copy_model("Consultant v2")).insert()
		with self.assertRaises(frappe.PermissionError):
			frappe.client.set_value("BHC Question", "STR-01", "criticality", "Basic")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "BHC Business", "business_name": "Self-made Ltd"}).insert()

	def test_manager_finalises_only_assigned_businesses(self):
		own = fixtures.make_assessment(self.business_a, SAMPLE_ANSWERS).name
		other = fixtures.make_assessment(self.business_b, SAMPLE_ANSWERS).name
		self.as_user(MANAGER_A)
		frappe.get_doc("BHC Assessment", own).submit()
		self.assertEqual(frappe.db.get_value("BHC Assessment", own, "status"), "Finalised")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("BHC Assessment", other).submit()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("BHC Assessment", own).cancel()

	def test_assignments_are_changed_only_by_administrators(self):
		self.as_user(CONSULTANT_A)
		doc = frappe.get_doc("BHC Business", self.business_a)
		doc.append("assigned_users", {"user": UNASSIGNED})
		doc.location = "Pune, Maharashtra"
		doc.save()
		frappe.set_user("Administrator")
		doc = frappe.get_doc("BHC Business", self.business_a)
		self.assertEqual(doc.location, "Pune, Maharashtra")
		self.assertEqual([r.user for r in doc.assigned_users], [CONSULTANT_A, MANAGER_A])
		self.assertFalse(frappe.has_permission("BHC Business", "read", doc=self.business_a, user=UNASSIGNED))

	def test_sharing_and_assign_to_cannot_grant_access(self):
		for doctype, name in (("BHC Business", self.business_b), ("BHC Assessment", self.assessment_b)):
			with self.subTest(doctype):
				with self.assertRaises(frappe.PermissionError):
					frappe.share.add(doctype, name, UNASSIGNED, read=1)
				with self.assertRaises(frappe.PermissionError):
					assign_to.add({"assign_to": [UNASSIGNED], "doctype": doctype, "name": name})
				self.assertFalse(frappe.has_permission(doctype, "read", doc=name, user=UNASSIGNED))

	def test_service_methods_check_permission(self):
		self.as_user(CONSULTANT_A)
		for method, name in (
			(assessments.make_reassessment, self.final_b.name),
			(assessments.verify_results, self.assessment_b),
			(assessments.get_comparison, self.assessment_b),
		):
			with self.subTest(method.__name__):
				with self.assertRaises(frappe.PermissionError):
					method(name)

	def test_users_without_a_bhc_role_get_nothing(self):
		self.as_user(NO_ROLE)
		for doctype in ("BHC Business", "BHC Assessment"):
			with self.subTest(doctype):
				with self.assertRaises(frappe.PermissionError):
					frappe.get_list(doctype)
				self.assertFalse(
					frappe.has_permission(
						doctype,
						"read",
						doc=self.business_a if doctype == "BHC Business" else self.assessment_a,
					)
				)

	def test_system_manager_is_the_unrestricted_administrator(self):
		self.as_user(ADMIN)
		self.assertTrue(
			{self.business_a, self.business_b} <= set(frappe.get_list("BHC Business", pluck="name"))
		)
		self.assertTrue(
			{self.assessment_a, self.assessment_b} <= set(frappe.get_list("BHC Assessment", pluck="name"))
		)

	def test_reports_show_only_assigned_businesses(self):
		self.as_user(CONSULTANT_A)
		for report in ("BHC Gap Analysis", "BHC Department Results"):
			with self.subTest(report):
				rows = run(report, filters={})["result"]
				self.assertTrue(rows)
				self.assertEqual({r["business"] for r in rows}, {self.business_a})
				self.assertNotIn("Beta Castings Pvt Ltd", {r["business_name"] for r in rows})
				for filters in (
					{"business": self.business_b},
					{"assessment": self.assessment_b},
					{"status": "Finalised"},
				):
					self.assertEqual(run(report, filters=filters)["result"], [], filters)
		gaps = run("BHC Gap Analysis", filters={"business": self.business_b})
		self.assertEqual({s["label"]: s["value"] for s in gaps["report_summary"]}["Total Gaps"], 0)

	def test_comparison_and_summary_of_another_business_are_denied(self):
		for user in (CONSULTANT_A, UNASSIGNED):
			with self.subTest(user):
				self.as_user(user)
				with self.assertRaises(frappe.PermissionError):
					run("BHC Assessment Comparison", filters={"assessment": self.reassessment_b})
				with self.assertRaises(frappe.PermissionError):
					assessments.get_comparison(self.reassessment_b)
				with self.assertRaises(frappe.PermissionError):
					assessments.get_results_summary(self.assessment_b)

	def test_unassigned_user_gets_empty_reports(self):
		self.as_user(UNASSIGNED)
		for report in ("BHC Gap Analysis", "BHC Department Results"):
			with self.subTest(report):
				self.assertEqual(run(report, filters={})["result"], [])
				self.assertEqual(run(report, filters={"assessment": self.assessment_a})["result"], [])

	def test_users_without_a_bhc_role_cannot_run_the_reports(self):
		self.as_user(NO_ROLE)
		for report in ("BHC Gap Analysis", "BHC Department Results", "BHC Assessment Comparison"):
			with self.subTest(report):
				with self.assertRaises(frappe.PermissionError):
					run(report, filters={"assessment": self.assessment_a})

	def test_system_manager_reports_cover_every_business(self):
		self.as_user(ADMIN)
		rows = run("BHC Gap Analysis", filters={})["result"]
		self.assertTrue({self.business_a, self.business_b} <= {r["business"] for r in rows})
		comparison = run("BHC Assessment Comparison", filters={"assessment": self.reassessment_b})
		self.assertEqual(comparison["result"][0]["department"], "ALL")
