// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

// UI only: every score is calculated on the server when the assessment is saved; the Results Summary shows the
// stored figures returned by business_health_checkup.assessments.get_results_summary.
const BHC_COVERAGE_COLORS = {
	"Not assessed (no answers)": "gray",
	"Not assessed (all N/A)": "gray",
	"Partly answered": "orange",
	"Fully answered": "blue",
};

frappe.ui.form.on("BHC Assessment", {
	setup(frm) {
		frm.set_query("previous_assessment", () => ({
			filters: { business: frm.doc.business, docstatus: 1, name: ["!=", frm.doc.name] },
		}));
		frm.set_query("scoring_model", () => ({ filters: { docstatus: 1 } }));
	},

	refresh(frm) {
		frm.get_field("results_summary").$wrapper.empty();
		if (frm.is_new()) return;

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Re-assessment"),
				() =>
					frappe.model.open_mapped_doc({
						method: "business_health_checkup.assessments.make_reassessment",
						frm,
					}),
				__("Create")
			);
			if (frappe.model.can_create("BHC Improvement Action")) {
				frm.add_custom_button(__("Improvement Actions"), () => bhc_create_actions_dialog(frm), __("Create"));
			}
		}
		const open_report = (report, filters) => frappe.set_route("query-report", report, filters);
		frm.add_custom_button(
			__("Gap Analysis"),
			() => open_report("BHC Gap Analysis", { assessment: frm.doc.name, status: frm.doc.status }),
			__("View")
		);
		frm.add_custom_button(
			__("Department Results"),
			() => open_report("BHC Department Results", { assessment: frm.doc.name, status: frm.doc.status }),
			__("View")
		);
		frm.add_custom_button(
			__("Management Report"),
			() =>
				window.open(
					`/printview?doctype=${encodeURIComponent("BHC Assessment")}&name=${encodeURIComponent(frm.doc.name)}` +
						`&format=${encodeURIComponent("BHC Management Report")}&no_letterhead=1`
				),
			__("View")
		);
		frm.add_custom_button(
			__("Owner Dashboard"),
			() => {
				frappe.route_options = { assessment: frm.doc.name };
				frappe.set_route("bhc-owner-dashboard");
			},
			__("View")
		);
		frm.add_custom_button(
			__("90 Day Plan"),
			() => open_report("BHC 90 Day Plan", { assessment: frm.doc.name }),
			__("View")
		);
		frm.add_custom_button(
			__("Improvement Actions"),
			() => frappe.set_route("List", "BHC Improvement Action", { assessment: frm.doc.name }),
			__("View")
		);
		if (frm.doc.previous_assessment) {
			frm.add_custom_button(
				__("Comparison with Previous"),
				() => open_report("BHC Assessment Comparison", { assessment: frm.doc.name }),
				__("View")
			);
		}
		frm.add_custom_button(__("Verify Results"), () =>
			frappe
				.call("business_health_checkup.assessments.verify_results", { name: frm.doc.name })
				.then(({ message }) =>
					frappe.msgprint(
						message.matches
							? __("Stored results match the scoring model.")
							: __("Stored results differ:") + "<br>" + message.differences.map(frappe.utils.escape_html).join("<br>")
					)
				)
		);

		frappe
			.call("business_health_checkup.assessments.get_results_summary", { name: frm.doc.name })
			.then(({ message }) => frm.get_field("results_summary").$wrapper.html(bhc_results_html(message)));
	},
});

function bhc_results_html(s) {
	const esc = frappe.utils.escape_html;
	const pct = (v) => `${format_number(v || 0, null, 1)}%`;
	const pill = (text, color) => `<span class="indicator-pill ${color}">${esc(text)}</span>`;
	const link = (name) => `<a href="/app/bhc-assessment/${encodeURIComponent(name)}">${esc(name)}</a>`;

	const rows = [...s.departments]
		.sort((a, b) => a.workbook_rank - b.workbook_rank)
		.map((d) => {
			const not_assessed = !d.assessed;
			const score = not_assessed
				? `<span class="text-muted" title="${__("No applicable answer: not a measured score")}">${pct(d.score_percent)}</span>`
				: pct(d.score_percent);
			return `<tr${not_assessed ? ' class="text-muted"' : ""}>
				<td>${d.workbook_rank}</td>
				<td>${esc(d.department_name || d.department)}</td>
				<td>${pill(d.coverage, BHC_COVERAGE_COLORS[d.coverage] || "gray")}</td>
				<td class="text-right">${d.answered} / ${d.questions}</td>
				<td class="text-right">${d.not_applicable}</td>
				<td class="text-right">${score}</td>
				<td>${esc(d.maturity || "")}</td>
				<td class="text-right">${d.high_gaps} / ${d.medium_gaps} / ${d.low_gaps}</td>
				<td>${esc(d.growth_status || "")}</td>
			</tr>`;
		})
		.join("");

	const actions = s.actions || { gaps: 0, total: 0, by_status: {} };
	const by_status = Object.entries(actions.by_status)
		.map(([status, count]) => `${esc(status)} ${count}`)
		.join(", ");
	const actions_line = `${__("Improvement actions")}: ${actions.total} ${__("for")} ${actions.gaps} ${__("gaps")}${
		by_status ? ` (${by_status})` : ""
	}`;

	const related = [];
	if (s.previous) {
		related.push(`${__("Previous assessment")}: ${link(s.previous.name)} (${esc(s.previous.status)}, ${pct(s.previous.overall_score)})`);
	}
	for (const r of s.reassessments) {
		related.push(`${__("Re-assessment")}: ${link(r.name)} (${esc(r.status)}, ${pct(r.overall_score)})`);
	}

	return `<div class="bhc-results">
		<p>
			<b>${pct(s.overall_score)}</b> · ${esc(s.overall_maturity || "")} · ${pill(s.coverage, BHC_COVERAGE_COLORS[s.coverage] || "gray")}
			<br>${__("Answered")}: ${s.answered} / ${s.questions} · ${__("N/A")}: ${s.not_applicable} · ${__("Unanswered")}: ${s.unanswered}
			· ${__("Gaps")}: ${pill(`HIGH ${s.high_gaps}`, "red")} ${pill(`MEDIUM ${s.medium_gaps}`, "orange")} ${pill(`LOW ${s.low_gaps}`, "green")}
		</p>
		<table class="table table-bordered table-sm">
			<thead><tr>
				<th title="${__("SCORE CALCULATION!U5: 1 = weakest; departments without applicable answers take part with 0 %")}">${__("Rank (workbook)")}</th>
				<th>${__("Department")}</th><th>${__("Coverage")}</th><th>${__("Answered")}</th><th>${__("N/A")}</th>
				<th>${__("Score")}</th><th>${__("Maturity")}</th><th>${__("Gaps H / M / L")}</th><th>${__("Growth Plan Status (workbook)")}</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>
		<p class="text-muted small">${__(
			"Unanswered and N/A questions are left out of the score. A department marked Not assessed has no applicable answer: its 0 % and its rank follow the workbook formula and are not a measured result."
		)}</p>
		<p>${actions_line}</p>
		${related.length ? `<p>${related.join("<br>")}</p>` : ""}
	</div>`;
}

