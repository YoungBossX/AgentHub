DEMO_PLANNER_RATIONALES = {
    "deterministic_login_v1": "Preserve the deterministic login-page demo fallback.",
    "dynamic_manager_v1": "Create a bounded frontend change task graph for the demo app.",
    "contract_first_v1": "Create a shared app contract before backend/frontend implementation tasks.",
}


def demo_plan_rationale(planner: str, intent: str) -> str:
    base = DEMO_PLANNER_RATIONALES.get(
        planner,
        "Preserve existing deterministic demo planning behavior.",
    )
    return f"{base} Intent: {intent}."
