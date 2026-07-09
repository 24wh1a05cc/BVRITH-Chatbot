"""
tools/executors.py
------------------
Python execution functions for every BVRIT tool.

Each function:
  • Accepts validated arguments (already checked by validators/).
  • Returns a structured dict with a human-readable 'summary' field that
    the router injects back into the LLM as a ToolMessage.
  • Raises ToolExecutionError on unrecoverable problems.

NO LLM calls happen here — pure Python arithmetic only.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, Optional


class ToolExecutionError(Exception):
    """Raised when a tool cannot complete its computation."""


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 – fee_calculator
# ─────────────────────────────────────────────────────────────────────────────

def execute_fee_calculator(
    annual_fee: float,
    years: int,
    scholarship_percentage: Optional[float] = None,
    hostel_fee: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate multi-year BVRIT fee with optional scholarship and hostel.

    Returns
    -------
    dict with keys:
        annual_fee, years, scholarship_percentage, hostel_fee,
        annual_fee_after_scholarship, annual_total_with_hostel,
        grand_total, scholarship_savings, summary (str)
    """
    # ── validation ──────────────────────────────────────────────────────────
    if annual_fee <= 0:
        raise ToolExecutionError(f"annual_fee must be positive, got {annual_fee}")
    if years <= 0 or years > 10:
        raise ToolExecutionError(f"years must be between 1 and 10, got {years}")
    if scholarship_percentage is not None:
        if not (0 <= scholarship_percentage <= 100):
            raise ToolExecutionError(
                f"scholarship_percentage must be 0–100, got {scholarship_percentage}"
            )
    if hostel_fee is not None and hostel_fee < 0:
        raise ToolExecutionError(f"hostel_fee cannot be negative, got {hostel_fee}")

    # ── computation ─────────────────────────────────────────────────────────
    scholarship_pct = scholarship_percentage or 0.0
    h_fee = hostel_fee or 0.0

    discount = annual_fee * (scholarship_pct / 100)
    annual_after_scholarship = annual_fee - discount
    annual_with_hostel = annual_after_scholarship + h_fee
    grand_total = annual_with_hostel * years
    total_savings = discount * years

    # ── human-readable summary ───────────────────────────────────────────────
    lines = [
        f"Fee Calculation for {years} Year(s) at BVRIT:",
        f"  Annual tuition fee          : ₹{annual_fee:,.0f}",
    ]
    if scholarship_pct:
        lines.append(f"  Scholarship discount ({scholarship_pct}%)   : −₹{discount:,.0f}/year")
        lines.append(f"  Annual fee after scholarship : ₹{annual_after_scholarship:,.0f}")
    if h_fee:
        lines.append(f"  Annual hostel fee            : ₹{h_fee:,.0f}")
        lines.append(f"  Annual total (tuition+hostel): ₹{annual_with_hostel:,.0f}")
    lines.append(f"  ──────────────────────────────────────────")
    lines.append(f"  GRAND TOTAL ({years} years)        : ₹{grand_total:,.0f}")
    if scholarship_pct:
        lines.append(f"  Total scholarship savings    : ₹{total_savings:,.0f}")

    return {
        "annual_fee": annual_fee,
        "years": years,
        "scholarship_percentage": scholarship_pct,
        "hostel_fee": h_fee,
        "annual_fee_after_scholarship": round(annual_after_scholarship, 2),
        "annual_total_with_hostel": round(annual_with_hostel, 2),
        "grand_total": round(grand_total, 2),
        "scholarship_savings": round(total_savings, 2),
        "summary": "\n".join(lines),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 – date_checker
# ─────────────────────────────────────────────────────────────────────────────

def execute_date_checker(target_date: str) -> Dict[str, Any]:
    """
    Compare target_date (YYYY-MM-DD) against today and return status.

    Returns
    -------
    dict with keys:
        target_date, today, status ('past'|'today'|'upcoming'),
        days_remaining (int, 0 if past/today), days_elapsed (int),
        summary (str)
    """
    # ── parse ────────────────────────────────────────────────────────────────
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise ToolExecutionError(
            f"Invalid date format '{target_date}'. Expected YYYY-MM-DD (e.g. 2025-07-31)."
        )

    today = date.today()
    delta = (target - today).days  # positive = future, negative = past

    if delta > 0:
        status = "upcoming"
        days_remaining = delta
        days_elapsed = 0
        summary = (
            f"📅 Date Status: {target_date}\n"
            f"  Today               : {today}\n"
            f"  Status              : ✅ UPCOMING\n"
            f"  Days remaining      : {days_remaining} day(s)\n"
            f"  Deadline has NOT passed — there is still time."
        )
    elif delta == 0:
        status = "today"
        days_remaining = 0
        days_elapsed = 0
        summary = (
            f"📅 Date Status: {target_date}\n"
            f"  Today               : {today}\n"
            f"  Status              : 🔔 TODAY — This is the deadline/event day!"
        )
    else:
        status = "past"
        days_remaining = 0
        days_elapsed = abs(delta)
        summary = (
            f"📅 Date Status: {target_date}\n"
            f"  Today               : {today}\n"
            f"  Status              : ❌ PAST\n"
            f"  Days elapsed        : {days_elapsed} day(s) ago\n"
            f"  This deadline/event has already passed."
        )

    return {
        "target_date": target_date,
        "today": str(today),
        "status": status,
        "days_remaining": days_remaining,
        "days_elapsed": days_elapsed,
        "delta_days": delta,
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 – percentage_calculator
# ─────────────────────────────────────────────────────────────────────────────

def execute_percentage_calculator(
    value: float,
    percentage: float,
    operation: str,
) -> Dict[str, Any]:
    """
    Perform percentage arithmetic.

    Operations
    ----------
    increase  : result = value × (1 + pct/100)
    decrease  : result = value × (1 − pct/100)
    calculate : result = (value / percentage) × 100   [percentage = total/denominator]

    Returns
    -------
    dict with keys: value, percentage, operation, result, summary (str)
    """
    # ── validation ──────────────────────────────────────────────────────────
    VALID_OPS = {"increase", "decrease", "calculate"}
    if operation not in VALID_OPS:
        raise ToolExecutionError(
            f"operation must be one of {VALID_OPS}, got '{operation}'"
        )
    if operation in ("increase", "decrease") and not (0 <= percentage <= 10_000):
        raise ToolExecutionError(
            f"percentage must be 0–10000 for '{operation}', got {percentage}"
        )
    if operation == "calculate" and percentage == 0:
        raise ToolExecutionError("Cannot divide by zero: 'percentage' (total) must be non-zero.")
    if math.isinf(value) or math.isinf(percentage):
        raise ToolExecutionError("Inputs must be finite numbers.")
    if abs(value) > 1e12 or abs(percentage) > 1e12:
        raise ToolExecutionError("Input values are too large (max 1 trillion).")

    # ── computation ─────────────────────────────────────────────────────────
    if operation == "increase":
        result = value * (1 + percentage / 100)
        summary = (
            f"Percentage Increase:\n"
            f"  Base value          : {value:,.2f}\n"
            f"  Increase by         : {percentage}%\n"
            f"  Amount added        : {value * percentage / 100:,.2f}\n"
            f"  Result              : {result:,.2f}"
        )
    elif operation == "decrease":
        result = value * (1 - percentage / 100)
        saving = value * percentage / 100
        summary = (
            f"Percentage Decrease:\n"
            f"  Base value          : {value:,.2f}\n"
            f"  Decrease by         : {percentage}%\n"
            f"  Amount saved        : {saving:,.2f}\n"
            f"  Result after deduction: {result:,.2f}"
        )
    else:  # calculate
        result = (value / percentage) * 100
        summary = (
            f"Percentage Calculation:\n"
            f"  Part value          : {value:,.2f}\n"
            f"  Total (denominator) : {percentage:,.2f}\n"
            f"  Percentage          : {result:.2f}%"
        )

    return {
        "value": value,
        "percentage": percentage,
        "operation": operation,
        "result": round(result, 4),
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch table – used by the router
# ─────────────────────────────────────────────────────────────────────────────

TOOL_EXECUTORS = {
    "fee_calculator": execute_fee_calculator,
    "date_checker": execute_date_checker,
    "percentage_calculator": execute_percentage_calculator,
}


def dispatch(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the named tool with the given arguments.
    Raises ToolExecutionError if tool_name is unknown.
    """
    if tool_name not in TOOL_EXECUTORS:
        raise ToolExecutionError(
            f"Unknown tool '{tool_name}'. Available: {list(TOOL_EXECUTORS)}"
        )
    return TOOL_EXECUTORS[tool_name](**arguments)
