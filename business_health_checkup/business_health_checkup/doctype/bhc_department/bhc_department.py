# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

# SETTINGS!A41:A50 codes are 2-3 capital letters (STR, QA ...); allow a little room without allowing free text.
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


class BHCDepartment(Document):
	def validate(self):
		if not self.is_new() and self.department_code != self.name:
			frappe.throw(_("Department Code cannot be changed"))
		if not CODE_PATTERN.match(self.department_code or ""):
			frappe.throw(_("Department Code must be 2-10 capital letters or digits, starting with a letter"))
		if (self.display_order or 0) < 1:
			frappe.throw(_("Display Order must be 1 or more"))
		if frappe.db.exists(
			"BHC Department", {"display_order": self.display_order, "name": ("!=", self.name)}
		):
			frappe.throw(_("Another department already has Display Order {0}").format(self.display_order))

		seqs = [row.seq for row in self.growth_recommendations]
		if any((seq or 0) < 1 for seq in seqs) or len(set(seqs)) != len(seqs):
			frappe.throw(_("Growth recommendation Seq must be unique and 1 or more"))
