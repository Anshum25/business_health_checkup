// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

frappe.query_reports["BHC Assessment Comparison"] = {
	filters: [
		{
			fieldname: "assessment",
			label: __("Assessment"),
			fieldtype: "Link",
			options: "BHC Assessment",
			reqd: 1,
			description: __("Compared with its Previous Assessment"),
			get_query: () => ({ filters: { previous_assessment: ["is", "set"] } }),
		},
		{
			fieldname: "view",
			label: __("Show"),
			fieldtype: "Select",
			options: "Departments\nQuestions",
			default: "Departments",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "comparable") {
			const color = data.comparable === __("Yes") ? "blue" : "orange";
			return `<span class="indicator-pill ${color}">${value}</span>`;
		}
		if (column.fieldname === "difference" && data.difference == null) {
			return `<span class="text-muted">${__("n/a")}</span>`;
		}
		if (data.department === "ALL") return `<b>${value}</b>`;
		return value;
	},
};
