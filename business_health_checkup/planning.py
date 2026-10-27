"""ACTION PLAN and 90 DAY PLAN rules of the workbook, free of Frappe so they can be tested on their own.

Each function reproduces a workbook formula or validation; the cell references are in the comments.

- An action's 90-day phase and suggested dates come from its priority and the source assessment's scoring rules
  (SETTINGS!E20:I22 via scoring.Rules), counted from the assessment date. Without an assessment date there are
  no suggested dates: nothing falls back to today (the workbook's COMPANY PROFILE!C32 does, see W-06).
- "Overdue" depends only on the agreed Target Date, never on a suggested date (ACTION PLAN!Q8).
"""

from datetime import date

from business_health_checkup import scoring

# SETTINGS!A34:A37 (StatusList), the ACTION PLAN!O8:O207 dropdown.
OPEN = "Open"
IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
HOLD = "Hold"
STATUSES = (OPEN, IN_PROGRESS, COMPLETED, HOLD)

# ACTION PLAN!L8:M207 data validation: "date greater than 36526", i.e. after 1 January 2000.
DATES_AFTER = date(2000, 1, 1)


def suggested_dates(priority: str, assessment_date: date | None, rules: scoring.Rules) -> tuple:
	"""(start, due) of SCORE CALCULATION!T25:U25, or (None, None) when the assessment has no date."""
	if not assessment_date:
		return None, None
	return scoring.suggested_dates(priority, assessment_date, rules)


def is_valid_plan_date(value: date | None) -> bool:
	"""ACTION PLAN!L8:M207 accepts a blank or a date after 1 January 2000."""
	return value is None or value > DATES_AFTER


def is_overdue(status: str | None, target_date: date | None, today: date) -> bool:
	"""ACTION PLAN!Q8 =IF(AND(E8<>"",O8<>"Completed",M8<>"",M8<TODAY()),"OVERDUE","").

	Every action has a priority (E8), so only the status and the agreed Target Date (M8) matter; a target date of
	today is not overdue yet, and an action without a target date never is.
	"""
	return bool(target_date) and status != COMPLETED and target_date < today


def action_counters(actions, today: date) -> dict:
	"""ACTION PLAN!A4:G4 for a set of actions given as (status, target_date) pairs.

	A blank status counts as Open (B4); Completion % = Completed / Total (G4, 0 when there are none).
	"""
	actions = list(actions)
	statuses = [status or OPEN for status, _target in actions]
	total = len(actions)
	completed = statuses.count(COMPLETED)
	return {
		"total": total,
		"open": statuses.count(OPEN),
		"in_progress": statuses.count(IN_PROGRESS),
		"completed": completed,
		"hold": statuses.count(HOLD),
		"overdue": sum(1 for status, target in actions if is_overdue(status, target, today)),
		"completion": completed / total if total else 0.0,
	}
