# Final managed-input context accounting

Individual memory, Skill, pin and attachment limits do not bound the final rendered
request, including escaping, repeated context, provider schemas and native review
contracts. Add a shared final-request gate and non-content accounting receipts.

This focused change covers coding/review launch and the four existing real Planner
transports. Preserve frozen snapshots, selected Skills and mandatory rules. Fail
closed on total overflow, with explicit source-selection/omission evidence; do not
silently truncate required input or fall back to a weaker prompt. No new provider,
dependency or model-specific tokenizer. State character/byte units and exclude
CLI-managed hidden context and response/tool-loop growth from the guarantee.
