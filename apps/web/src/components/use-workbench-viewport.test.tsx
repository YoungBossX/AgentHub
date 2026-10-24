import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useWorkbenchViewport } from "./use-workbench-viewport"

function Fixture({ sessionId = "first" }: { sessionId?: string }) {
  const ref = useWorkbenchViewport()
  return <section key={sessionId} ref={ref} data-testid="shell" />
}

class Viewport extends EventTarget {
  height = 460
  offsetTop = 0
  scale = 1
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe("小屏工作台可见区域", () => {
  function setup(width = 390) {
    const viewport = new Viewport()
    vi.stubGlobal("innerWidth", width)
    vi.stubGlobal("visualViewport", viewport)
    const view = render(<Fixture />)
    const shell = screen.getByTestId("shell")
    return { viewport, view, shell }
  }

  it("跟随键盘缩小、平移与恢复的可见高度", () => {
    const { viewport, shell } = setup()
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("460px")
    viewport.height = 320; viewport.offsetTop = 40
    viewport.dispatchEvent(new Event("resize"))
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("320px")
    expect(shell.style.getPropertyValue("--workspace-viewport-top")).toBe("40px")
    viewport.height = 844; viewport.offsetTop = 0
    viewport.dispatchEvent(new Event("scroll"))
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("844px")
    expect(shell.style.getPropertyValue("--workspace-viewport-top")).toBe("0px")
  })

  it("桌面与捏合缩放使用原有布局，恢复正常比例后重新跟随", () => {
    const { viewport, shell } = setup(1440)
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("")
    vi.stubGlobal("innerWidth", 390)
    window.dispatchEvent(new Event("resize"))
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("460px")
    viewport.scale = 2
    viewport.dispatchEvent(new Event("resize"))
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("")
    expect(shell.style.getPropertyValue("--workspace-viewport-top")).toBe("")
    viewport.scale = 1
    viewport.dispatchEvent(new Event("resize"))
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("460px")
  })

  it("不支持 API 或区域值无效时保留 dvh 回退", () => {
    vi.stubGlobal("visualViewport", undefined)
    const view = render(<Fixture />)
    expect(screen.getByTestId("shell").style.cssText).toBe("")
    view.unmount()
    const { viewport, shell } = setup()
    viewport.height = Number.NaN
    viewport.dispatchEvent(new Event("resize"))
    expect(shell.style.cssText).toBe("")
  })

  it("切换会话重建 shell 后，监听绑定新节点并清除旧节点尺寸", () => {
    const { viewport, shell: oldShell, view } = setup()
    view.rerender(<Fixture sessionId="second" />)
    const shell = screen.getByTestId("shell")
    viewport.height = 320
    viewport.dispatchEvent(new Event("resize"))
    expect(shell).not.toBe(oldShell)
    expect(shell.style.getPropertyValue("--workspace-viewport-height")).toBe("320px")
    expect(oldShell.style.cssText).toBe("")
  })

  it("卸载时取消全部窗口监听并清除临时边界", () => {
    const viewport = new Viewport()
    const remove = vi.spyOn(viewport, "removeEventListener")
    const removeWindow = vi.spyOn(window, "removeEventListener")
    vi.stubGlobal("innerWidth", 390)
    vi.stubGlobal("visualViewport", viewport)
    const view = render(<Fixture />)
    const shell = screen.getByTestId("shell")
    view.unmount()
    expect(remove.mock.calls.map(([name]) => name)).toEqual(["resize", "scroll"])
    expect(removeWindow).toHaveBeenCalledWith("resize", expect.any(Function))
    expect(shell.style.cssText).toBe("")
  })
})
