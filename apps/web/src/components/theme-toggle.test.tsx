import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { runInNewContext } from "node:vm"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ThemeToggle } from "./theme-toggle"
import { setTheme, THEME_INIT_SCRIPT, THEME_STORAGE_KEY } from "@/lib/theme"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  delete document.documentElement.dataset.theme
  delete document.documentElement.dataset.themeChanging
})

describe("workbench themes", () => {
  it("keeps colors synchronous through the first rendered frame and restores transitions on the second", () => {
    const frames: FrameRequestCallback[] = []
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback))
    setTheme("dark")
    expect(document.documentElement.dataset.theme).toBe("dark")
    expect(document.documentElement.dataset.themeChanging).toBe("true")
    frames.shift()!(0)
    expect(document.documentElement.dataset.themeChanging).toBe("true")
    frames.shift()!(16)
    expect(document.documentElement.dataset.themeChanging).toBeUndefined()
  })

  it("does not let an older frame resume transitions during a newer theme change", () => {
    const frames: FrameRequestCallback[] = []
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback))
    setTheme("dark")
    frames.shift()!(0)
    setTheme("light")
    frames.shift()!(16)
    expect(document.documentElement.dataset.themeChanging).toBe("true")
    expect(document.documentElement.dataset.theme).toBe("light")
    frames.shift()!(32)
    frames.shift()!(48)
    expect(document.documentElement.dataset.themeChanging).toBeUndefined()
  })

  it("pauses transitions for cross-tab theme updates too", () => {
    const frames: FrameRequestCallback[] = []
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback))
    render(<ThemeToggle />)
    fireEvent(window, new StorageEvent("storage", { key: THEME_STORAGE_KEY, newValue: "dark", storageArea: localStorage }))
    expect(document.documentElement.dataset.themeChanging).toBe("true")
    expect(document.documentElement.dataset.theme).toBe("dark")
    frames.shift()!(0)
    frames.shift()!(16)
    expect(document.documentElement.dataset.themeChanging).toBeUndefined()
  })
  it("switches both directions and persists the explicit choice", () => {
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole("button", { name: "切换到暗色模式" }))
    expect(document.documentElement.dataset.theme).toBe("dark")
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark")
    expect(screen.getByRole("button", { name: "切换到亮色模式" }).getAttribute("aria-pressed")).toBe("true")
    fireEvent.click(screen.getByRole("button", { name: "切换到亮色模式" }))
    expect(document.documentElement.dataset.theme).toBe("light")
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light")
  })

  it.each(["dark", "light", "unsupported"])("restores %s safely before mounting the toolbar", (stored) => {
    localStorage.setItem(THEME_STORAGE_KEY, stored)
    runInNewContext(THEME_INIT_SCRIPT, { localStorage, document })
    render(<ThemeToggle />)
    expect(document.documentElement.dataset.theme).toBe(stored === "dark" ? "dark" : "light")
    expect(screen.getByRole("button", { name: stored === "dark" ? "切换到亮色模式" : "切换到暗色模式" })).toBeTruthy()
  })

  it("starts in light when reading browser storage is denied", () => {
    runInNewContext(THEME_INIT_SCRIPT, { document, localStorage: { getItem() { throw new Error("denied") } } })
    expect(document.documentElement.dataset.theme).toBe("light")
  })

  it("remains usable when saving browser storage is denied", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied") })
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole("button", { name: "切换到暗色模式" }))
    expect(document.documentElement.dataset.theme).toBe("dark")
    fireEvent.click(screen.getByRole("button", { name: "切换到亮色模式" }))
    expect(document.documentElement.dataset.theme).toBe("light")
  })

  it("syncs local-storage changes and clears while ignoring other settings", () => {
    render(<ThemeToggle />)
    fireEvent(window, new StorageEvent("storage", { key: THEME_STORAGE_KEY, newValue: "dark", storageArea: localStorage }))
    expect(screen.getByRole("button", { name: "切换到亮色模式" })).toBeTruthy()
    fireEvent(window, new StorageEvent("storage", { key: "other-setting", newValue: "light", storageArea: localStorage }))
    fireEvent(window, new StorageEvent("storage", { key: THEME_STORAGE_KEY, newValue: "light", storageArea: sessionStorage }))
    expect(document.documentElement.dataset.theme).toBe("dark")
    fireEvent(window, new StorageEvent("storage", { key: null, newValue: null, storageArea: localStorage }))
    expect(screen.getByRole("button", { name: "切换到暗色模式" })).toBeTruthy()
  })
})
