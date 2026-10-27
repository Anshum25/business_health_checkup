"""The workbook masters copied into workbook_v1/ are complete and consistent with each other.

Counts and point totals are the ones found in the workbook audit (docs/workbook_audit.md, section 2).
"""

import json
import unittest
from collections import Counter

from business_health_checkup import hooks, scoring

DEPARTMENT_MAX_POINTS = {
	"STR": 118,
	"KPI": 113,
	"HR": 80,
	"MKT": 78,
	"SAL": 113,
	"PUR": 101,
	"PRD": 101,
	"QA": 101,
	"MNT": 87,
	"INV": 82,
}


def load(name):
	return json.loads((scoring.WORKBOOK_DATA / name).read_text())


class TestAppMetadata(unittest.TestCase):
	def test_hooks(self):
		self.assertEqual(hooks.app_name, "business_health_checkup")
		self.assertEqual(hooks.app_title, "Business Health Checkup")


class TestWorkbookData(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.rules = scoring.load_workbook_rules()
		cls.questions = load("questions.json")["questions"]
		cls.departments = load("departments.json")["departments"]

	def test_same_source_workbook(self):
		hashes = {
			load(name)["_source"]["sha256"] for name in ("rules.json", "questions.json", "departments.json")
		}
		self.assertEqual(len(hashes), 1)

	def test_ten_departments_in_workbook_order(self):
		self.assertEqual(
			[d["code"] for d in self.departments],
			["STR", "KPI", "HR", "MKT", "SAL", "PUR", "PRD", "QA", "MNT", "INV"],
		)
		for department in self.departments:
			with self.subTest(department=department["code"]):
				self.assertEqual([r["seq"] for r in department["growth_recommendations"]], list(range(1, 8)))
				self.assertTrue(department["business_risk"])

	def test_question_bank(self):
		self.assertEqual(len(self.questions), 150)
		ids = [q["question_id"] for q in self.questions]
		self.assertEqual(len(set(ids)), 150)
		self.assertEqual(
			Counter(q["department"] for q in self.questions), dict.fromkeys(DEPARTMENT_MAX_POINTS, 15)
		)
		codes = {d["code"] for d in self.departments}
		for q in self.questions:
			with self.subTest(question=q["question_id"]):
				self.assertTrue(q["question_id"].startswith(q["department"] + "-"))
				self.assertIn(q["department"], codes)
				self.assertIn(q["criticality"], self.rules.criticality_weight)
				for field in ("sub_category", "question", "recommendation", "kpi", "business_risk"):
					self.assertTrue(q[field], field)

	def test_criticality_mix(self):
		# "Basic" is defined in SETTINGS but no supplied question uses it.
		self.assertEqual(
			Counter(q["criticality"] for q in self.questions),
			{"Important": 66, "Critical": 56, "Standard": 28},
		)

	def test_department_max_points(self):
		points = Counter()
		for q in self.questions:
			points[q["department"]] += self.rules.criticality_weight[q["criticality"]]
		self.assertEqual(dict(points), DEPARTMENT_MAX_POINTS)
		self.assertEqual(sum(points.values()), 974)
