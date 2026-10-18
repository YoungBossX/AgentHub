"""Offline rule evaluation. Does not call a provider or create product records."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from app.planning_intents import recognize_intent


CORPUS = Path(__file__).resolve().parents[1] / "evals" / "intent_cases.json"


def evaluate_intents(corpus_path: Path = CORPUS) -> dict:
    raw = corpus_path.read_bytes()
    corpus = json.loads(raw)
    cases = corpus["cases"]
    if corpus["schemaVersion"] != 1 or not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Invalid or duplicate intent evaluation cases.")
    mismatches = []
    categories: dict[str, Counter] = {}
    totals = Counter()
    for case in cases:
        result = recognize_intent(case["content"], roles=tuple(case.get("roles", []))).to_payload()
        checks = {key: result[key] == value for key, value in case["expected"].items()}
        counts = categories.setdefault(case["category"], Counter())
        counts["total"] += 1
        counts["passed"] += all(checks.values())
        totals["passed"] += all(checks.values())
        for key, passed in checks.items():
            totals[key + "Checked"] += 1
            totals[key + "Correct"] += passed
        if case.get("mustNotRuleExecute", False):
            totals["nonExecutableCases"] += 1
            totals["unsafeRuleExecutionErrors"] += result["route"] == "continue" and result["requestType"] == "change"
        if not all(checks.values()):
            mismatches.append({"id": case["id"], "expected": case["expected"], "actual": result})
    return {"schemaVersion": 1, "evaluationKind": "offline_rule_only",
            "corpusSha256": hashlib.sha256(raw).hexdigest(), "total": len(cases),
            **dict(totals), "categories": {key: dict(value) for key, value in categories.items()},
            "mismatches": mismatches,
            "limits": "Authored regression corpus; no real LLM accuracy, latency, generalization or task execution claim."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_intents()
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        # New report only: never overwrite a caller's existing artifact.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    print(serialized)
    raise SystemExit(0 if not report["mismatches"] and not report.get("unsafeRuleExecutionErrors", 0) else 1)


if __name__ == "__main__":
    main()
