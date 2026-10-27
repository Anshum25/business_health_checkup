from frappe import _


def get_data():
	return {
		"fieldname": "business",
		"transactions": [
			{"label": _("Assessments"), "items": ["BHC Assessment"]},
			{"label": _("Improvement"), "items": ["BHC Improvement Action"]},
		],
	}
