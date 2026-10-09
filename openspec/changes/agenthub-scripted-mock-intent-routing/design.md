# Design

Use a fixed mapping from planContext.target to the three existing demo mutations:
login_page, primary_action_button_text and demo_heading_text. The structured target
is authoritative even when prose or the legacy script hint contains other action
keywords. Structured copy mutations require a nonempty string targetText; login
ignores unrelated copy text. Unknown, null or malformed explicit targets fail via
the existing SCRIPTED_MOCK_MUTATION_FAILED event before writing the source file.

Only requests with no target key use the existing prose/script compatibility
selection and copy-text extraction. Do not infer filesystem permissions from
these mutation selectors or add arbitrary file paths/scripts. Keep all existing
network/path checks and the execution engine's scope and completion gates.

Regression tests use real temporary Vite source/Git files. Strengthen the existing
HTTP login-plan execution test to require email/password form creation and an
unchanged page heading. Then create an explicit dependent frontend follow-up Task
in that Session, preserving the real request builder/engine path and checking the
button-only mutation. This verifies adapter/task behavior, not the ordinary second
HTTP message's QA dependency or a healthy browser Preview. Those remain a distinct
end-to-end acceptance boundary.
