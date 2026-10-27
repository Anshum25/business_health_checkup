# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class BHCQuestion(Document):
	"""A question of the bank (QUESTION MASTER). Assessments copy it when they are created, so editing it never
	changes an existing assessment."""

	def validate(self):
		if not self.is_new() and self.question_code != self.name:
			frappe.throw(_("Question ID cannot be changed; assessments refer to it"))
		# QUESTION MASTER IDs are the department code, a hyphen and a number (STR-01; INSTRUCTIONS!C16: QA-16).
		if not re.fullmatch(rf"{re.escape(self.department or '')}-\d+", self.question_code or ""):
			frappe.throw(
				_("Question ID must be the department code, a hyphen and a number, e.g. {0}-01").format(
					self.department
				)
			)
		if (self.seq or 0) < 1:
			frappe.throw(_("Seq must be 1 or more"))
		if frappe.db.exists(
			"BHC Question", {"department": self.department, "seq": self.seq, "name": ("!=", self.name)}
		):
			frappe.throw(_("Another question of {0} already has Seq {1}").format(self.department, self.seq))
		if not (self.question or "").strip():
			frappe.throw(_("Question text is required"))
