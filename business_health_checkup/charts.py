"""The workbook's dashboard and report charts as plain SVG, free of Frappe.

Drawn on the server so the Management Report print / PDF and the Owner Dashboard page show the same picture
without a chart library (Frappe's built-in charts have no radar type). Every label is escaped. A department
without applicable answers has no measured score: bars show "not assessed" instead of a zero-length bar, and
the radar marks the point with a hollow circle and "(not assessed)" in grey.

Charts (workbook): bar and radar of department scores (OWNER DASHBOARD!A9:B18, MANAGEMENT REPORT!B17:C26) and
the overall trend line (SCORE CALCULATION!B17:E21, which leaves out assessments with nothing answered).
"""

import math
from decimal import ROUND_HALF_UP, Decimal
from html import escape

GRID = "#d0d4d9"
TEXT = "#36414c"
MUTED = "#8d99a6"
BAR = "#5e64ff"


def _fmt(value) -> str:
	"""Like the workbook's "0%" format: halves round away from zero (54.5 -> 55%), as management.percent_text."""
	return f"{Decimal(str(float(value))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)}%"


def bar_chart(items, width: int = 640) -> str:
	"""Horizontal bars 0-100 %. `items` are (label, score percent, assessed) tuples."""
	row, label_w, top = 26, 170, 10
	plot_w = width - label_w - 60
	height = top + row * len(items) + 24
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
	]
	for pct in (0, 25, 50, 75, 100):
		x = label_w + plot_w * pct / 100
		parts.append(
			f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - 20}" stroke="{GRID}" stroke-width="1"/>'
		)
		parts.append(
			f'<text x="{x:.1f}" y="{height - 6}" font-size="10" fill="{MUTED}" text-anchor="middle">{pct}%</text>'
		)
	for i, (label, score, assessed) in enumerate(items):
		y = top + i * row
		parts.append(
			f'<text x="{label_w - 8}" y="{y + 16}" font-size="12" fill="{TEXT if assessed else MUTED}" '
			f'text-anchor="end">{escape(str(label))}</text>'
		)
		if assessed:
			w = plot_w * max(0.0, min(float(score or 0), 100.0)) / 100
			parts.append(f'<rect x="{label_w}" y="{y + 5}" width="{w:.1f}" height="15" fill="{BAR}"/>')
			parts.append(
				f'<text x="{label_w + w + 4:.1f}" y="{y + 16}" font-size="11" fill="{TEXT}">{_fmt(score or 0)}</text>'
			)
		else:
			parts.append(
				f'<text x="{label_w + 4}" y="{y + 16}" font-size="11" fill="{MUTED}">not assessed</text>'
			)
	parts.append("</svg>")
	return "".join(parts)


def radar_chart(items, size: int = 360) -> str:
	"""Radar of department scores 0-100 %. `items` are (label, score percent, assessed) tuples."""
	n = len(items)
	if n < 3:
		return ""
	pad = 90
	width, height = size + 2 * pad, size + 40
	cx, cy, radius = width / 2, size / 2 + 20, size / 2 - 10

	def point(i, pct):
		angle = -math.pi / 2 + 2 * math.pi * i / n
		r = radius * max(0.0, min(float(pct or 0), 100.0)) / 100
		return cx + r * math.cos(angle), cy + r * math.sin(angle)

	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'
	]
	for pct in (25, 50, 75, 100):
		ring = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, pct) for i in range(n)))
		parts.append(f'<polygon points="{ring}" fill="none" stroke="{GRID}" stroke-width="1"/>')
	for i, (label, _score, assessed) in enumerate(items):
		x, y = point(i, 100)
		parts.append(
			f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
		)
		lx, ly = point(i, 116)
		anchor = "middle" if abs(lx - cx) < 10 else ("start" if lx > cx else "end")
		text = escape(str(label)) + ("" if assessed else " (not assessed)")
		parts.append(
			f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="11" fill="{TEXT if assessed else MUTED}" '
			f'text-anchor="{anchor}">{text}</text>'
		)
	shape = " ".join(
		f"{x:.1f},{y:.1f}" for x, y in (point(i, s if a else 0) for i, (_l, s, a) in enumerate(items))
	)
	parts.append(
		f'<polygon points="{shape}" fill="{BAR}" fill-opacity="0.25" stroke="{BAR}" stroke-width="2"/>'
	)
	for i, (_label, score, assessed) in enumerate(items):
		x, y = point(i, score if assessed else 0)
		fill = BAR if assessed else "#ffffff"
		parts.append(
			f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{fill}" stroke="{BAR if assessed else MUTED}"/>'
		)
	parts.append("</svg>")
	return "".join(parts)


def trend_chart(points, width: int = 640, height: int = 220) -> str:
	"""Overall score per assessment, in date order. `points` are (label, score percent or None) pairs; None
	(nothing answered) is skipped like the workbook's NA() series (SCORE CALCULATION!B21)."""
	values = [(label, score) for label, score in points if score is not None]
	if not values:
		return ""
	left, right, top, bottom = 40, 20, 14, 46
	plot_w, plot_h = width - left - right, height - top - bottom
	step = plot_w / max(len(values) - 1, 1)

	def xy(i, score):
		return left + (i * step if len(values) > 1 else plot_w / 2), top + plot_h * (1 - float(score) / 100)

	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
	]
	for pct in (0, 25, 50, 75, 100):
		y = top + plot_h * (1 - pct / 100)
		parts.append(
			f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
		)
		parts.append(
			f'<text x="{left - 6}" y="{y + 4:.1f}" font-size="10" fill="{MUTED}" text-anchor="end">{pct}%</text>'
		)
	coords = [xy(i, score) for i, (_label, score) in enumerate(values)]
	if len(coords) > 1:
		line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
		parts.append(f'<polyline points="{line}" fill="none" stroke="{BAR}" stroke-width="2"/>')
	for (label, score), (x, y) in zip(values, coords, strict=True):
		parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{BAR}"/>')
		parts.append(
			f'<text x="{x:.1f}" y="{y - 8:.1f}" font-size="11" fill="{TEXT}" text-anchor="middle">{_fmt(score)}</text>'
		)
		parts.append(
			f'<text x="{x:.1f}" y="{height - 26}" font-size="10" fill="{MUTED}" text-anchor="middle">{escape(str(label))}</text>'
		)
	parts.append("</svg>")
	return "".join(parts)
