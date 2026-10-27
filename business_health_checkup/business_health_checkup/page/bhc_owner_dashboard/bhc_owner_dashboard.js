// Copyright (c) 2026, Skydot Infotech and contributors
// For license information, please see license.txt

// OWNER DASHBOARD of the workbook. Display only: every figure and chart comes from
// business_health_checkup.management.get_owner_dashboard, which checks that the user may read the assessment.
frappe.pages["bhc-owner-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Business Health Dashboard"), single_column: true });
	const body = $('<div class="bhc-owner-dashboard"></div>').appendTo(page.main);

	const business = page.add_field({
		fieldname: "business",
		label: __("Business"),
		fieldtype: "Link",
		options: "BHC Business",
		change() {
			const value = business.get_value();
			if (!value) return;
			// Convenience only: start with the most recent assessment of the business; any other can be chosen.
			frappe.db
				.get_list("BHC Assessment", {
					filters: { business: value, docstatus: ["<", 2] },
					fields: ["name"],
					order_by: "assessment_date desc",
					limit: 1,
				})
				.then((rows) => assessment.set_value(rows.length ? rows[0].name : ""));
		},
	});
	const assessment = page.add_field({
		fieldname: "assessment",
		label: __("Assessment"),
		fieldtype: "Link",
		options: "BHC Assessment",
		get_query: () => ({ filters: business.get_value() ? { business: business.get_value() } : {} }),
		change: () => load(),
	});
	wrapper.bhc = { business, assessment };

	function load() {
		const name = assessment.get_value();
		if (!name) {
			body.html(`<p class="text-muted" style="padding: 20px">${__("Select a business and an assessment.")}</p>`);
			return;
		}
		frappe
			.call("business_health_checkup.management.get_owner_dashboard", { name })
			.then(({ message }) => body.html(bhc_dashboard_html(message)));
	}
	load();
};

frappe.pages["bhc-owner-dashboard"].on_page_show = function (wrapper) {
	const name = frappe.route_options && frappe.route_options.assessment;
	if (name && wrapper.bhc) {
		frappe.route_options = null;
		wrapper.bhc.assessment.set_value(name);
	}
};