// Q-07 (open): actions are created only for the gaps the user selects; nothing is pre-selected.
function bhc_create_actions_dialog(frm) {
	frappe
		.call("business_health_checkup.actions.get_eligible_gaps", { assessment: frm.doc.name })
		.then(({ message: gaps }) => {
			const without_action = gaps.filter((g) => !g.action);
			if (!without_action.length) {
				frappe.msgprint(__("Every gap of this assessment already has an improvement action."));
				return;
			}
			const dialog = new frappe.ui.Dialog({
				title: __("Create Improvement Actions"),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						options: `<p class="text-muted">${__(
							"Tick the gaps that should become improvement actions. Gaps you leave unticked stay gaps; nothing is created for them. Priority, phase and suggested dates come from this assessment."
						)}</p>`,
					},
					{
						fieldname: "gaps",
						fieldtype: "Table",
						label: __("Gaps without an action"),
						cannot_add_rows: true,
						cannot_delete_rows: true,
						in_place_edit: false,
						data: without_action,
						fields: [
							{ fieldname: "gap_rank", label: __("Gap No."), fieldtype: "Int", read_only: 1, in_list_view: 1, columns: 1 },
							{ fieldname: "question_code", label: __("Question ID"), fieldtype: "Data", read_only: 1, in_list_view: 1, columns: 1 },
							{ fieldname: "priority", label: __("Priority"), fieldtype: "Data", read_only: 1, in_list_view: 1, columns: 1 },
							{ fieldname: "phase", label: __("Phase"), fieldtype: "Data", read_only: 1, in_list_view: 1, columns: 1 },
							{ fieldname: "question_text", label: __("Question"), fieldtype: "Small Text", read_only: 1, in_list_view: 1, columns: 3 },
							{ fieldname: "recommendation", label: __("Recommendation"), fieldtype: "Small Text", read_only: 1, in_list_view: 1, columns: 3 },
						],
					},
					{ fieldtype: "Section Break" },
					{ fieldname: "responsible", fieldtype: "Data", label: __("Responsible (all selected)") },
					{
						fieldname: "responsible_user",
						fieldtype: "Link",
						options: "User",
						label: __("Responsible User (optional)"),
						description: __("Must already be assigned to this business"),
						get_query: () => ({
							query: "business_health_checkup.actions.responsible_user_query",
							filters: { business: frm.doc.business },
						}),
					},
					{ fieldtype: "Column Break" },
					{
						fieldname: "use_suggested_dates",
						fieldtype: "Check",
						label: __("Use the suggested dates as the agreed Start and Target dates"),
					},
				],
				primary_action_label: __("Create Actions"),
				primary_action(values) {
					const selected = dialog.fields_dict.gaps.grid.get_selected_children().map((row) => row.question_code);
					if (!selected.length) {
						frappe.msgprint(__("Select at least one gap"));
						return;
					}
					frappe
						.call({
							method: "business_health_checkup.actions.create_actions",
							args: {
								assessment: frm.doc.name,
								questions: selected,
								responsible: values.responsible,
								responsible_user: values.responsible_user,
								use_suggested_dates: values.use_suggested_dates ? 1 : 0,
							},
							freeze: true,
						})
						.then(({ message }) => {
							dialog.hide();
							const created = message.filter((row) => row.created).length;
							frappe.show_alert({ message: __("{0} improvement action(s) created", [created]), indicator: "green" });
							frappe.set_route("List", "BHC Improvement Action", { assessment: frm.doc.name });
						});
				},
			});
			dialog.show();
		});
}
