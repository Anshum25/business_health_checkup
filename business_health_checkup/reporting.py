"""Helpers shared by the BHC script reports.

Every report starts from `permitted_assessments`, which goes through frappe.get_list and therefore through the
record-level access rules in permissions.py: filters can only narrow the assessments a user may read, never
widen them. Child rows are then read only for those assessments.
"""

import frappe

STATUSES = ("Draft", "Finalised", "Cancelled")


def permitted_assessments(filters, fields) -> list:
	"""Assessments the current user may read that match the business / assessment / status filters.

	Cancelled assessments are left out unless the Status filter asks for them: an amendment replaces them, and
	listing both would count the same answers twice.
	"""
	conditions = []
	if filters.get("business"):
		conditions.append(["business", "=", filters.business])
	if filters.get("assessment"):
		conditions.append(["name", "=", filters.assessment])
	if filters.get("status"):
		conditions.append(["status", "=", filters.status])
	else:
		conditions.append(["docstatus", "<", 2])
	return frappe.get_list(
		"BHC Assessment",
		filters=conditions,
		fields=fields,
		order_by="assessment_date desc, name desc",
		limit_page_length=0,
	)
