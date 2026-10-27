# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

COUNT_FIELDS = ("number_of_employees", "number_of_customers", "number_of_plants")


class BHCBusiness(Document):
	"""The business being assessed (COMPANY PROFILE!C4:C21).

	`assigned_users` decides who may see the business and its assessments (business_health_checkup.permissions);
	only System Managers can change it.
	"""

	def validate(self):
		users = [row.user for row in self.assigned_users]
		if len(set(users)) != len(users):
			frappe.throw(_("A user is assigned to this business more than once"))

		for fieldname in COUNT_FIELDS:
			if (self.get(fieldname) or 0) < 0:
				frappe.throw(_("{0} cannot be negative").format(_(self.meta.get_label(fieldname))))
		if (self.annual_turnover_lakh or 0) < 0:
			frappe.throw(_("Annual Turnover cannot be negative"))
		if not 0 <= (self.export_percent or 0) <= 100:
			frappe.throw(_("Export % must be between 0 and 100"))
		if self.year_established and not 1800 <= self.year_established <= getdate(today()).year:
			frappe.throw(_("Year Established is not a valid year"))
