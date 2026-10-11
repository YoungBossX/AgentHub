# Requirement-level demo validation

Add browser interaction acceptance for three existing structured demo intents:
login form, heading text and primary button text. Keep build validation, immutable
source receipts and completion fencing. Repair the scripted login form's missing
validation/submit interaction. Do not add authentication or automatic repair.

Use pinned Playwright as a developer dependency with an already installed browser.
Runtime never installs dependencies or browsers. Unsupported requests and missing
browser runtimes are explicit, not fabricated passes.
