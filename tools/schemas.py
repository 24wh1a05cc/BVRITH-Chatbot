"""
tools/schemas.py
----------------
OpenAI / OpenRouter function-calling JSON schemas for the BVRIT chatbot.

WHY THESE DESCRIPTIONS ARE SPECIFIC
-------------------------------------
Generic descriptions like "do math" cause the model to call tools on questions
that should be answered by RAG (e.g. "what is the fee?"). Each description:
  • States the EXACT computational action the tool performs.
  • Lists example trigger phrases.
  • Explicitly says when NOT to call it (RAG handles simple lookups).

This keeps the RAG pipeline intact for factual lookups and routes only
genuinely computational queries to tools.
"""

from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 – fee_calculator
# Description rationale:
#   We list every sub-case (multi-year total, scholarship discount, hostel combo)
#   so the model knows this tool is for arithmetic, not lookups. The explicit
#   "Do NOT use for simple fee lookup" prevents over-triggering on RAG questions.
# ─────────────────────────────────────────────────────────────────────────────
FEE_CALCULATOR_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "fee_calculator",
        "description": (
            "Calculate BVRIT tuition fee totals across multiple academic years, "
            "apply scholarship or fee-concession percentage discounts to the annual fee, "
            "and optionally add annual hostel charges to produce a combined payable amount. "
            "Trigger this tool when the user asks for a COMPUTED fee result such as: "
            "'total fees over 4 years', 'how much after 25% scholarship', "
            "'tuition plus hostel for 2 years', or 'how much will I save with concession'. "
            "Do NOT trigger for a plain fee lookup like 'what is the CSE fee?' — "
            "that is answered directly from the retrieved document context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "annual_fee": {
                    "type": "number",
                    "description": (
                        "Annual tuition fee in INR extracted from the retrieved document "
                        "(e.g. 120000 for ₹1,20,000/year). Must be a positive number."
                    ),
                },
                "years": {
                    "type": "integer",
                    "description": (
                        "Number of academic years to calculate for "
                        "(4 for B.Tech, 2 for M.Tech). Must be a positive integer."
                    ),
                },
                "scholarship_percentage": {
                    "type": "number",
                    "description": (
                        "Optional scholarship or fee-concession percentage (0–100) to deduct "
                        "from the annual_fee before multiplying by years. "
                        "E.g. 25 means 25% discount. Omit if no scholarship applies."
                    ),
                },
                "hostel_fee": {
                    "type": "number",
                    "description": (
                        "Optional annual hostel fee in INR to add per year "
                        "before computing the multi-year total. Omit if not asked."
                    ),
                },
            },
            "required": ["annual_fee", "years"],
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 – date_checker
# Description rationale:
#   The model must understand it needs a date STRING (YYYY-MM-DD) from the
#   retrieved context. Listing concrete trigger phrases ("has the deadline passed",
#   "how many days left") prevents it from calling this on general date questions
#   like "when was BVRIT founded?" which are pure RAG lookups.
# ─────────────────────────────────────────────────────────────────────────────
DATE_CHECKER_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "date_checker",
        "description": (
            "Compare a specific admission deadline, entrance exam date, fee payment due date, "
            "or academic event date extracted from the BVRIT knowledge base against today's "
            "date to determine: is the event upcoming, already past, or happening today? "
            "Also returns exact days remaining or days elapsed. "
            "Trigger when the user asks time-sensitive questions such as: "
            "'has the application deadline passed?', 'how many days left to apply?', "
            "'is EAPCET counselling still open?', 'when does hostel fee payment close?'. "
            "IMPORTANT: First extract the exact date from the retrieved context, "
            "then pass it as YYYY-MM-DD. Do NOT call for general date questions "
            "that are answered by the document alone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": (
                        "The date to compare against today, in ISO 8601 format YYYY-MM-DD "
                        "(e.g. '2025-07-31'). Extract from the retrieved document context."
                    ),
                },
            },
            "required": ["target_date"],
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 – percentage_calculator
# Description rationale:
#   Three named operations (increase / decrease / calculate) are listed explicitly
#   so the model always picks the right one. The "Do NOT use for simple lookup"
#   clause stops it from calling the tool when the document already states the %.
# ─────────────────────────────────────────────────────────────────────────────
PERCENTAGE_CALCULATOR_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "percentage_calculator",
        "description": (
            "Perform percentage arithmetic on BVRIT-related numeric data: "
            "scholarship eligibility thresholds, placement rates, admission cutoff scores, "
            "fee increase/decrease calculations, or converting raw counts to percentages. "
            "Three operations are supported — "
            "'increase': result = value × (1 + pct/100), use for fee hikes or score boosts; "
            "'decrease': result = value × (1 − pct/100), use for scholarship savings; "
            "'calculate': result = (value / total) × 100, use to express a count as a %. "
            "Trigger when the user needs a COMPUTED percentage result such as: "
            "'what % of students were placed?', 'how much do I save with 30% scholarship?', "
            "'what is 15% of 120000?'. "
            "Do NOT trigger for simple percentage lookups already stated in the document."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": (
                        "The base numeric value (e.g. 120000 for annual fee, "
                        "180 for placed students, 95 for a score)."
                    ),
                },
                "percentage": {
                    "type": "number",
                    "description": (
                        "For 'increase'/'decrease': the percentage to apply (e.g. 25 for 25%). "
                        "For 'calculate': the total/denominator (e.g. 240 for total students). "
                        "Always pass as a plain number, no % symbol."
                    ),
                },
                "operation": {
                    "type": "string",
                    "enum": ["increase", "decrease", "calculate"],
                    "description": (
                        "Which calculation to perform: "
                        "'increase' — add percentage to value; "
                        "'decrease' — subtract percentage from value; "
                        "'calculate' — express value as % of percentage (the total)."
                    ),
                },
            },
            "required": ["value", "percentage", "operation"],
        },
    },
}

# Master list consumed by routing engine and LLM binding
BVRIT_TOOLS: List[Dict[str, Any]] = [
    FEE_CALCULATOR_SCHEMA,
    DATE_CHECKER_SCHEMA,
    PERCENTAGE_CALCULATOR_SCHEMA,
]

# Name → schema lookup
TOOL_SCHEMA_MAP: Dict[str, Dict[str, Any]] = {
    t["function"]["name"]: t for t in BVRIT_TOOLS
}
