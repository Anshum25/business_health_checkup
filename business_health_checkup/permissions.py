"""Record-level access to businesses, their assessments and their improvement actions.

Provisional policy (open question Q-18): a user sees a BHC Business, and the BHC Assessments of it, only when
listed in the business's Assigned Users. No assignment means no access, never access to everything. System
Manager (and Administrator) is the administrator role and is unrestricted.

An improvement action belongs to the business of its source assessment. Naming a user as an action's
responsible person gives no access: actions follow the same Assigned Users rule.

Role permissions decide what a user may do (read, write, submit ...); these hooks only narrow them to the
assigned businesses. Child tables (responses, department results) are covered through their parent: Frappe
checks the parent document for child access and joins the parent's conditions into child-table list queries.

Frappe lets a document share override both hooks, and "Assign To" shares a document automatically with an
assignee who has no access. `prevent_sharing` therefore refuses every share of these doctypes; access is given
only by assigning the user to the business. For the same reason `prevent_share_key` refuses Document Share
Keys, which let anyone holding the key open a document's print view (e.g. the "view link" in e-mails).
"""

import frappe
from frappe import _

UNRESTRICTED_ROLES = frozenset({"System Manager"})
CONFIDENTIAL_DOCTYPES = ("BHC Business", "BHC Assessment", "BHC Improvement Action")


def is_unrestricted(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(UNRESTRICTED_ROLES.intersection(frappe.get_roles(user)))


def assigned_businesses(user: str) -> set[str]:
	return set(
		frappe.get_all(
			"BHC Business User",
			filters={"user": user, "parenttype": "BHC Business", "parentfield": "assigned_users"},
			pluck="parent",
		)
	)


def has_business_access(user: str, business: str | None) -> bool:
	"""Whether `user` may see `business` under the Assigned Users rule (unrestricted users see every business)."""
	if not business:
		return False
	return is_unrestricted(user) or business in assigned_businesses(user)


def _assigned_subquery(user: str) -> str:
	return (
		"select `parent` from `tabBHC Business User` where `parenttype` = 'BHC Business'"
		f" and `parentfield` = 'assigned_users' and `user` = {frappe.db.escape(user)}"
	)


def business_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	return f"`tabBHC Business`.`name` in ({_assigned_subquery(user)})"


def assessment_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	return f"`tabBHC Assessment`.`business` in ({_assigned_subquery(user)})"


def action_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	return f"`tabBHC Improvement Action`.`business` in ({_assigned_subquery(user)})"


def has_business_permission(
	doc, ptype: str | None = None, user: str | None = None, debug: bool = False
) -> bool:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return True
	return bool(doc.name) and doc.name in assigned_businesses(user)


def has_assessment_permission(
	doc, ptype: str | None = None, user: str | None = None, debug: bool = False
) -> bool:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return True
	business = doc.get("business")
	return bool(business) and business in assigned_businesses(user)


def has_action_permission(
	doc, ptype: str | None = None, user: str | None = None, debug: bool = False
) -> bool:
	"""Decided by the source assessment's business as stored in the database, not by the action's own `business`
	field, so a request cannot point an action at one business and its source at another."""
	user = user or frappe.session.user
	if is_unrestricted(user):
		return True
	assessment = doc.get("assessment")
	business = frappe.db.get_value("BHC Assessment", assessment, "business") if assessment else None
	return bool(business) and business in assigned_businesses(user)


def prevent_share_key(doc, method=None) -> None:
	"""Document Share Key validate hook."""
	if doc.reference_doctype in CONFIDENTIAL_DOCTYPES:
		frappe.throw(
			_(
				"{0} records cannot be opened with a share link. Assign the user to the business instead."
			).format(_(doc.reference_doctype)),
			frappe.PermissionError,
		)


def prevent_sharing(doc, method=None) -> None:
	"""DocShare validate hook."""
	if doc.share_doctype in CONFIDENTIAL_DOCTYPES:
		frappe.throw(
			_("{0} records cannot be shared. Assign the user to the business instead.").format(
				_(doc.share_doctype)
			),
			frappe.PermissionError,
		)
