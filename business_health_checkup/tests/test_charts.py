"""SVG charts (charts.py). No site needed:

env/bin/python -m unittest business_health_checkup.tests.test_charts
"""

import unittest
import xml.etree.ElementTree as ET

from business_health_checkup import charts

SVG = "{http://www.w3.org/2000/svg}"
ITEMS = [("Strategy", 34.78, True), ("KPI", 0, True), ("<b>HR</b> & Co", 0, False), ("Sales", 100, True)]


def texts(svg):
	return [t.text for t in ET.fromstring(svg).iter(f"{SVG}text")]


class TestCharts(unittest.TestCase):
	def test_bar_chart(self):
		svg = charts.bar_chart(ITEMS)
		labels = texts(svg)
		self.assertIn("35%", labels)  # 34.78 shown rounded
		self.assertIn("0%", labels)  # KPI: assessed at 0 % is a real bar label
		self.assertEqual(labels.count("not assessed"), 1)  # HR: no bar, no 0 %
		self.assertEqual(len(ET.fromstring(svg).findall(f"{SVG}rect")), 3)

	def test_labels_are_escaped(self):
		for svg in (
			charts.bar_chart(ITEMS),
			charts.radar_chart(ITEMS),
			charts.trend_chart([("<i>A1</i>", 50)]),
		):
			with self.subTest(svg[:30]):
				self.assertNotIn("<b>", svg)
				self.assertNotIn("<i>", svg)
				ET.fromstring(svg)  # well-formed

	def test_radar_marks_unassessed_points(self):
		svg = charts.radar_chart(ITEMS)
		self.assertIn("<b>HR</b> & Co (not assessed)", texts(svg))
		circles = ET.fromstring(svg).findall(f"{SVG}circle")
		self.assertEqual([c.get("fill") for c in circles].count("#ffffff"), 1)
		self.assertEqual(charts.radar_chart(ITEMS[:2]), "")  # fewer than 3 axes: no radar

	def test_trend_skips_unanswered_assessments(self):
		svg = charts.trend_chart([("Assessment 1", 24.24), ("Assessment 2", None), ("Assessment 3", 54.5)])
		labels = texts(svg)
		self.assertIn("Assessment 1", labels)
		self.assertNotIn("Assessment 2", labels)
		self.assertIn("55%", labels)
		self.assertEqual(charts.trend_chart([("Assessment 1", None)]), "")

	def test_deterministic(self):
		self.assertEqual(charts.bar_chart(ITEMS), charts.bar_chart(list(ITEMS)))
