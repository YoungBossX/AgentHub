const checklistItems = [
  "Create a focused login page in the empty slot",
  "Keep the change small enough for a readable diff",
  "Refresh the preview after the follow-up button copy change",
]

export default function App() {
  return (
    <main className="demo-shell">
      <section className="workspace-panel" aria-labelledby="demo-heading">
        <div className="workspace-copy">
          <p className="eyebrow">AgentHub demo workspace</p>
          <h1 id="demo-heading">Launchpad for a visible coding-agent change</h1>
          <p className="lede">
            This baseline Vite React app gives future agents a stable place to
            add a login page and then adjust button copy without changing the
            rest of the product scaffold.
          </p>

          <ul className="demo-checklist" aria-label="Demo targets">
            {checklistItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <aside className="mutation-card" aria-label="Deterministic mutation targets">
          <div className="status-row">
            <span className="status-dot" aria-hidden="true" />
            Ready for adapter changes
          </div>

          <div
            className="login-slot"
            data-agenthub-target="login-page-slot"
            aria-label="Login page insertion target"
          >
            <p className="slot-label">Login page target</p>
            <p className="slot-copy">
              Build the login page here during the first demo request.
            </p>
          </div>

          <button
            className="primary-action"
            data-agenthub-target="primary-action-button"
            type="button"
          >
            Continue
          </button>
        </aside>
      </section>
    </main>
  )
}
