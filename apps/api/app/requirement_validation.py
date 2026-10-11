"""Server-owned contracts for existing structured demo intents only."""
import json

VERSION = "agenthub.requirement_validation.v1"
TARGETS = {"login_page", "demo_heading_text", "primary_action_button_text"}


def requirement_contract(plan):
    if (not isinstance(plan, dict) or plan.get("targetId") != "demo-frontend"
            or not isinstance(plan.get("target"), str) or plan["target"] not in TARGETS):
        return None
    result = {"schemaVersion": VERSION, "target": plan["target"]}
    if plan["target"] != "login_page":
        text = plan.get("targetText")
        if not isinstance(text, str) or not text.strip() or len(text) > 256:
            return None
        result["expectedText"] = text.strip()
    return result


def check_ids(contract):
    checks = {"login_page": ["fields", "empty", "invalid_email", "submit", "runtime"],
              "demo_heading_text": ["text", "runtime"],
              "primary_action_button_text": ["text", "click", "runtime"]}[contract["target"]]
    return [f"{viewport}.{check}" for viewport in ("desktop", "narrow") for check in checks]


def parse_browser_result(result, contract):
    """Process exit, exact check coverage and contract must agree; no log inference."""
    unavailable = {"schemaVersion": VERSION, "status": "unavailable", "contract": contract,
                   "checks": [], "reason": "Browser evidence is missing or incomplete."}
    try:
        data = json.loads(result["log"])
        if data["schemaVersion"] != VERSION or data["contract"] != contract:
            return unavailable
        if data["status"] == "unavailable":
            return {**unavailable, "reason": "Browser runtime could not start. Check the installed browser."}
        checks = data["checks"]
        if ([check["id"] for check in checks] != check_ids(contract)
                or any(check["status"] not in {"passed", "failed"} for check in checks)):
            return unavailable
        passed = all(check["status"] == "passed" for check in checks)
        if (data["status"] != ("passed" if passed else "failed")
                or result["status"] not in {"passed", "failed"}
                or (result["exitCode"] == 0) != passed):
            return unavailable
        return {"schemaVersion": VERSION, "status": data["status"], "contract": contract,
                "checks": [{"id": c["id"], "status": c["status"], "detail": str(c.get("detail", ""))[:600]} for c in checks],
                "browserVersion": str(data.get("browserVersion", "unknown"))[:80],
                "durationMs": result["durationMs"]}
    except (KeyError, ValueError, TypeError):
        return unavailable
