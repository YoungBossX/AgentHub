## Context

P16 introduced Agent Runtime Configuration and P17b expanded Planner runtime settings to include API provider presets such as DeepSeek and MiMo. The current UI renders this detailed configuration inside the chat workspace sidebar through `runtimeSettingsSlot`, which competes with the session list and makes the IM-style workspace feel like a settings console.

The current provider status strings are also backend/internal values such as `unchecked`, `missing_key`, `not_required`, and `unavailable`. They are useful for code paths and tests, but poor user-facing copy. P17c is a UI and information-architecture hardening change: it should preserve runtime configuration behavior while moving detailed configuration to a dedicated settings surface.

## Goals / Non-Goals

**Goals:**
- Keep the chat page visually simple and session-focused.
- Replace the inline runtime settings panel with a compact settings entry point.
- Provide a dedicated runtime settings page for Planner, Frontend, Backend, and Review configuration.
- Support Save and Cancel actions with draft state that does not immediately mutate persisted runtime config.
- Display provider/profile/config status with clear user-facing labels and explanations.
- Preserve P16/P17/P17b runtime config APIs and behavior.

**Non-Goals:**
- Do not add new provider protocols, provider presets, or coding adapters.
- Do not add raw API key entry or secret storage.
- Do not add a full provider marketplace or arbitrary custom shell agents.
- Do not change Planner/Coding Agent runtime separation.
- Do not change scheduler, Target Registry, PlanValidator, or adapter execution semantics.

## Decisions

### Dedicated Settings Route

Create a dedicated runtime settings page, preferably under an application route such as `/settings/runtime` or a workspace-scoped equivalent if the existing router structure makes that cleaner.

Rationale: a route gives configuration enough room for grouped controls, validation messages, provider explanations, and future settings tabs without cluttering the chat sidebar. A modal would still compete with the chat surface and become cramped as configuration grows.

Alternative considered: keep settings inline but collapsed. This would reduce clutter only partially and would still bind a growing configuration surface to the session navigation component.

### Chat Page Keeps a Compact Entry Point

The chat workspace should keep only a settings button or compact link, placed in a stable chrome area such as the sidebar header, workspace header, or top-right toolbar.

Rationale: users need quick access to configuration, but the default mental model should remain "choose a session and chat with agents."

### Draft State With Save And Cancel

The settings page should load persisted runtime config into local draft state. Save persists the draft through existing runtime config APIs. Cancel discards draft changes and returns to the previous page or reloads the persisted values.

Rationale: provider/runtime settings are meaningful system behavior. Accidental changes should not leak into live agent execution before the user explicitly saves.

### User-facing Status Mapping

Keep internal status values stable for APIs and tests, but map them in the UI to labels and helper text:

- `unchecked`: "未检测" / "AgentHub 尚未验证本机工具或认证状态"
- `configured`: "已配置" / "已找到所需配置"
- `missing_key`: "缺少密钥环境变量" / "请在后端进程环境中设置对应 env"
- `not_required`: "无需认证"
- `unavailable`: "不可用"
- validation `required` errors: "必填配置缺失" with the specific field.

Rationale: this preserves implementation clarity while avoiding raw internal enum leakage in the product UI.

### Preserve Runtime Config API

P17c should consume existing APIs unless a tiny read-only metadata addition is needed. The backend should not be redesigned for this UI move.

Rationale: the problem is primarily layout and presentation. Runtime behavior is already covered by P16/P17b.

## Risks / Trade-offs

- Settings route may need to reuse workspace context and backend URL wiring currently owned by `workspace-shell` -> Mitigation: extract small hooks or pass route-level props without changing API contracts.
- Existing tests may assume settings render inside the workspace shell -> Mitigation: update tests to assert a settings entry point in chat and detailed controls on the settings page.
- Status translation may obscure exact debug values -> Mitigation: display concise user labels with optional detail text or tooltip that includes the stable internal status when useful.
- Cancel behavior can be ambiguous if there are unsaved changes -> Mitigation: define Cancel as "discard draft and restore persisted config"; navigation confirmation can be deferred unless already available.
