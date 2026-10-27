"""Masters, the workbook importer and scoring-model versions.

Run: bench --site <test site> run-tests --module business_health_checkup.tests.test_masters
"""

import json
import shutil
import tempfile
from pathlib import Path

import frappe

from business_health_checkup import scoring
from business_health_checkup.business_health_checkup.doctype.bhc_scoring_model.bhc_scoring_model import (
	get_default_scoring_model,
)
from business_health_checkup.setup import importer
from business_health_checkup.tests import fixtures


def package_json(name):
	return json.loads((scoring.WORKBOOK_DATA / name).read_text())


class TestImportedMasters(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()

	def test_departments_in_workbook_order(self):
		rows = frappe.get_all(
			"BHC Department", fields=["name", "department_name", "display_order"], order_by="display_order"
		)
		self.assertEqual(
			[r.name for r in rows], ["STR", "KPI", "HR", "MKT", "SAL", "PUR", "PRD", "QA", "MNT", "INV"]
		)
		self.assertEqual(rows[0].department_name, "Business Strategy & Goals")  # SETTINGS!C41
		strategy = frappe.get_doc("BHC Department", "STR")
		self.assertEqual(len(strategy.growth_recommendations), 7)
		self.assertEqual(strategy.growth_recommendations[0].source_reference, "RECOMMENDATION MASTER!E4")

	def test_questions_match_the_package_exactly(self):
		source = package_json("questions.json")["questions"]
		stored = {
			q.name: q
			for q in frappe.get_all(
				"BHC Question",
				fields=[
					"name",
					"department",
					"seq",
					"question",
					"criticality",
					"recommendation",
					"source_reference",
				],
			)
		}
		self.assertEqual(len(source), 150)
		for q in source:
			with self.subTest(question=q["question_id"]):
				row = stored[q["question_id"]]
				self.assertEqual(
					(
						row.department,
						row.seq,
						row.question,
						row.criticality,
						row.recommendation,
						row.source_reference,
					),
					(
						q["department"],
						q["seq"],
						q["question"],
						q["criticality"],
						q["recommendation"],
						q["source_row"],
					),
				)

	def test_imported_model_reproduces_the_workbook_rules(self):
		model = frappe.get_doc("BHC Scoring Model", get_default_scoring_model())
		self.assertEqual((model.version_label, model.docstatus), ("Workbook v1", 1))
		self.assertEqual(model.get_rules(), scoring.load_workbook_rules())

	def test_second_import_changes_nothing(self):
		before = {d: frappe.db.count(d) for d in ("BHC Department", "BHC Question", "BHC Scoring Model")}
		report = importer.import_workbook_v1()
		self.assertEqual((report["departments"]["created"], report["questions"]["created"]), ([], []))
		self.assertEqual(
			(len(report["departments"]["unchanged"]), len(report["questions"]["unchanged"])), (10, 150)
		)
		self.assertEqual(report["scoring_model"]["status"], "unchanged")
		self.assertEqual(before, {d: frappe.db.count(d) for d in before})

	def test_changed_and_extra_records_are_reported_not_overwritten(self):
		self.addCleanup(frappe.clear_document_cache, "BHC Department", "QA")
		frappe.db.set_value("BHC Department", "QA", "department_name", "Quality Assurance")
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
		report = importer.import_workbook_v1()
		self.assertEqual(report["departments"]["conflicts"], {"QA": ["department_name"]})
		self.assertEqual(report["questions"]["extra"], ["QA-16"])
		self.assertEqual(frappe.db.get_value("BHC Department", "QA", "department_name"), "Quality Assurance")
		self.assertTrue(frappe.db.exists("BHC Question", "QA-16"))

	def test_dry_run_writes_nothing_and_a_rerun_restores_a_missing_record(self):
		frappe.delete_doc("BHC Question", "INV-15")
		report = importer.import_workbook_v1(dry_run=True)
		self.assertEqual(report["questions"]["created"], ["INV-15"])
		self.assertFalse(frappe.db.exists("BHC Question", "INV-15"))
		importer.import_workbook_v1()
		self.assertEqual(frappe.db.get_value("BHC Question", "INV-15", "criticality"), "Standard")


class TestPackageValidation(fixtures.BHCTestCase):
	def setUp(self):
		self.folder = Path(tempfile.mkdtemp())
		self.addCleanup(shutil.rmtree, self.folder)
		for name in importer.FILES:
			shutil.copy(scoring.WORKBOOK_DATA / name, self.folder / name)

	def edit(self, name, change):
		data = json.loads((self.folder / name).read_text())
		change(data)
		(self.folder / name).write_text(json.dumps(data))

	def test_valid_package(self):
		self.assertEqual(importer.validate_package(importer.load_package(self.folder)), [])

	def test_problems_are_detected_before_anything_is_written(self):
		def break_questions(data):
			questions = data["questions"]
			questions.append(dict(questions[0]))  # duplicate STR-01
			questions[1]["department"] = "XYZ"
			questions[2]["criticality"] = "Urgent"
			questions[3]["question"] = ""

		self.edit("questions.json", break_questions)
		count = frappe.db.count("BHC Question")
		with self.assertRaises(importer.PackageError) as caught:
			importer.import_workbook_v1(folder=str(self.folder))
		message = str(caught.exception)
		for expected in (
			"duplicate question ID: STR-01",
			"unknown department XYZ",
			"unknown criticality Urgent",
			"STR-04: missing question",
		):
			self.assertIn(expected, message)
		self.assertEqual(frappe.db.count("BHC Question"), count)

	def test_mixed_workbooks_are_rejected(self):
		self.edit("departments.json", lambda d: d["_source"].update(sha256="0" * 64))
		with self.assertRaises(importer.PackageError):
			importer.load_package(self.folder)

	def test_invalid_rules_are_rejected(self):
		self.edit("rules.json", lambda d: d["answer_options"].pop())  # drop N/A
		with self.assertRaises(importer.PackageError):
			importer.load_package(self.folder)


class TestMasterValidation(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()

	def department(self, **values):
		return frappe.get_doc(
			{"doctype": "BHC Department", "department_name": "Test", "display_order": 99, **values}
		)

	def question(self, **values):
		return frappe.get_doc(
			{
				"doctype": "BHC Question",
				"department": "STR",
				"seq": 99,
				"question": "Test?",
				"criticality": "Basic",
				**values,
			}
		)

	def test_department_rules(self):
		with self.assertRaises(frappe.ValidationError):
			self.department(department_code="str").insert()
		with self.assertRaises(frappe.ValidationError):
			self.department(department_code="TST", display_order=1).insert()  # STR has 1
		with self.assertRaises(frappe.DuplicateEntryError):
			self.department(department_code="STR").insert()

	def test_question_rules(self):
		with self.assertRaises(frappe.ValidationError):
			self.question(question_code="KPI-99").insert()  # prefix is not its department
		with self.assertRaises(frappe.LinkValidationError):
			self.question(question_code="XYZ-01", department="XYZ").insert()
		with self.assertRaises(frappe.ValidationError):
			self.question(question_code="STR-99", seq=1).insert()  # STR-01 has seq 1
		with self.assertRaises(frappe.ValidationError):
			self.question(question_code="STR-98", criticality="Urgent").insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			self.question(question_code="STR-01", seq=98).insert()

	def test_question_id_cannot_change(self):
		doc = frappe.get_doc("BHC Question", "STR-01")
		doc.question_code = "STR-77"
		with self.assertRaises(frappe.ValidationError):
			doc.save()


class TestScoringModel(fixtures.BHCTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures.ensure_masters()

	def assert_invalid(self, change):
		values = fixtures.copy_model("Broken")
		change(values)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(values).insert()

	def test_invalid_configurations(self):
		cases = {
			"no N/A": lambda v: v["answer_scores"].pop(),
			"NO excluded": lambda v: v["answer_scores"][2].update(excluded=1),
			"fraction above 1": lambda v: v["answer_scores"][0].update(score_fraction=1.5),
			"missing Basic": lambda v: v["criticality_weights"].pop(),
			"zero weight": lambda v: v["criticality_weights"][0].update(weight=0),
			"duplicate band": lambda v: v["maturity_bands"][1].update(lower_bound=0),
			"band not from 0": lambda v: v["maturity_bands"][0].update(lower_bound=0.1),
			"matrix gap": lambda v: v["priority_matrix"].pop(),
			"missing LOW rule": lambda v: v["priority_rules"].pop(),
			"due before start": lambda v: v["priority_rules"][1].update(due_offset_days=10),
			"growth above strength": lambda v: v.update(growth_plan_threshold=0.8),
			"draft default": lambda v: v.update(is_default=1),
		}
		for label, change in cases.items():
			with self.subTest(label):
				self.assert_invalid(change)

	def test_submitted_model_cannot_be_edited(self):
		model = frappe.get_doc("BHC Scoring Model", get_default_scoring_model())
		model.growth_plan_threshold = 0.5
		with self.assertRaises(frappe.UpdateAfterSubmitError):
			model.save()
		model.reload()
		model.criticality_weights[0].weight += 1
		with self.assertRaises(frappe.UpdateAfterSubmitError):
			model.save()

	def test_new_version_replaces_the_default(self):
		old = get_default_scoring_model()
		new = frappe.get_doc(fixtures.copy_model("Test v2", Critical=20)).insert()
		self.assertNotEqual(new.rules_hash, frappe.db.get_value("BHC Scoring Model", old, "rules_hash"))
		new.is_default = 1
		new.submit()
		self.assertEqual(get_default_scoring_model(), new.name)
		self.assertEqual(frappe.db.get_value("BHC Scoring Model", old, "is_default"), 0)
		self.assertEqual(new.get_rules().criticality_weight["Critical"], 20)

	def test_rules_hash_ignores_row_order(self):
		values = fixtures.copy_model("Reordered")
		values["maturity_bands"].reverse()
		values["answer_scores"].reverse()
		reordered = frappe.get_doc(values).insert()
		original = frappe.get_doc("BHC Scoring Model", get_default_scoring_model())
		self.assertEqual(reordered.rules_hash, original.rules_hash)

	def test_model_used_by_a_finalised_assessment_cannot_be_cancelled(self):
		model = frappe.get_doc(fixtures.copy_model("In use")).insert()
		model.submit()
		business = fixtures.make_business("Model Use Ltd")
		fixtures.make_assessment(business, scoring_model=model.name).submit()
		with self.assertRaises(frappe.LinkExistsError):
			model.cancel()
