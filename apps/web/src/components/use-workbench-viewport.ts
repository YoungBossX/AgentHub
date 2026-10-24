"use client"

import { useCallback, useEffect, useState, useSyncExternalStore } from "react"

function subscribeViewport(change: () => void) {
  const viewport = window.visualViewport
  window.addEventListener("resize", change)
  viewport?.addEventListener("resize", change)
  return () => {
    window.removeEventListener("resize", change)
    viewport?.removeEventListener("resize", change)
  }
}

function compactInputSnapshot() {
  const viewport = window.visualViewport
  return window.innerWidth < 1024 && (viewport?.scale ?? 1) === 1
    && (viewport?.height ?? window.innerHeight) < 600
}

export function useCompactInput() {
  return useSyncExternalStore(subscribeViewport, compactInputSnapshot, () => false)
}

export function useWorkbenchViewport() {
  const [node, setNode] = useState<HTMLElement | null>(null)
  const ref = useCallback((element: HTMLElement | null) => { setNode(element) }, [])
  useEffect(() => {
    const viewport = window.visualViewport
    if (!node || !viewport) return
    const reset = () => {
      node.style.removeProperty("--workspace-viewport-height")
      node.style.removeProperty("--workspace-viewport-top")
    }
    const update = () => {
      if (window.innerWidth >= 1024 || viewport.scale !== 1 || !Number.isFinite(viewport.height)
        || viewport.height <= 0 || !Number.isFinite(viewport.offsetTop)) {
        reset()
        return
      }
      node.style.setProperty("--workspace-viewport-height", `${viewport.height}px`)
      node.style.setProperty("--workspace-viewport-top", `${Math.max(0, viewport.offsetTop)}px`)
    }
    update()
    viewport.addEventListener("resize", update)
    viewport.addEventListener("scroll", update)
    window.addEventListener("resize", update)
    return () => {
      viewport.removeEventListener("resize", update)
      viewport.removeEventListener("scroll", update)
      window.removeEventListener("resize", update)
      reset()
    }
  }, [node])
  return ref
}
