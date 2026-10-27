// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

// Status colours follow ACTION PLAN!O8:O207's conditional formatting.
const BHC_STATUS_COLORS = { Open: "red", "In Progress": "yellow", Completed: "green", Hold: "gray" };

frappe.query_reports["BHC 90 Day Plan"] = {
	filters: [
		{ fieldname: "business", label: __("Business"), fieldtype: "Link", options: "BHC Business" },
		{
			fieldname: "assessment",
			label: __("Assessment"),
			fieldtype: "Link",
			options: "BHC Assessment",
			get_query: () => {
				const business = frappe.query_report.get_filter_value("business");
				return { filters: { docstatus: 1, ...(business ? { business } : {}) } };
			},
		},
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "BHC Department" },
		{ fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: "\nHIGH\nMEDIUM\nLOW" },
		{
			fieldname: "phase",
			label: __("90-Day Phase"),
			fieldtype: "Select",
			options: "\n0-30 Days\n31-60 Days\n61-90 Days",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nIn Progress\nCompleted\nHold",
		},
		{ fieldname: "responsible", label: __("Responsible (name contains)"), fieldtype: "Data" },
		{ fieldname: "responsible_user", label: __("Responsible User"), fieldtype: "Link", options: "User" },
		{ fieldname: "target_from", label: __("Target Date From"), fieldtype: "Date" },
		{ fieldname: "target_to", label: __("Target Date To"), fieldtype: "Date" },
		{ fieldname: "overdue_only", label: __("Overdue Only"), fieldtype: "Check" },
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "status" && BHC_STATUS_COLORS[data.status]) {
			return `<span class="indicator-pill ${BHC_STATUS_COLORS[data.status]}">${value}</span>`;
		}
		if (column.fieldname === "overdue" && data.overdue) {
			return `<span class="indicator-pill red">${value}</span>`;
		}
		if (["suggested_start_date", "suggested_due_date"].includes(column.fieldname)) {
			return `<span class="text-muted" title="${__("Suggested from the priority; not an agreed date")}">${value}</span>`;
		}
		return value;
	},
};
