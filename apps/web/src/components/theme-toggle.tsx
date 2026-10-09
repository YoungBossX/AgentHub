"use client"

import { useSyncExternalStore } from "react"
import { Moon, Sun } from "lucide-react"
import { getServerTheme, getTheme, setTheme, subscribeTheme } from "@/lib/theme"

export function useTheme() {
  return useSyncExternalStore(subscribeTheme, getTheme, getServerTheme)
}

export function ThemeToggle() {
  const theme = useTheme()
  const label = theme === "dark" ? "切换到亮色模式" : "切换到暗色模式"
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={theme === "dark"}
      title={label}
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="rounded-lg p-2 text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
    >
      {theme === "dark" ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
    </button>
  )
}