function bhc_dashboard_html(d) {
	const esc = frappe.utils.escape_html;
	const h = d.header;
	const c = d.cards;
	const card = (label, value, note) => `<div class="col-sm-3" style="margin-bottom: 10px">
		<div style="border: 1px solid var(--border-color); border-radius: 6px; padding: 10px">
			<div class="text-muted small">${esc(label)}</div>
			<div style="font-size: 20px; font-weight: 600">${esc(String(value))}</div>
			${note ? `<div class="text-muted small">${esc(note)}</div>` : ""}
		</div></div>`;
	const link = (route, label) => `<a href="${route}">${esc(label)}</a>`;
	const name = encodeURIComponent(h.assessment);
	const report = (title) => `/app/query-report/${encodeURIComponent(title)}?assessment=${name}`;

	const rows = d.heat_map
		.map(
			(r) => `<tr${r.assessed ? "" : ' class="text-muted"'}>
				<td><span style="display:inline-block;width:12px;height:12px;margin-right:6px;background:${r.color}"></span>${esc(r.label)}</td>
				<td class="text-right">${esc(r.score_text)}</td>
				<td>${esc(r.assessed ? r.short_maturity || "" : __("Not assessed"))}</td>
				<td class="text-right">${esc(r.previous_text || "")}</td>
				<td class="text-right">${esc(r.change_text || "")}</td>
				<td class="text-right">${r.total_gaps}</td>
				<td>${esc(r.coverage)}</td>
			</tr>`
		)
		.join("");
	const o = d.overall_row;
	const trend = d.trend
		.map(
			(t) => `<tr${t.current ? ' style="font-weight:600"' : ""}>
				<td>${link(`/app/bhc-assessment/${encodeURIComponent(t.name)}`, t.assessment_label || t.name)}</td>
				<td class="text-right">${esc(t.score_text)}</td><td class="text-right">${t.answered_questions}</td>
				<td>${esc(frappe.datetime.str_to_user(t.assessment_date) || "")}</td><td>${esc(t.status)}</td></tr>`
		)
		.join("");

	return `<div style="padding: 10px 15px">
		<h4 style="margin-top: 0">${esc(h.company || "")}</h4>
		<p class="text-muted">${esc(h.assessment_label || h.assessment)} · ${__("Assessment date")}: ${esc(h.assessment_date_text)}
			· ${__("Industry")}: ${esc(h.industry || "")} · ${__("Consultant")}: ${esc(h.consultant || "")}
			· ${esc(h.status)}</p>
		${h.docstatus !== 1 ? `<div class="alert alert-warning">${__("This assessment is not finalised; its results can still change.")}</div>` : ""}
		<div class="row">
			${card(__("Business Health Score"), c.score_text)}
			${card(__("Maturity Level"), c.maturity || "")}
			${card(__("Questions Answered"), c.answered)}
			${card(__("HIGH Priority Gaps"), c.high_gaps)}
			${card(__("MEDIUM Priority Gaps"), c.medium_gaps)}
			${card(__("LOW Priority Gaps"), c.low_gaps)}
			${card(__("Actions Open"), c.actions_open, __("Open + In Progress + Hold; overdue: {0}", [c.actions_overdue]))}
			${card(__("Actions Completed"), c.actions_completed, __("Gaps with an action: {0}", [c.gaps_with_action]))}
		</div>

		<h5>${__("Department Performance & Heat Map")}</h5>
		<table class="table table-bordered table-sm">
			<thead><tr><th>${__("Department")}</th><th class="text-right">${__("Score")}</th><th>${__("Status")}</th>
				<th class="text-right">${__("Previous")}</th><th class="text-right">${__("Change (points)")}</th>
				<th class="text-right">${__("Gaps")}</th><th>${__("Coverage")}</th></tr></thead>
			<tbody>${rows}
				<tr style="font-weight:600"><td><span style="display:inline-block;width:12px;height:12px;margin-right:6px;background:${o.color}"></span>${__("OVERALL")}</td>
					<td class="text-right">${esc(c.score_text)}</td><td>${esc(o.maturity || "")}</td>
					<td class="text-right">${esc(o.previous_text)}</td>
					<td class="text-right">${esc(o.change_text)}</td>
					<td class="text-right">${o.total_gaps}</td><td></td></tr>
			</tbody>
		</table>
		<p class="text-muted small">${__(
			"Heat map: red < 40% | orange 40-59% | yellow 60-74% | light green 75-89% | green >= 90%; grey = not assessed (no applicable answer, the 0 % is not a measured score). Previous = the linked previous assessment; change only when both have applicable answers."
		)}</p>
		${o.limitations.length ? `<p class="text-muted small">${o.limitations.map(esc).join("<br>")}</p>` : ""}
		<div class="row"><div class="col-md-6">${d.charts.bar}</div><div class="col-md-6">${d.charts.radar}</div></div>

		<h5>${__("Business Health Improvement Trend")}</h5>
		<table class="table table-bordered table-sm">
			<thead><tr><th>${__("Assessment")}</th><th class="text-right">${__("Overall Score")}</th>
				<th class="text-right">${__("Answered")}</th><th>${__("Date")}</th><th>${__("Status")}</th></tr></thead>
			<tbody>${trend}</tbody>
		</table>
		${d.charts.trend}

		<h5>${__("Owner's 10-Number Business Dashboard")}</h5>
		<p class="text-muted">${esc(d.kpi.reason)}</p>

		<p>${__("Open")}: ${link(`/app/bhc-assessment/${name}`, __("Assessment"))} ·
			${link(report("BHC Gap Analysis"), __("Gap Analysis"))} ·
			${link(report("BHC Department Results"), __("Department Results"))} ·
			${link(report("BHC 90 Day Plan"), __("90 Day Plan"))} ·
			${link(
				`/printview?doctype=${encodeURIComponent("BHC Assessment")}&name=${name}&format=${encodeURIComponent("BHC Management Report")}&no_letterhead=1`,
				__("Management Report")
			)}</p>
	</div>`;
}
