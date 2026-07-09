"""
function_calling_eval.py
------------------------
Exercise 5 – Automatic evaluation of the complete tool-enabled chatbot.

Runs 10 predefined test cases and produces a table with columns:
  Query | Expected Routing | Actual Routing | Tool Used | Arguments |
  Retrieved Chunks | Final Response | Latency (ms) | Pass/Fail

Run directly:
    python function_calling_eval.py

Results are printed to stdout as a formatted table and saved to
function_calling_results.json.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from retriever import retrieve_chunks
from routing import Router, ROUTE_CONVERSATION, ROUTE_RAG, ROUTE_TOOL

# ─────────────────────────────────────────────────────────────────────────────
# 10 Assignment test cases
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES: List[Dict[str, Any]] = [
    # ── CONVERSATION ─────────────────────────────────────────────────────────
    {
        "id": "TC01",
        "query": "Hello",
        "expected_route": ROUTE_CONVERSATION,
        "expected_tool": None,
        "description": "Greeting — no RAG, no tool",
    },
    # ── RAG ──────────────────────────────────────────────────────────────────
    {
        "id": "TC02",
        "query": "What departments does BVRIT have?",
        "expected_route": ROUTE_RAG,
        "expected_tool": None,
        "description": "Pure document lookup",
    },
    {
        "id": "TC03",
        "query": "What is the hostel fee at BVRIT?",
        "expected_route": ROUTE_RAG,
        "expected_tool": None,
        "description": "Fee lookup (no calculation needed)",
    },
    {
        "id": "TC04",
        "query": "What are the top recruiters at BVRIT?",
        "expected_route": ROUTE_RAG,
        "expected_tool": None,
        "description": "Placement lookup",
    },
    # ── TOOL: fee_calculator ─────────────────────────────────────────────────
    {
        "id": "TC05",
        "query": "What is the total tuition for four years if the annual fee is 120000?",
        "expected_route": ROUTE_TOOL,
        "expected_tool": "fee_calculator",
        "description": "Multi-year fee calculation",
    },
    {
        "id": "TC06",
        "query": "If I get 15% scholarship and the annual fee is 120000, what is my fee for 4 years?",
        "expected_route": ROUTE_TOOL,
        "expected_tool": "fee_calculator",
        "description": "Fee with scholarship discount",
    },
    {
        "id": "TC07",
        "query": "Annual tuition is 120000 and hostel is 75000. What is my total cost for 4 years?",
        "expected_route": ROUTE_TOOL,
        "expected_tool": "fee_calculator",
        "description": "Tuition + hostel combination",
    },
    # ── TOOL: date_checker ───────────────────────────────────────────────────
    {
        "id": "TC08",
        "query": "Has the admission deadline of 2025-07-31 passed?",
        "expected_route": ROUTE_TOOL,
        "expected_tool": "date_checker",
        "description": "Admission deadline status check",
    },
    {
        "id": "TC09",
        "query": "How many days are left until the exam on 2027-01-15?",
        "expected_route": ROUTE_TOOL,
        "expected_tool": "date_checker",
        "description": "Days remaining calculation",
    },
    # ── TOOL: percentage_calculator ──────────────────────────────────────────
    {
        "id": "TC10",
        "query": "If 180 out of 240 students got placed, what is the placement percentage?",
        "expected_route": ROUTE_TOOL,
        "expected_tool": "percentage_calculator",
        "description": "Placement percentage calculation",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation() -> List[Dict[str, Any]]:
    router = Router()
    results = []

    print("\n" + "=" * 100)
    print("BVRIT Function Calling Evaluation — Exercise 5")
    print("=" * 100)

    for tc in TEST_CASES:
        print(f"\n[{tc['id']}] {tc['description']}")
        print(f"  Query: {tc['query']}")

        # Retrieve chunks
        t0 = time.time()
        try:
            chunks = retrieve_chunks(tc["query"], top_k=5)
        except Exception as e:
            chunks = []
            print(f"  Retrieval error: {e}")

        # Route
        try:
            result = router.route(tc["query"], chunks)
        except Exception as e:
            print(f"  Router error: {e}")
            results.append({
                "id": tc["id"],
                "query": tc["query"],
                "expected_route": tc["expected_route"],
                "actual_route": "ERROR",
                "expected_tool": tc["expected_tool"],
                "actual_tool": None,
                "tool_args": None,
                "chunks_retrieved": len(chunks),
                "final_response": f"ERROR: {e}",
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "pass_fail": "FAIL",
            })
            continue

        # Evaluate
        route_ok = result.route == tc["expected_route"]
        tool_ok = result.tool_name == tc["expected_tool"]
        passed = route_ok and tool_ok

        row = {
            "id": tc["id"],
            "query": tc["query"],
            "expected_route": tc["expected_route"],
            "actual_route": result.route,
            "expected_tool": tc["expected_tool"],
            "actual_tool": result.tool_name,
            "tool_args": result.tool_args,
            "chunks_retrieved": result.chunks_used,
            "final_response": result.answer[:200] + ("..." if len(result.answer) > 200 else ""),
            "latency_ms": result.latency_ms,
            "pass_fail": "PASS" if passed else "FAIL",
        }
        results.append(row)

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  Expected: {tc['expected_route']} / {tc['expected_tool']}")
        print(f"  Actual  : {result.route} / {result.tool_name}")
        print(f"  Latency : {result.latency_ms:.0f} ms")
        print(f"  Result  : {status}")

    return results


def print_table(results: List[Dict[str, Any]]) -> None:
    """Print a formatted summary table."""
    passed = sum(1 for r in results if r["pass_fail"] == "PASS")
    total = len(results)

    print("\n" + "=" * 100)
    print(f"EVALUATION SUMMARY  —  {passed}/{total} passed  ({passed/total*100:.0f}%)")
    print("=" * 100)

    header = (
        f"{'ID':<5} {'Route Expected':<14} {'Route Actual':<14} "
        f"{'Tool Expected':<22} {'Tool Actual':<22} "
        f"{'Chunks':>6} {'Latency':>8} {'P/F':>5}"
    )
    print(header)
    print("-" * 100)

    for r in results:
        print(
            f"{r['id']:<5} "
            f"{r['expected_route']:<14} "
            f"{r['actual_route']:<14} "
            f"{str(r['expected_tool']):<22} "
            f"{str(r['actual_tool']):<22} "
            f"{r['chunks_retrieved']:>6} "
            f"{r['latency_ms']:>7.0f}ms "
            f"{'✅' if r['pass_fail']=='PASS' else '❌':>5}"
        )

    print("=" * 100)


def save_results(results: List[Dict[str, Any]], path: str = "function_calling_results.json") -> None:
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    results = run_evaluation()
    print_table(results)
    save_results(results)
