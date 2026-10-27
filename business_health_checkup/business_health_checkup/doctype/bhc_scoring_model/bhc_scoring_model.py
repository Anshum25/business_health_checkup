# Copyright (c) 2026, Skydot Infotech and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document

from business_health_checkup import scoring

ANSWERS = ("YES", "PARTIALLY", "NO", "N/A")
CRITICALITIES = ("Critical", "Important", "Standard", "Basic")
GAP_ANSWERS = ("NO", "PARTIALLY")
PRIORITIES = ("HIGH", "MEDIUM", "LOW")


class BHCScoringModel(Document):
	"""One version of the SETTINGS rules. Submitted versions are immutable (standard Frappe submission); a rule
	change is a new version (amend or new document). Assessments link the version they were scored with."""

	def validate(self):
		if problems := self.get_problems():
			frappe.throw("<br>".join(problems), title=_("Invalid Scoring Model"))
		self.rules_hash = rules_hash(self.as_rules_dict())
		if self.is_default and self.docstatus != 1:
			frappe.throw(_("Only a submitted scoring model can be the default"))

	def on_submit(self):
		if self.is_default:
			self.clear_other_defaults()

	def on_update_after_submit(self):
		if self.is_default:
			self.clear_other_defaults()

	def on_cancel(self):
		if self.is_default:
			self.db_set("is_default", 0)

	def clear_other_defaults(self):
		for name in frappe.get_all(
			"BHC Scoring Model", filters={"is_default": 1, "name": ("!=", self.name)}, pluck="name"
		):
			frappe.db.set_value("BHC Scoring Model", name, "is_default", 0)

	def get_problems(self) -> list[str]:
		"""Everything that would make the rules incomplete or different in kind from the workbook's."""
		problems = []

		answers = [row.answer for row in self.answer_scores]
		if sorted(answers) != sorted(ANSWERS):
			problems.append(_("Answer Scores must list YES, PARTIALLY, NO and N/A exactly once each"))
		for row in self.answer_scores:
			if not 0 <= (row.score_fraction or 0) <= 1:
				problems.append(_("Share of weight for {0} must be between 0 and 1").format(row.answer))
			# The department sheets test K7="N/A" literally (L7/M7): only N/A is left out of the score.
			if bool(row.excluded) != (row.answer == "N/A"):
				problems.append(_("Only N/A can be excluded from the score"))

		criticalities = [row.criticality for row in self.criticality_weights]
		if sorted(criticalities) != sorted(CRITICALITIES):
			problems.append(
				_("Criticality Weights must list Critical, Important, Standard and Basic exactly once each")
			)
		if any((row.weight or 0) <= 0 for row in self.criticality_weights):
			problems.append(_("Every criticality weight must be more than 0"))

		bounds = [row.lower_bound for row in self.maturity_bands]
		labels = [(row.label or "").strip() for row in self.maturity_bands]
		if not bounds:
			problems.append(_("At least one maturity band is required"))
		else:
			if len(set(bounds)) != len(bounds):
				problems.append(_("Maturity band lower bounds must be unique"))
			if min(bounds) != 0:
				problems.append(_("The lowest maturity band must start at 0"))
			if any(not 0 <= (b or 0) <= 1 for b in bounds):
				problems.append(_("Maturity band lower bounds must be between 0 and 1"))
			if not all(labels) or len(set(labels)) != len(labels):
				problems.append(_("Maturity levels need a unique label"))

		pairs = [(row.criticality, row.answer) for row in self.priority_matrix]
		expected = [(c, a) for c in CRITICALITIES for a in GAP_ANSWERS]
		if sorted(pairs) != sorted(expected):
			problems.append(
				_("Priority Matrix must give one priority for NO and PARTIALLY of every criticality")
			)

		priorities = [row.priority for row in self.priority_rules]
		if sorted(priorities) != sorted(PRIORITIES):
			problems.append(_("Priority Rules must list HIGH, MEDIUM and LOW exactly once each"))
		ranks = [row.rank_score for row in self.priority_rules]
		if any((r or 0) < 1 for r in ranks) or len(set(ranks)) != len(ranks):
			problems.append(_("Priority rank scores must be unique and 1 or more"))
		for row in self.priority_rules:
			if not (row.phase or "").strip():
				problems.append(_("Priority {0} needs a 90-day phase").format(row.priority))
			if (row.start_offset_days or 0) < 0 or (row.due_offset_days or 0) < (row.start_offset_days or 0):
				problems.append(_("Priority {0}: due day must not be before start day").format(row.priority))

		for fieldname in ("growth_plan_threshold", "strength_threshold", "kpi_watch_tolerance"):
			if not 0 <= (self.get(fieldname) or 0) <= 1:
				problems.append(_("{0} must be between 0 and 1").format(_(self.meta.get_label(fieldname))))
		if (self.growth_plan_threshold or 0) > (self.strength_threshold or 0):
			problems.append(_("The growth plan trigger cannot be above the strength threshold"))

		if not problems:
			try:
				scoring.Rules.from_dict(self.as_rules_dict())
			except (KeyError, TypeError, ValueError) as e:
				problems.append(_("The scoring engine cannot use these rules: {0}").format(e))
		return problems

	def as_rules_dict(self) -> dict:
		"""The rules in the workbook_v1/rules.json layout, in a fixed order (row order does not matter)."""

		def order(values, key):
			return sorted(values, key=key)

		return {
			"answer_options": order(
				[
					{
						"answer": r.answer,
						"score_fraction": float(r.score_fraction or 0),
						"excluded": bool(r.excluded),
					}
					for r in self.answer_scores
				],
				key=lambda o: _index(ANSWERS, o["answer"]),
			),
			"criticality_weights": order(
				[
					{"criticality": r.criticality, "weight": float(r.weight or 0)}
					for r in self.criticality_weights
				],
				key=lambda o: _index(CRITICALITIES, o["criticality"]),
			),
			"maturity_bands": order(
				[{"lower_bound": float(r.lower_bound or 0), "label": r.label} for r in self.maturity_bands],
				key=lambda o: o["lower_bound"],
			),
			"priority_matrix": order(
				[
					{"criticality": r.criticality, "answer": r.answer, "priority": r.priority}
					for r in self.priority_matrix
				],
				key=lambda o: (_index(CRITICALITIES, o["criticality"]), _index(GAP_ANSWERS, o["answer"])),
			),
			"priority_rules": order(
				[
					{
						"priority": r.priority,
						"rank_score": int(r.rank_score or 0),
						"phase": r.phase,
						"start_offset_days": int(r.start_offset_days or 0),
						"due_offset_days": int(r.due_offset_days or 0),
					}
					for r in self.priority_rules
				],
				key=lambda o: _index(PRIORITIES, o["priority"]),
			),
			"growth_plan_threshold": {"value": float(self.growth_plan_threshold or 0)},
			"strength_threshold": {"value": float(self.strength_threshold or 0)},
			"kpi_watch_tolerance": {"value": float(self.kpi_watch_tolerance or 0)},
		}

	def get_rules(self) -> scoring.Rules:
		return scoring.Rules.from_dict(self.as_rules_dict())


def _index(values, value):
	return values.index(value) if value in values else len(values)


def rules_hash(rules: dict) -> str:
	return hashlib.sha256(json.dumps(rules, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def get_default_scoring_model() -> str | None:
	names = frappe.get_all("BHC Scoring Model", filters={"docstatus": 1, "is_default": 1}, pluck="name")
	if len(names) > 1:
		frappe.throw(_("More than one scoring model is marked as default"))
	return names[0] if names else None
