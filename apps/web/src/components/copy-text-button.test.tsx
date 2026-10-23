import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { CopyTextButton } from "./copy-text-button"

beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } }) })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
const copy = async () => { await act(async () => { fireEvent.click(screen.getByRole("button")) }) }

it("restores the copy action 2500ms after success and restarts the lifetime", async () => {
  render(<CopyTextButton text="中文证据" label="复制消息" />)
  await copy()
  act(() => vi.advanceTimersByTime(2400))
  expect(screen.getByRole("button").textContent).toBe("已复制")
  await copy()
  act(() => vi.advanceTimersByTime(2499))
  expect(screen.getByRole("button").textContent).toBe("已复制")
  act(() => vi.advanceTimersByTime(1))
  expect(screen.getByRole("button").textContent).toBe("复制消息")
  expect(screen.getByRole("status").textContent).toBe("")
})

it("does not let an expired old copy clear a newer pending or successful copy", async () => {
  let finish: () => void = () => {}
  const write = navigator.clipboard.writeText as ReturnType<typeof vi.fn>
  render(<CopyTextButton text="内容" label="复制" />)
  await copy()
  act(() => vi.advanceTimersByTime(2000))
  write.mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve }))
  await copy()
  act(() => vi.advanceTimersByTime(1000))
  expect(screen.getByRole("button").textContent).toBe("复制中…")
  await act(async () => finish())
  act(() => vi.advanceTimersByTime(2499))
  expect(screen.getByRole("button").textContent).toBe("已复制")
})

it("ignores clipboard completion after content changes and clears unmounted timers", async () => {
  let finish: () => void = () => {}
  vi.mocked(navigator.clipboard.writeText).mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve }))
  const view = render(<CopyTextButton text="旧内容" label="复制" />)
  await copy()
  view.rerender(<CopyTextButton text="新内容" label="复制" />)
  await act(async () => finish())
  expect(screen.getByRole("status").textContent).toBe("")
  await copy()
  view.unmount()
  expect(vi.getTimerCount()).toBe(0)
})

it("does not resurrect old success when content changes away and back", async () => {
  const view = render(<CopyTextButton text="A" label="复制" />)
  await copy()
  view.rerender(<CopyTextButton text="B" label="复制" />)
  view.rerender(<CopyTextButton text="A" label="复制" />)
  expect(screen.getByRole("button").textContent).toBe("复制")
  expect(screen.getByRole("status").textContent).toBe("")
})

it("does not resurrect an invalidated pending operation after returning to old content", async () => {
  let finish: () => void = () => {}
  vi.mocked(navigator.clipboard.writeText).mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve }))
  const view = render(<CopyTextButton text="A" label="复制" />)
  await copy()
  view.rerender(<CopyTextButton text="B" label="复制" />)
  view.rerender(<CopyTextButton text="A" label="复制" />)
  await act(async () => finish())
  expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(false)
  expect(screen.getByRole("button").textContent).toBe("复制")
})
