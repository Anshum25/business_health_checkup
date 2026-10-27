"""Shared records and the base class of the integration tests. setUpClass records live in the class transaction
(rolled back when the class finishes); each test is also rolled back to a savepoint."""

import frappe
from frappe.tests import IntegrationTestCase

from business_health_checkup.setup import importer

# The five answers the workbook ships with (STRATEGY!G7:G9, KPI!G16:G17); expected results are Excel's cached
# values (SCORE CALCULATION!C5:M6, C15:M15; GAP ANALYSIS!C19:J22).
SAMPLE_ANSWERS = {"STR-01": "YES", "STR-02": "PARTIALLY", "STR-03": "NO", "KPI-10": "NO", "KPI-11": "NO"}
SAMPLE_DATE = "2026-10-24"


class BHCTestCase(IntegrationTestCase):
	"""IntegrationTestCase rolls back only when the class ends; this also rolls each test back, so tests in one
	class cannot see each other's records."""

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("bhc_test")
		self.addCleanup(frappe.db.rollback, save_point="bhc_test")


def ensure_masters() -> None:
	importer.import_workbook_v1()


def make_user(email: str, *roles: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
	return email


def make_business(name: str, users=()) -> str:
	return (
		frappe.get_doc(
			{"doctype": "BHC Business", "business_name": name, "assigned_users": [{"user": u} for u in users]}
		)
		.insert(ignore_permissions=True)
		.name
	)


def set_answers(doc, answers: dict) -> None:
	for row in doc.responses:
		if row.question_code in answers:
			row.answer = answers[row.question_code]


def make_assessment(business: str, answers: dict | None = None, date: str = SAMPLE_DATE, **values):
	doc = frappe.get_doc(
		{"doctype": "BHC Assessment", "business": business, "assessment_date": date, **values}
	)
	doc.insert()
	if answers:
		set_answers(doc, answers)
		doc.save()
	return doc


def response(doc, code: str):
	return next(row for row in doc.responses if row.question_code == code)


def department(doc, code: str):
	return next(row for row in doc.department_results if row.department == code)


def copy_model(label: str, **weights) -> dict:
	"""Values of a scoring model like Workbook v1, with some criticality weights changed."""
	values = importer.scoring_model_values(importer.load_package()["rules.json"])
	values["version_label"] = label
	for row in values["criticality_weights"]:
		row["weight"] = weights.get(row["criticality"], row["weight"])
	return values
