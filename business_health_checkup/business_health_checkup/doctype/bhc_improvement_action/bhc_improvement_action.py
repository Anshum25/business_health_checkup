# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from business_health_checkup import actions


class BHCImprovementAction(Document):
	"""One row of the workbook's ACTION PLAN: an agreed action for one gap of one finalised assessment.

	The gap part (source, question, priority, phase, suggested dates, recommendation ...) is copied from the source
	assessment when the action is created and is read-only for ever after; the plan part (agreed action,
	responsible, dates, target / measure, status, remarks) is what users maintain. See business_health_checkup.actions.
	"""

	def before_insert(self):
		actions.fill_from_source(self)

	def validate(self):
		if not self.is_new():
			actions.check_source_unchanged(self)
		actions.validate_plan(self)
