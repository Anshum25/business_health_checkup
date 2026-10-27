// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

frappe.listview_settings["BHC Assessment"] = {
	add_fields: ["status", "overall_score"],
	get_indicator(doc) {
		const color = { Draft: "red", Finalised: "green", Cancelled: "gray" }[doc.status] || "gray";
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
