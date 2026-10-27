from frappe import _


def get_data():
	return {
		"fieldname": "previous_assessment",
		"non_standard_fieldnames": {"BHC Improvement Action": "assessment"},
		"transactions": [
			{"label": _("Re-assessments"), "items": ["BHC Assessment"]},
			{"label": _("Improvement"), "items": ["BHC Improvement Action"]},
		],
	}
