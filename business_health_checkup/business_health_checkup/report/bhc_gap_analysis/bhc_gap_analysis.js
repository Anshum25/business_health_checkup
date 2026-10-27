// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

frappe.query_reports["BHC Gap Analysis"] = {
	filters: [
		{ fieldname: "business", label: __("Business"), fieldtype: "Link", options: "BHC Business" },
		{
			fieldname: "assessment",
			label: __("Assessment"),
			fieldtype: "Link",
			options: "BHC Assessment",
			get_query: () => {
				const business = frappe.query_report.get_filter_value("business");
				return { filters: business ? { business } : {} };
			},
		},
		{
			fieldname: "status",
			label: __("Assessment Status"),
			fieldtype: "Select",
			options: "\nDraft\nFinalised\nCancelled",
			description: __("Blank = Draft and Finalised"),
		},
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "BHC Department" },
		{
			fieldname: "criticality",
			label: __("Criticality"),
			fieldtype: "Select",
			options: "\nCritical\nImportant\nStandard\nBasic",
		},
		{ fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: "\nHIGH\nMEDIUM\nLOW" },
		{ fieldname: "answer", label: __("Answer"), fieldtype: "Select", options: "\nNO\nPARTIALLY" },
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "priority" && data) {
			const color = { HIGH: "red", MEDIUM: "orange", LOW: "green" }[data.priority];
			if (color) value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
