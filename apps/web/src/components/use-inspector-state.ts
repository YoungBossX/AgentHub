"use client"

import { useState } from "react"

type Preference = { collapsed?: boolean; overlay: boolean; expanded: boolean }
const initial: Preference = { overlay: false, expanded: false }

export function useInspectorState(sessionId: string | null, hasSelection: boolean) {
  const [sessions, setSessions] = useState<Record<string, Preference>>({})
  const key = sessionId ?? ""
  const preference = sessions[key] ?? initial
  const collapsed = preference.collapsed ?? !hasSelection
  function update(change: (previous: Preference) => Preference) {
    setSessions(previous => ({ ...previous, [key]: change(previous[key] ?? initial) }))
  }
  return {
    collapsed, overlay: preference.overlay, expanded: preference.expanded,
    reveal: () => update(previous => ({ ...previous, collapsed: false, overlay: true })),
    close: () => update(() => ({ collapsed: true, overlay: false, expanded: false })),
    dismissOverlay: () => update(previous => ({ ...previous, overlay: false, expanded: false })),
    toggleDesktop: () => update(previous => ({ ...previous, collapsed: !(previous.collapsed ?? !hasSelection), expanded: false })),
    toggleMobile: () => update(previous => ({ ...previous, overlay: !previous.overlay })),
    toggleExpanded: () => update(previous => ({ collapsed: false, overlay: true, expanded: !previous.expanded })),
  }
}
