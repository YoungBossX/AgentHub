import { describe, expect, it, vi } from "vitest"
import { controlledRequest } from "./api-core"

describe("local API request boundary", () => {
  it.each(["POST", "PUT", "PATCH", "DELETE"])("marks %s including bodyless requests", async (method) => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response())
    await controlledRequest(fetcher, "http://127.0.0.1:8000/control", { method, headers: { "Content-Type": "application/json" } })
    const init = fetcher.mock.calls[0][1] as RequestInit
    expect(new Headers(init.headers).get("X-AgentHub-Control")).toBe("local-workspace")
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json")
  })

  it("preserves upload bytes, cancellation and GET options", async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response())
    const body = new Blob(["upload"]), signal = new AbortController().signal
    await controlledRequest(fetcher, "http://127.0.0.1:8000/attachments", { method: "POST", body, signal })
    expect(fetcher.mock.calls[0][1]).toMatchObject({ body, signal })
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has("Content-Type")).toBe(false)
    const options = { cache: "no-store" as const }
    await controlledRequest(fetcher, "http://127.0.0.1:8000/health", options)
    expect(fetcher.mock.calls[1][1]).toBe(options)
  })
})
