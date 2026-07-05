export type Fetcher = typeof fetch

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
