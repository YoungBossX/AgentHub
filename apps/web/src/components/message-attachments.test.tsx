import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { MessageAttachment } from "@/lib/api"
import { useMessageAttachments } from "./use-message-attachments"
import { MessageAttachments } from "./message-attachments"
import { MessageComposer } from "./message-composer"

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const item: MessageAttachment = { id: "file-1", sessionId: "a", messageId: null, filename: "需求.txt", kind: "text", mediaType: "text/plain", byteSize: 20, sha256: "abc", extractionStatus: "ready", textTruncated: false, imageWidth: null, imageHeight: null, imageSha256: null, createdAt: "2026-10-09T00:00:00Z" }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done }); return { promise, resolve } }
const response = (value = item) => new Response(JSON.stringify(value), { status: 201 })

describe("message attachments", () => {
  it("keeps late upload responses in the original Session and reuses its draft on return", async () => {
    const pending = deferred<Response>()
    const fetcher = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValueOnce(response({ ...item, id: "file-b", sessionId: "b" }))
    vi.stubGlobal("fetch", fetcher)
    const { result, rerender } = renderHook(({ sid }) => useMessageAttachments("http://localhost:8000", sid), { initialProps: { sid: "a" } })
    act(() => result.current.add([new File(["text"], "需求.txt")]))
    expect(result.current.blocked).toBe(true)
    rerender({ sid: "b" })
    expect(result.current.items).toEqual([])
    await act(async () => { pending.resolve(response()); await pending.promise })
    expect(result.current.ids).toEqual([])
    act(() => result.current.add([new File(["text"], "second.txt")]))
    await waitFor(() => expect(result.current.ids).toEqual(["file-b"]))
    rerender({ sid: "a" })
    expect(result.current.ids).toEqual(["file-1"])
    act(() => result.current.sent("a", ["file-1"]))
    expect(result.current.items).toEqual([])
    rerender({ sid: "b" })
    expect(result.current.ids).toEqual(["file-b"])
  })

  it("preserves errors until removal and handles server removal failure", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: "不支持文件格式" }), { status: 415 }))
      .mockResolvedValueOnce(response()).mockResolvedValueOnce(new Response(JSON.stringify({ detail: "已发送" }), { status: 409 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetcher)
    const { result } = renderHook(() => useMessageAttachments("", "a"))
    act(() => result.current.add([new File(["x"], "file.exe")]))
    await waitFor(() => expect(result.current.items[0].error).toBe("不支持文件格式"))
    expect(result.current.blocked).toBe(true)
    await act(async () => result.current.remove(result.current.items[0].key))
    act(() => result.current.add([new File(["x"], "file.txt")]))
    await waitFor(() => expect(result.current.ids).toEqual(["file-1"]))
    await act(async () => result.current.remove(result.current.items[0].key))
    expect(result.current.items[0].error).toBe("已发送")
    await act(async () => result.current.remove(result.current.items[0].key))
    expect(result.current.items).toEqual([])
  })

  it("bounds concurrent selections to four and aborts pending uploads on unmount", () => {
    const fetcher = vi.fn().mockReturnValue(new Promise(() => {})); vi.stubGlobal("fetch", fetcher)
    const { result, unmount } = renderHook(() => useMessageAttachments("", "a"))
    act(() => { result.current.add(Array.from({ length: 3 }, (_, index) => new File(["x"], `${index}.txt`))); result.current.add([new File(["x"], "four.txt"), new File(["x"], "five.txt")]) })
    expect(result.current.items).toHaveLength(4)
    expect(fetcher).toHaveBeenCalledTimes(4)
    unmount()
    expect(fetcher.mock.calls.every((call) => call[1].signal.aborted)).toBe(true)
  })

  it("renders explicit extraction limits, scoped raster preview and original download", () => {
    render(<MessageAttachments backendUrl="http://localhost:8000" items={[{ ...item, kind: "image", extractionStatus: "image" }, { ...item, id: "scan", filename: "scan.pdf", kind: "pdf", extractionStatus: "no_text" }]} />)
    expect(screen.getByRole("img").getAttribute("src")).toContain("/sessions/a/attachments/file-1/content?preview=true")
    expect(screen.getByRole("link", { name: "下载 需求.txt" }).getAttribute("href")).toBe("http://localhost:8000/sessions/a/attachments/file-1/content")
    expect(screen.getByText(/未提取到文字/)).toBeTruthy()
    expect(screen.getAllByText("文件来源")).toHaveLength(2)
  })

  it("prevents Enter/button send until validation succeeds and reports upload state", () => {
    const submit = vi.fn((event) => event.preventDefault())
    const props = { contextItems: [], draft: "参考附件", isPending: false, onClearContext: vi.fn(), onDraftChange: vi.fn(), onMoveContextItem: vi.fn(), onRemoveContextItem: vi.fn(), onSubmit: submit, onAttach: vi.fn() }
    const { rerender } = render(<MessageComposer {...props} attachmentsBlocked attachments={[{ key: "k", filename: "需求.txt", state: "uploading" }]} />)
    expect(screen.getByText("正在上传并校验…")).toBeTruthy()
    expect(screen.getByRole("button", { name: "发送" }).hasAttribute("disabled")).toBe(true)
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" })
    expect(submit).not.toHaveBeenCalled()
    rerender(<MessageComposer {...props} attachments={[{ key: "k", filename: "需求.txt", state: "ready", attachment: item }]} />)
    fireEvent.click(screen.getByRole("button", { name: "发送" }))
    expect(submit).toHaveBeenCalledTimes(1)
  })
})
