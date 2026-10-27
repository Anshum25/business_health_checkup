"""ACTION PLAN / 90 DAY PLAN rules (planning.py) against the workbook. No site needed:

env/bin/python -m unittest business_health_checkup.tests.test_planning
"""

import unittest
from datetime import date

from business_health_checkup import planning, scoring

ASSESSED = date(2026, 10, 24)  # the sample's cached AssessmentDate


class TestStatuses(unittest.TestCase):
	def test_status_list(self):
		# SETTINGS!A34:A37
		self.assertEqual(planning.STATUSES, ("Open", "In Progress", "Completed", "Hold"))


class TestSuggestedDates(unittest.TestCase):
	def setUp(self):
		self.rules = scoring.load_workbook_rules()

	def test_phase_boundaries(self):
		# SETTINGS!H20:I22 offsets 0/30, 31/60, 61/90 days from the assessment date
		cases = {
			"HIGH": (date(2026, 10, 24), date(2026, 11, 23)),  # day 0 and day 30
			"MEDIUM": (date(2026, 11, 24), date(2026, 12, 23)),  # day 31 and day 60
			"LOW": (date(2026, 12, 24), date(2027, 1, 22)),  # day 61 and day 90
		}
		for priority, expected in cases.items():
			with self.subTest(priority):
				self.assertEqual(planning.suggested_dates(priority, ASSESSED, self.rules), expected)
		self.assertEqual((date(2026, 11, 23) - ASSESSED).days, 30)
		self.assertEqual((date(2026, 11, 24) - ASSESSED).days, 31)
		self.assertEqual((date(2027, 1, 22) - ASSESSED).days, 90)

	def test_phases(self):
		self.assertEqual(
			dict(self.rules.priority_phase),
			{"HIGH": "0-30 Days", "MEDIUM": "31-60 Days", "LOW": "61-90 Days"},
		)

	def test_leap_year(self):
		self.assertEqual(
			planning.suggested_dates("HIGH", date(2028, 2, 1), self.rules),
			(date(2028, 2, 1), date(2028, 3, 2)),
		)

	def test_no_assessment_date_gives_no_dates(self):
		self.assertEqual(planning.suggested_dates("HIGH", None, self.rules), (None, None))


class TestPlanDates(unittest.TestCase):
	def test_after_1_january_2000(self):
		# ACTION PLAN!L8:M207: greaterThan 36526
		self.assertFalse(planning.is_valid_plan_date(date(2000, 1, 1)))
		self.assertTrue(planning.is_valid_plan_date(date(2000, 1, 2)))
		self.assertTrue(planning.is_valid_plan_date(None))


class TestOverdue(unittest.TestCase):
	def test_action_plan_q8(self):
		today = date(2026, 12, 1)
		cases = {
			("Open", date(2026, 11, 30)): True,
			("In Progress", date(2026, 11, 30)): True,
			("Hold", date(2026, 11, 30)): True,
			("Completed", date(2026, 11, 30)): False,
			("Open", date(2026, 12, 1)): False,  # due today is not overdue yet (M8<TODAY())
			("Open", date(2026, 12, 2)): False,
			("Open", None): False,  # no agreed target date: never overdue
			(None, date(2026, 11, 30)): True,  # blank status counts as not completed
		}
		for (status, target), expected in cases.items():
			with self.subTest(status=status, target=target):
				self.assertEqual(planning.is_overdue(status, target, today), expected)


class TestCounters(unittest.TestCase):
	def test_action_plan_a4_g4(self):
		today = date(2026, 12, 1)
		actions = [
			("Open", date(2026, 11, 1)),
			(None, None),
			("In Progress", None),
			("Completed", date(2026, 11, 1)),
			("Hold", date(2026, 11, 1)),
		]
		self.assertEqual(
			planning.action_counters(actions, today),
			{
				"total": 5,
				"open": 2,
				"in_progress": 1,
				"completed": 1,
				"hold": 1,
				"overdue": 2,
				"completion": 0.2,
			},
		)

	def test_no_actions(self):
		self.assertEqual(planning.action_counters([], date(2026, 12, 1))["completion"], 0.0)
