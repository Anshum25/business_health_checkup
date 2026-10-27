# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from business_health_checkup import assessments


class BHCAssessment(Document):
	"""One assessment event of one business (one column of the department sheets, with its own snapshot).

	Draft: answers can change and every save re-scores. Submitted ("Finalised"): frozen; Frappe allows no field
	to change and nothing re-scores it. Cancel and amend are System Manager only (no correction process has been
	approved yet).
	"""

	def before_insert(self):
		if self.amended_from:
			assessments.check_amendment_snapshot(self)
		else:
			assessments.ensure_scoring_model(self)
			assessments.build_snapshot(self)
		self.sequence_no = (
			frappe.db.get_value("BHC Assessment", self.amended_from, "sequence_no")
			if self.amended_from
			else assessments.next_sequence_no(self.business)
		)
		if not self.assessment_label:
			self.assessment_label = _("Assessment {0}").format(self.sequence_no) + (
				" - " + _("Baseline") if self.sequence_no == 1 else ""
			)
		if not self.consultant:
			self.consultant = frappe.session.user

	def validate(self):
		if not self.is_new():
			if self.has_value_changed("scoring_model") or self.has_value_changed("business"):
				frappe.throw(
					_("Business and Scoring Model cannot be changed after the assessment is created")
				)
			assessments.check_snapshot_unchanged(self)
		assessments.get_scoring_model(self.scoring_model)
		assessments.validate_previous_assessment(self)
		assessments.calculate(self)
		self.status = "Finalised" if self.docstatus == 1 else "Draft"

	def before_submit(self):
		if differences := assessments.stored_result_differences(self):
			frappe.throw(_("Results do not match the scoring model: {0}").format(differences[0]))
		if self.answered_questions < self.total_questions:
			frappe.msgprint(
				_("{0} of {1} questions are unanswered; they are left out of the score.").format(
					self.total_questions - self.answered_questions, self.total_questions
				),
				alert=True,
			)

	def on_cancel(self):
		self.db_set("status", "Cancelled")
