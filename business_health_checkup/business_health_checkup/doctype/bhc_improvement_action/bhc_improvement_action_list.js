// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

// Status colours follow ACTION PLAN!O8:O207's conditional formatting.
frappe.listview_settings["BHC Improvement Action"] = {
	add_fields: ["status", "priority", "target_date"],
	get_indicator(doc) {
		const color = { Open: "red", "In Progress": "yellow", Completed: "green", Hold: "gray" }[doc.status] || "gray";
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
