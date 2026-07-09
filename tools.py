"""
Exercise 1 – Function Calling Tool Definitions
Defines the OpenAI/OpenRouter function-calling JSON schemas for the BVRIT RAG chatbot.

These schemas are DEFINITIONS ONLY. No execution logic lives here yet.
Exercise 2 will add routing logic and the actual Python functions that carry out each operation.

Each entry in BVRIT_TOOLS is a dict that matches the OpenAI function-calling spec:
  {
      "type": "function",
      "function": {
          "name": <str>,
          "description": <str>,  # tells the model WHEN to use the tool
          "parameters": <JSON Schema object>
      }
  }

LangChain's ChatOpenAI.bind_tools() accepts this exact format and injects it
into the "tools" field of every API request without changing any other behaviour.
"""

from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Tool 1 – fee_calculator
# ---------------------------------------------------------------------------
# Purpose: Handle any question that requires arithmetic over BVRIT fee data —
#   multi-year totals, hostel additions, or scholarship discounts.
# The model should call this when the user asks for a *calculated* result,
#   not just a fee lookup (e.g. "what is the fee?" is a RAG question, but
#   "how much will I pay over 4 years after a 25 % scholarship?" needs this tool).
# ---------------------------------------------------------------------------
FEE_CALCULATOR_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "fee_calculator",
        "description": (
            "Calculate BVRIT tuition fees across multiple academic years, "
            "apply scholarship or fee-concession discounts, and optionally add "
            "hostel charges to produce a combined total. "
            "Use this tool whenever the user asks for a computed fee result — "
            "for example: total fees over N years, amount payable after a scholarship "
            "discount, or combined tuition-plus-hostel cost. "
            "Do NOT use this tool for a simple fee lookup; use the RAG context for that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "annual_fee": {
                    "type": "number",
                    "description": (
                        "The annual tuition fee in INR as retrieved from the document "
                        "(e.g. 120000 for ₹1,20,000 per year)."
                    ),
                },
                "years": {
                    "type": "integer",
                    "description": (
                        "Number of academic years for which the total should be calculated "
                        "(typically 4 for B.Tech, 2 for M.Tech)."
                    ),
                },
                "scholarship_percentage": {
                    "type": "number",
                    "description": (
                        "Optional. Scholarship or fee-concession percentage to deduct "
                        "from the annual tuition fee before multiplying by years "
                        "(e.g. 25 means a 25 % discount). Omit if no scholarship applies."
                    ),
                },
                "hostel_fee": {
                    "type": "number",
                    "description": (
                        "Optional. Annual hostel fee in INR to add to the tuition fee "
                        "before calculating the multi-year total "
                        "(e.g. 75000 for ₹75,000 per year). Omit if not requested."
                    ),
                },
            },
            "required": ["annual_fee", "years"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool 2 – date_checker
# ---------------------------------------------------------------------------
# Purpose: Tell the user whether an admission deadline, exam date, or event date
#   found in the retrieved document is upcoming, already past, or how many
#   days away it is — relative to today's date.
# The model should call this when the user asks about the status of a date
#   (e.g. "has the admission deadline passed?", "how many days left for EAPCET?").
# The model must extract the date string from the RAG context first, then
#   pass it here as YYYY-MM-DD.
# ---------------------------------------------------------------------------
DATE_CHECKER_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "date_checker",
        "description": (
            "Compare an admission deadline, entrance exam date, or college event date "
            "extracted from the BVRIT knowledge base against today's date to determine "
            "whether the event is upcoming, already past, or exactly how many days remain. "
            "Use this tool when the user asks time-sensitive questions like "
            "'has the application deadline passed?', 'how many days left to apply?', "
            "or 'is the EAPCET counselling still open?'. "
            "Always extract the specific date from the retrieved context before calling this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": (
                        "The date to check, in ISO 8601 format: YYYY-MM-DD "
                        "(e.g. '2025-07-31' for 31 July 2025). "
                        "Extract this value from the document context before calling the tool."
                    ),
                },
            },
            "required": ["target_date"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool 3 – percentage_calculator
# ---------------------------------------------------------------------------
# Purpose: Perform any percentage-based arithmetic related to BVRIT data —
#   scholarship eligibility thresholds, placement percentages, admission cutoffs,
#   or score-to-percentage conversions.
# The model should call this when the user asks for a *computed* percentage result,
#   not just a quoted statistic (e.g. "what is the placement percentage?" is a RAG
#   question, but "if 180 out of 240 students are placed, what is the percentage?" needs
#   this tool, as does "what marks do I need to get a 75 % scholarship?").
# ---------------------------------------------------------------------------
PERCENTAGE_CALCULATOR_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "percentage_calculator",
        "description": (
            "Perform percentage-based arithmetic on BVRIT-related figures such as "
            "scholarship eligibility percentages, placement rates, admission cutoff scores, "
            "or any other percentage calculation related to the college. "
            "Supports three operations: "
            "'increase' — add a percentage to a base value (e.g. a 10 % fee hike); "
            "'decrease' — subtract a percentage from a base value "
            "    (e.g. how much is saved with a 30 % scholarship); "
            "'calculate' — express one number as a percentage of another "
            "    (e.g. what percentage of applicants were admitted). "
            "Use this tool only when the user asks for a *calculated* result involving "
            "percentages, not for a simple lookup of a percentage figure already stated "
            "in the document."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": (
                        "The base numeric value to operate on "
                        "(e.g. 120000 for ₹1,20,000 annual fee, or 240 for total students)."
                    ),
                },
                "percentage": {
                    "type": "number",
                    "description": (
                        "The percentage figure to apply "
                        "(e.g. 25 for 25 %, or 95 for 95 % placement rate). "
                        "Always pass the number without the % symbol."
                    ),
                },
                "operation": {
                    "type": "string",
                    "enum": ["increase", "decrease", "calculate"],
                    "description": (
                        "'increase': result = value × (1 + percentage/100)  "
                        "    — use for fee hikes or score boosts; "
                        "'decrease': result = value × (1 − percentage/100)  "
                        "    — use for scholarship discounts or reductions; "
                        "'calculate': result = (value / percentage) × 100  "
                        "    — use to express value as a percentage of a total "
                        "    where 'percentage' is actually the denominator/total."
                    ),
                },
            },
            "required": ["value", "percentage", "operation"],
        },
    },
}


# ---------------------------------------------------------------------------
# Master list – imported by generator.py
# ---------------------------------------------------------------------------
BVRIT_TOOLS: List[Dict[str, Any]] = [
    FEE_CALCULATOR_TOOL,
    DATE_CHECKER_TOOL,
    PERCENTAGE_CALCULATOR_TOOL,
]
