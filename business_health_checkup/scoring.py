"""Scoring rules of Business_Health_Checkup_System.xlsx, kept free of Frappe so they can be tested on their own.

Each function reproduces a workbook formula; the cell references are in the comments and in docs/workbook_audit.md.
Nothing here adds a business rule. `rank_departments` and `growth_status` keep the workbook's behaviour for
departments with nothing applicable answered (they take part with their score of 0); whether that should change
is open question Q-04, and callers must show such departments as not assessed (`Summary.assessed`). How a change
against a previous assessment is interpreted is not a workbook formula and is left to analysis.py / Q-11.

Scores are returned unrounded (the workbook only rounds for display, with the "0%" number format), and the
maturity band is always looked up from the unrounded score.

Callers pass the rules and the question snapshot explicitly, so a stored assessment can be re-scored with the
rules it was finalised with, whatever the masters say today.
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import MappingProxyType

WORKBOOK_DATA = Path(__file__).parent / "workbook_v1"

# Literal used by SCORE CALCULATION!I5:I15 and the department sheets' C5 when nothing applicable was answered.
NOT_ASSESSED = "Not Assessed"


@dataclass(frozen=True)
class Rules:
	answer_fraction: MappingProxyType  # answer -> share of the weight earned, SETTINGS!A5:B8
	excluded_answers: frozenset  # answers left out of earned and max ("N/A" in the department sheets' L7/M7)
	criticality_weight: MappingProxyType  # SETTINGS!D5:E8
	maturity_bands: tuple  # ((lower bound, label), ...) ascending, SETTINGS!A12:C16
	priority_matrix: MappingProxyType  # (criticality, answer) -> priority, SETTINGS!A19:C23
	priority_rank: MappingProxyType  # priority -> rank score, SETTINGS!E20:F22
	priority_phase: MappingProxyType  # priority -> 90-day phase label, SETTINGS!E20:G22
	priority_offsets: (
		MappingProxyType  # priority -> (start, due) days after the assessment date, SETTINGS!E20:I22
	)
	growth_plan_threshold: float | None = None  # GrowthThreshold, SETTINGS!B27
	strength_threshold: float | None = None  # StrengthThreshold, SETTINGS!B28

	@classmethod
	def from_dict(cls, data: dict) -> "Rules":
		"""Build rules from the rules.json layout (copies everything, so later edits to `data` change nothing)."""
		bands = sorted((float(b["lower_bound"]), b["label"]) for b in data["maturity_bands"])
		return cls(
			answer_fraction=MappingProxyType(
				{o["answer"]: float(o["score_fraction"]) for o in data["answer_options"]}
			),
			excluded_answers=frozenset(o["answer"] for o in data["answer_options"] if o["excluded"]),
			criticality_weight=MappingProxyType(
				{c["criticality"]: float(c["weight"]) for c in data["criticality_weights"]}
			),
			maturity_bands=tuple(bands),
			priority_matrix=MappingProxyType(
				{(p["criticality"], p["answer"]): p["priority"] for p in data["priority_matrix"]}
			),
			priority_rank=MappingProxyType(
				{p["priority"]: int(p["rank_score"]) for p in data["priority_rules"]}
			),
			priority_phase=MappingProxyType({p["priority"]: p["phase"] for p in data["priority_rules"]}),
			priority_offsets=MappingProxyType(
				{
					p["priority"]: (int(p["start_offset_days"]), int(p["due_offset_days"]))
					for p in data["priority_rules"]
				}
			),
			growth_plan_threshold=_optional_value(data, "growth_plan_threshold"),
			strength_threshold=_optional_value(data, "strength_threshold"),
		)


def _optional_value(data: dict, key: str) -> float | None:
	"""A `{"value": x}` parameter of rules.json, or None when the layout has none."""
	if data.get(key) is None:
		return None
	return float(data[key]["value"])


def load_workbook_rules() -> Rules:
	"""The SETTINGS values of the source workbook (workbook_v1/rules.json)."""
	return Rules.from_dict(json.loads((WORKBOOK_DATA / "rules.json").read_text()))


@dataclass(frozen=True)
class Question:
	"""The parts of a question that scoring depends on, as they stood when the assessment was taken."""

	question_id: str
	department: str
	criticality: str


@dataclass(frozen=True)
class QuestionResult:
	question_id: str
	department: str
	criticality: str
	weight: float
	answer: str | None
	earned: float
	max_points: float
	gap: float
	priority: str | None

	@property
	def answered(self) -> bool:
		return bool(self.answer)


@dataclass(frozen=True)
class Summary:
	questions: int
	answered: int
	completion: float
	earned: float
	max_points: float
	score: float
	maturity: str
	high: int
	medium: int
	low: int

	@property
	def assessed(self) -> bool:
		return self.max_points > 0

	@property
	def total_gaps(self) -> int:
		return self.high + self.medium + self.low


@dataclass(frozen=True)
class AssessmentResult:
	questions: tuple  # QuestionResult, in question order
	departments: MappingProxyType  # department code -> Summary, in the order departments first appear
	overall: Summary


def score_question(question: Question, answer: str | None, rules: Rules) -> QuestionResult:
	"""Earned, max, gap and priority of one answer (department sheets, columns F and K:O)."""
	if question.criticality not in rules.criticality_weight:
		raise ValueError(f"{question.question_id}: unknown criticality {question.criticality!r}")
	answer = answer or None
	if answer is not None and answer not in rules.answer_fraction:
		raise ValueError(f"{question.question_id}: unknown answer {answer!r}")

	weight = rules.criticality_weight[question.criticality]
	# L7: =IF(OR($B7="",K7="",K7="N/A"),0,$F7*INDEX(ScorePct,MATCH(K7,AnswerList,0)))   M7: same test, else $F7
	if answer is None or answer in rules.excluded_answers:
		earned = max_points = 0.0
	else:
		earned = weight * rules.answer_fraction[answer]
		max_points = weight
	gap = max_points - earned  # N7
	# O7: =IF(N7<=0,"",INDEX(PrioMatrix,MATCH(E7,PrioCrit,0),MATCH(K7,PrioAns,0))), blank when not in the matrix
	priority = rules.priority_matrix.get((question.criticality, answer)) if gap > 0 else None
	return QuestionResult(
		question.question_id,
		question.department,
		question.criticality,
		weight,
		answer,
		earned,
		max_points,
		gap,
		priority,
	)


def maturity_label(score: float, rules: Rules) -> str:
	"""Band whose lower bound is the largest one <= score, like MATCH(score, MatLower, 1) in SCORE CALCULATION!I5."""
	label = None
	for lower_bound, band in rules.maturity_bands:
		if score >= lower_bound:
			label = band
	if label is None:
		raise ValueError(f"score {score!r} is below the lowest maturity band")
	return label


def summarise(results, rules: Rules) -> Summary:
	"""Totals of SCORE CALCULATION!C:M for a set of question results (one department, or all of them)."""
	results = list(results)
	questions = len(results)
	answered = sum(r.answered for r in results)  # D5 counts N/A as answered
	earned = sum(r.earned for r in results)
	max_points = sum(r.max_points for r in results)
	score = earned / max_points if max_points else 0.0  # H5: =IF(G5=0,0,F5/G5)
	priorities = [r.priority for r in results]
	return Summary(
		questions=questions,
		answered=answered,
		completion=answered / questions if questions else 0.0,  # E5: =IF(C5=0,0,D5/C5)
		earned=earned,
		max_points=max_points,
		score=score,
		maturity=maturity_label(score, rules) if max_points else NOT_ASSESSED,  # I5
		high=priorities.count("HIGH"),
		medium=priorities.count("MEDIUM"),
		low=priorities.count("LOW"),
	)


def score_assessment(questions, answers: dict, rules: Rules) -> AssessmentResult:
	"""Score every question of an assessment; `answers` maps question_id to answer (missing = unanswered).

	The overall score is total earned / total applicable max over all departments (SCORE CALCULATION!F15:H15),
	so departments count in proportion to their applicable points, not equally.
	"""
	results = tuple(score_question(q, answers.get(q.question_id), rules) for q in questions)
	by_department = {}
	for result in results:
		by_department.setdefault(result.department, []).append(result)
	return AssessmentResult(
		questions=results,
		departments=MappingProxyType({d: summarise(rs, rules) for d, rs in by_department.items()}),
		overall=summarise(results, rules),
	)


def rank_gaps(results, rules: Rules) -> list:
	"""Gaps ordered as GAP ANALYSIS lists them: priority rank, then points lost, then question order.

	SCORE CALCULATION!Q25 sorts on P*10000000 + K*10000 + (1000-ROW()) for every row with a gap (K>0); a gap
	without a priority gets rank score 0 (P25).
	"""
	gaps = [(i, r) for i, r in enumerate(results) if r.gap > 0]
	gaps.sort(key=lambda item: (-rules.priority_rank.get(item[1].priority, 0), -item[1].gap, item[0]))
	return [r for _, r in gaps]


def growth_status(score: float, rules: Rules) -> str:
	"""Department status of BUSINESS GROWTH PLAN!E8:E17.

	=IF(C8<GrowthThreshold,"PRIORITY - GROWTH PLAN",IF(C8>=StrengthThreshold,"STRENGTH - LEVERAGE","MAINTAIN & IMPROVE"))
	C8 is the department score, which is 0 for a department with nothing applicable answered.
	"""
	if rules.growth_plan_threshold is None or rules.strength_threshold is None:
		raise ValueError("these rules have no growth plan / strength thresholds")
	if score < rules.growth_plan_threshold:
		return "PRIORITY - GROWTH PLAN"
	if score >= rules.strength_threshold:
		return "STRENGTH - LEVERAGE"
	return "MAINTAIN & IMPROVE"


# SCORE CALCULATION!T5 =H5+ROW()/1000000 and U5 =RANK(T5,$T$5:$T$14,1); the first department is on row 5.
FIRST_DEPARTMENT_ROW = 5


def rank_departments(scores) -> dict:
	"""Workbook rank of each department, 1 = weakest (SCORE CALCULATION!U5:U14).

	`scores` are (department code, score 0-1) pairs in workbook department order. The tie key adds ROW()/1000000,
	so equal scores rank in department order; scores closer than the row offset (at most 9e-6) would also be
	ordered by row, which the workbook's weights cannot produce (W-09). Reproduced exactly. Unassessed departments
	take part with their score of 0.
	"""
	keys = [(score + (FIRST_DEPARTMENT_ROW + i) / 1_000_000, code) for i, (code, score) in enumerate(scores)]
	return {code: rank for rank, (_, code) in enumerate(sorted(keys), 1)}


# GAP ANALYSIS!H7 =IF(C7>=3,"YES - 3+ HIGH gaps: systemic weakness",IF(F7>=8,"YES - many gaps in one function",""))
# The thresholds are literals in the formula, not SETTINGS values (W-07).
REPEATED_HIGH_GAPS = 3
REPEATED_TOTAL_GAPS = 8


def repeated_problem_area(high_gaps: int, total_gaps: int) -> str:
	"""GAP ANALYSIS "Repeated problem area?" for one department; "" when neither threshold is reached."""
	if high_gaps >= REPEATED_HIGH_GAPS:
		return "YES - 3+ HIGH gaps: systemic weakness"
	if total_gaps >= REPEATED_TOTAL_GAPS:
		return "YES - many gaps in one function"
	return ""


def suggested_dates(priority: str, assessment_date: date, rules: Rules) -> tuple:
	"""Suggested start and due dates of a gap (SCORE CALCULATION!T25:U25: AssessmentDate + PrioStart/PrioDue)."""
	start, due = rules.priority_offsets[priority]
	return assessment_date + timedelta(days=start), assessment_date + timedelta(days=due)
