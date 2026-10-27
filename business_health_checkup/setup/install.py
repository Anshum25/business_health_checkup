import frappe

from business_health_checkup.setup import importer

# BHC Consultant: captures answers for assigned businesses. BHC Manager: may also finalise (submit) them.
# Who holds which role is a business decision (Q-03, Q-06); a user can hold both.
ROLES = ("BHC Consultant", "BHC Manager")


def ensure_roles() -> None:
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def after_install() -> None:
	ensure_roles()
	importer.print_summary(importer.import_workbook_v1())


def after_migrate() -> None:
	ensure_roles()
