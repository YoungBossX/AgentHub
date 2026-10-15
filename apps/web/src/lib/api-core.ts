export type Fetcher = typeof fetch

// This public marker forces browser preflight; the API also checks Host/Origin.
export function controlledRequest(fetcher: Fetcher, input: RequestInfo | URL, init?: RequestInit) {
  const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase()
  if (["GET", "HEAD", "OPTIONS"].includes(method)) return fetcher(input, init)
  const headers = new Headers(input instanceof Request ? input.headers : undefined)
  new Headers(init?.headers).forEach((value, name) => headers.set(name, value))
  headers.set("X-AgentHub-Control", "local-workspace")
  return fetcher(input, { ...init, headers: Object.fromEntries(headers.entries()) })
}

export class ApiRequestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ApiRequestError"
  }
}

export function apiUrl(backendUrl: string, path: string) {
  return `${backendUrl.replace(/\/$/, "")}${path}`
}

export async function responseErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail
    }
  } catch {
    return fallback
  }
  return fallback
}
