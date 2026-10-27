// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

// UI only: the gap, priority, phase and suggested dates are copied from the source assessment on the server.
frappe.ui.form.on("BHC Improvement Action", {
	setup(frm) {
		frm.set_query("assessment", () => ({ filters: { docstatus: 1 } }));
		frm.set_query("question", () => ({
			query: "business_health_checkup.actions.gap_question_query",
			filters: { assessment: frm.doc.assessment },
		}));
		frm.set_query("responsible_user", () => ({
			query: "business_health_checkup.actions.responsible_user_query",
			filters: { business: frm.doc.business },
		}));
	},

	refresh(frm) {
		if (frm.doc.assessment && !frm.is_new()) {
			frm.add_custom_button(__("Source Assessment"), () =>
				frappe.set_route("Form", "BHC Assessment", frm.doc.assessment)
			);
			frm.add_custom_button(__("90 Day Plan"), () =>
				frappe.set_route("query-report", "BHC 90 Day Plan", { assessment: frm.doc.assessment })
			);
		}
	},

	assessment(frm) {
		frm.set_value("question", null);
	},
});
