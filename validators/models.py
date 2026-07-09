"""
validators/models.py
--------------------
Pydantic v2 models for validating tool arguments BEFORE execution.

Every edge case from the assignment is handled here so the executor
only ever receives clean, safe data.

Edge cases covered
------------------
• Zero years (years=0)
• Negative fees
• Scholarship > 100 % or < 0 %
• Invalid date format / impossible dates
• Unknown operation for percentage_calculator
• Very large numbers (capped at 1 billion for fees)
• Prompt injection in string fields
• Missing required arguments (Pydantic handles automatically)
• Contradictory / unexpected extra fields (Pydantic ignores by default;
  we add model_config extra='forbid' so unexpected args raise an error)
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator, Field


# ─────────────────────────────────────────────────────────────────────────────
# Shared guard
# ─────────────────────────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore\s+previous",
    r"forget\s+instructions",
    r"you\s+are\s+now",
    r"act\s+as",
    r"jailbreak",
    r"system\s*prompt",
    r"<\s*script",
    r"DROP\s+TABLE",
    r"exec\s*\(",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def _check_injection(value: str, field_name: str) -> str:
    if _INJECTION_RE.search(value):
        raise ValueError(
            f"Field '{field_name}' contains a potentially unsafe pattern and was rejected."
        )
    return value


# ─────────────────────────────────────────────────────────────────────────────
# fee_calculator
# ─────────────────────────────────────────────────────────────────────────────

class FeeCalculatorInput(BaseModel):
    model_config = {"extra": "forbid"}   # unknown args → ValidationError

    annual_fee: float = Field(..., description="Annual tuition fee in INR")
    years: int = Field(..., description="Number of academic years (1–6)")
    scholarship_percentage: Optional[float] = Field(
        None, description="Scholarship discount 0–100 %"
    )
    hostel_fee: Optional[float] = Field(
        None, description="Annual hostel fee in INR"
    )

    @field_validator("annual_fee")
    @classmethod
    def validate_annual_fee(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(
                f"annual_fee must be positive (got {v}). "
                "Please provide the fee amount in INR."
            )
        if v > 1_000_000_000:
            raise ValueError(
                f"annual_fee={v} seems unrealistically large. Max allowed: ₹1,00,00,00,000."
            )
        return v

    @field_validator("years")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(
                f"years must be at least 1 (got {v}). "
                "A 0-year or negative programme does not make sense."
            )
        if v > 10:
            raise ValueError(
                f"years={v} is unrealistic. Max supported: 10 academic years."
            )
        return v

    @field_validator("scholarship_percentage")
    @classmethod
    def validate_scholarship(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError(
                f"scholarship_percentage cannot be negative (got {v}%). "
                "Use 0 for no scholarship."
            )
        if v > 100:
            raise ValueError(
                f"scholarship_percentage={v}% exceeds 100 %. "
                "A scholarship cannot exceed the full fee."
            )
        return v

    @field_validator("hostel_fee")
    @classmethod
    def validate_hostel_fee(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError(
                f"hostel_fee cannot be negative (got {v}). "
                "Use 0 or omit the field if there is no hostel charge."
            )
        if v > 500_000:
            raise ValueError(
                f"hostel_fee={v} seems unrealistically high. Max allowed: ₹5,00,000/year."
            )
        return v


# ─────────────────────────────────────────────────────────────────────────────
# date_checker
# ─────────────────────────────────────────────────────────────────────────────

class DateCheckerInput(BaseModel):
    model_config = {"extra": "forbid"}

    target_date: str = Field(..., description="Date in YYYY-MM-DD format")

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, v: str) -> str:
        # Injection check
        _check_injection(v, "target_date")

        # Format check
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError(
                f"target_date='{v}' is not in YYYY-MM-DD format. "
                "Example: '2025-07-31'."
            )

        # Parseable date check
        from datetime import datetime
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"target_date='{v}' is not a valid calendar date. "
                "Check day/month values (e.g. month 13 or day 32 are invalid)."
            )

        # Sanity range: 2000-01-01 to 2100-12-31
        year = int(v[:4])
        if year < 2000 or year > 2100:
            raise ValueError(
                f"target_date year {year} is out of supported range (2000–2100)."
            )

        return v


# ─────────────────────────────────────────────────────────────────────────────
# percentage_calculator
# ─────────────────────────────────────────────────────────────────────────────

class PercentageCalculatorInput(BaseModel):
    model_config = {"extra": "forbid"}

    value: float = Field(..., description="Base numeric value")
    percentage: float = Field(..., description="Percentage or denominator")
    operation: Literal["increase", "decrease", "calculate"] = Field(
        ..., description="One of: increase, decrease, calculate"
    )

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        if abs(v) > 1_000_000_000_000:
            raise ValueError(
                f"value={v} is too large. Max magnitude: 1 trillion."
            )
        return v

    @field_validator("percentage")
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        if abs(v) > 1_000_000_000_000:
            raise ValueError(
                f"percentage={v} is too large. Max magnitude: 1 trillion."
            )
        return v

    @model_validator(mode="after")
    def cross_validate(self) -> "PercentageCalculatorInput":
        op = self.operation
        pct = self.percentage

        if op in ("increase", "decrease"):
            if pct < 0:
                raise ValueError(
                    f"percentage={pct} is negative for operation='{op}'. "
                    "Use a positive percentage value."
                )
            if pct > 10_000:
                raise ValueError(
                    f"percentage={pct}% is unrealistically high for '{op}'."
                )

        if op == "calculate" and pct == 0:
            raise ValueError(
                "percentage (total/denominator) cannot be 0 for operation='calculate' "
                "— division by zero."
            )

        return self


# ─────────────────────────────────────────────────────────────────────────────
# Validation dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_VALIDATOR_MAP = {
    "fee_calculator": FeeCalculatorInput,
    "date_checker": DateCheckerInput,
    "percentage_calculator": PercentageCalculatorInput,
}


def validate_tool_args(tool_name: str, args: dict) -> dict:
    """
    Validate and coerce args for the named tool.

    Returns the cleaned args dict (with defaults applied).
    Raises ValueError with a clear message on any validation failure.
    """
    if tool_name not in _VALIDATOR_MAP:
        raise ValueError(f"No validator registered for tool '{tool_name}'.")

    model_cls = _VALIDATOR_MAP[tool_name]
    try:
        validated = model_cls(**args)
    except Exception as exc:
        # Re-raise as plain ValueError so the router can catch it uniformly
        raise ValueError(str(exc)) from exc

    return validated.model_dump(exclude_none=False)
