import type { ChatMessage } from "./api"
import { ApiRequestError, apiUrl, controlledRequest, responseErrorMessage, type Fetcher } from "./api-core"

export const HISTORY_PAGE_SIZE = 80
export const HISTORY_WINDOW_SIZE = 200
export type MessagePage = { messages: ChatMessage[]; pinnedMessages: ChatMessage[]; pinnedTotal: number; total: number;
  hasOlder: boolean; hasNewer: boolean; olderCursor: string | null; newerCursor: string | null; latestMessageId: string | null; previewCharacterLimit: number }
export type HistoryQuery = { limit?: number; before?: string; after?: string; around?: string }
export type MessageContentPage = { messageId: string; text: string; offset: number; totalCharacters: number; nextOffset: number | null; previousOffset: number | null; unit: string }

export async function listMessagePage(backendUrl: string, sessionId: string, query: HistoryQuery = {}, fetcher: Fetcher = fetch): Promise<MessagePage> {
  const params = new URLSearchParams({ limit: String(query.limit ?? HISTORY_PAGE_SIZE) })
  for (const key of ["before", "after", "around"] as const) if (query[key]) params.set(key, query[key])
  const response = await controlledRequest(fetcher, apiUrl(backendUrl, `/sessions/${encodeURIComponent(sessionId)}/messages/page?${params}`), { cache: "no-store" })
  if (!response.ok) throw new ApiRequestError(await responseErrorMessage(response, "无法读取会话历史"))
  const page = await response.json() as MessagePage
  if (!Array.isArray(page.messages) || !Array.isArray(page.pinnedMessages)
    || [...page.messages, ...page.pinnedMessages].some(row => !row || row.sessionId !== sessionId || typeof row.id !== "string")) throw new ApiRequestError("消息历史格式或会话归属不匹配，请确认前后端使用同一版本。")
  return page
}

export async function getHistoryMessage(backendUrl: string, sessionId: string, messageId: string): Promise<ChatMessage> {
  const response = await controlledRequest(fetch, apiUrl(backendUrl, `/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}`), { cache: "no-store" })
  if (!response.ok) throw new Error(await responseErrorMessage(response, "无法定位原消息"))
  return response.json()
}

export async function getMessageContent(backendUrl: string, sessionId: string, messageId: string, offset = 0): Promise<MessageContentPage> {
  const response = await controlledRequest(fetch, apiUrl(backendUrl, `/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/content?offset=${offset}&limit=12000`), { cache: "no-store" })
  if (!response.ok) throw new Error(await responseErrorMessage(response, "无法读取消息正文"))
  return response.json()
}
