export type Theme = "light" | "dark"

export const THEME_STORAGE_KEY = "agenthub.theme"
const THEME_EVENT = "agenthub:theme-change"
let themeChangeGeneration = 0

export function normalizeTheme(value: unknown): Theme {
  return value === "dark" ? "dark" : "light"
}

export const THEME_INIT_SCRIPT = `(() => {
  let theme = "light";
  try { if (localStorage.getItem("${THEME_STORAGE_KEY}") === "dark") theme = "dark"; } catch {}
  document.documentElement.dataset.theme = theme;
})();`

export function getTheme(): Theme {
  return normalizeTheme(document.documentElement.dataset.theme)
}

export function getServerTheme(): Theme {
  return "light"
}

function applyTheme(theme: Theme) {
  const root = document.documentElement
  const generation = ++themeChangeGeneration
  root.dataset.themeChanging = "true"
  root.dataset.theme = theme
  // Keep the pause through one render so normal transitions resume after
  // the new foreground and background have already been applied together.
  window.requestAnimationFrame(() => {
    if (generation !== themeChangeGeneration) return
    window.requestAnimationFrame(() => {
      if (generation === themeChangeGeneration) delete root.dataset.themeChanging
    })
  })
}

export function setTheme(theme: Theme) {
  applyTheme(theme)
  try { localStorage.setItem(THEME_STORAGE_KEY, theme) } catch { /* Switching still works without storage. */ }
  window.dispatchEvent(new Event(THEME_EVENT))
}

export function subscribeTheme(onChange: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key !== THEME_STORAGE_KEY && event.key !== null) return
    // Ignore sessionStorage events; access to localStorage itself can be denied.
    try { if (event.storageArea && event.storageArea !== localStorage) return } catch { return }
    applyTheme(normalizeTheme(event.newValue))
    onChange()
  }
  window.addEventListener(THEME_EVENT, onChange)
  window.addEventListener("storage", onStorage)
  return () => {
    window.removeEventListener(THEME_EVENT, onChange)
    window.removeEventListener("storage", onStorage)
  }
}
