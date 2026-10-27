// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

const BHC_NOT_ASSESSED = ["Not assessed (no answers)", "Not assessed (all N/A)"];

frappe.query_reports["BHC Department Results"] = {
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
			fieldname: "coverage",
			label: __("Coverage"),
			fieldtype: "Select",
			options: ["", ...BHC_NOT_ASSESSED, "Partly answered", "Fully answered"].join("\n"),
		},
		{
			fieldname: "sort_by",
			label: __("Sort By"),
			fieldtype: "Select",
			options: "Rank (weakest first)\nDepartment order",
			default: "Rank (weakest first)",
		},
	],

	// Display only: a department without applicable answers keeps its stored 0 %, shown as "not assessed".
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		const not_assessed = BHC_NOT_ASSESSED.includes(data.coverage);
		if (column.fieldname === "coverage") {
			const color = not_assessed ? "gray" : data.coverage === "Partly answered" ? "orange" : "blue";
			return `<span class="indicator-pill ${color}">${value}</span>`;
		}
		if (column.fieldname === "total_gaps" && data.total_gaps) {
			const query = new URLSearchParams({ assessment: data.assessment, department: data.department });
			return `<a href="/app/query-report/${encodeURIComponent("BHC Gap Analysis")}?${query}" title="${__(
				"Open the gaps of this department"
			)}">${value}</a>`;
		}
		if (not_assessed && ["score_percent", "workbook_rank", "maturity"].includes(column.fieldname)) {
			return `<span class="text-muted" title="${__("No applicable answer: not a measured score")}">${value}</span>`;
		}
		return value;
	},
};
