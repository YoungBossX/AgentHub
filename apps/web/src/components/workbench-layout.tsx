"use client"

import { useCallback, useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from "react"

type Widths = { sidebar: number; inspector: number }
type Side = keyof Widths
type Drag = { side: Side; pointerId: number; startX: number; start: Widths; last: Widths; previous: Widths | null; element: HTMLDivElement }
export const COLUMN_STORAGE_KEY = "agenthub.workbench-columns"
const MIN = { sidebar: 180, inspector: 280 }
const MAX = { sidebar: 360, inspector: 720 }
const CENTER_MIN = 400
const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), Math.max(min, max))

export function defaultWidths(width: number): Widths {
  return width >= 1600 ? { sidebar: 240, inspector: 420 } : { sidebar: 220, inspector: 360 }
}

export function fitColumnWidths(preferred: Widths, width: number, inspectorVisible: boolean): Widths {
  const sidebar = clamp(preferred.sidebar, MIN.sidebar, MAX.sidebar)
  const inspector = clamp(preferred.inspector, MIN.inspector, MAX.inspector)
  if (width < 1200) return { sidebar, inspector }
  const budget = width - CENTER_MIN
  if (!inspectorVisible) return { sidebar: Math.min(sidebar, budget), inspector }
  const fittedInspector = Math.max(MIN.inspector, Math.min(inspector, budget - sidebar))
  return { sidebar: Math.min(sidebar, budget - fittedInspector), inspector: fittedInspector }
}

function readWidths(): Widths | null {
  try {
    const value = JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY) ?? "null")
    if (!value || !["sidebar", "inspector"].every((side) => typeof value[side] === "number" && Number.isFinite(value[side]) && value[side] >= MIN[side as Side] && value[side] <= MAX[side as Side])) return null
    return { sidebar: value.sidebar, inspector: value.inspector }
  } catch { return null }
}

function saveWidths(widths: Widths) {
  try { localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(widths)) } catch { /* Keep current layout usable when storage is blocked. */ }
}

function ColumnSeparator({ side, value, maximum, controls, onStart, onMove, onFinish, onKeyboard, onReset }: {
  side: Side; value: number; maximum: number; controls: string
  onStart: (side: Side, event: PointerEvent<HTMLDivElement>) => void
  onMove: (event: PointerEvent<HTMLDivElement>) => void
  onFinish: (event: PointerEvent<HTMLDivElement>, commit: boolean) => void
  onKeyboard: (side: Side, event: KeyboardEvent<HTMLDivElement>) => void
  onReset: (side: Side) => void
}) {
  return <div
    role="separator"
    tabIndex={0}
    aria-label={side === "sidebar" ? "调整会话侧栏宽度" : "调整成果面板宽度"}
    aria-orientation="vertical"
    aria-controls={controls}
    aria-valuemin={MIN[side]}
    aria-valuemax={maximum}
    aria-valuenow={Math.round(value)}
    aria-valuetext={`${Math.round(value)} 像素`}
    title="拖动调整宽度；方向键微调，双击恢复默认"
    className={`workbench-resizer workbench-resizer-${side}`}
    onPointerDown={(event) => onStart(side, event)}
    onPointerMove={onMove}
    onPointerUp={(event) => onFinish(event, true)}
    onPointerCancel={(event) => onFinish(event, false)}
    onLostPointerCapture={(event) => onFinish(event, false)}
    onKeyDown={(event) => onKeyboard(side, event)}
    onDoubleClick={() => onReset(side)}
  ><span aria-hidden="true" /></div>
}

export function WorkbenchLayout({ children, className, inspectorCollapsed, inspectorExpanded }: {
  children: ReactNode; className: string; inspectorCollapsed: boolean; inspectorExpanded: boolean
}) {
  const id = useId()
  const container = useRef<HTMLDivElement | null>(null)
  const drag = useRef<Drag | null>(null)
  const [preferred, setPreferred] = useState<Widths | null>(null)
  const [width, setWidth] = useState(0)
  const [resizing, setResizing] = useState(false)
  const inspectorVisible = !inspectorCollapsed && !inspectorExpanded
  const effective = fitColumnWidths(preferred ?? defaultWidths(width), width, inspectorVisible)

  const attach = useCallback((node: HTMLDivElement | null) => {
    container.current = node
    if (node) {
      setWidth(node.getBoundingClientRect().width)
      setPreferred(readWidths())
    }
  }, [])

  const finish = useCallback((commit: boolean) => {
    const current = drag.current
    if (!current) return
    drag.current = null
    setResizing(false)
    if (commit) saveWidths(current.last)
    else setPreferred(current.previous)
    if (current.element.hasPointerCapture?.(current.pointerId)) current.element.releasePointerCapture(current.pointerId)
  }, [])

  useEffect(() => {
    const node = container.current
    if (!node) return
    const measure = () => {
      const nextWidth = node.getBoundingClientRect().width
      setWidth(nextWidth)
      if (nextWidth < 1200) finish(false)
    }
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null
    observer?.observe(node)
    const cancel = () => finish(false)
    window.addEventListener("resize", measure)
    window.addEventListener("blur", cancel)
    return () => {
      observer?.disconnect()
      window.removeEventListener("resize", measure)
      window.removeEventListener("blur", cancel)
      const current = drag.current
      drag.current = null
      if (current?.element.hasPointerCapture?.(current.pointerId)) current.element.releasePointerCapture(current.pointerId)
    }
  }, [finish])

  function maximum(side: Side, sizes = effective) {
    if (width < 1200) return MAX[side]
    const other = side === "sidebar" ? sizes.inspector : sizes.sidebar
    return Math.max(MIN[side], Math.min(MAX[side], width - CENTER_MIN - (side === "sidebar" && !inspectorVisible ? 0 : other)))
  }

  function resize(side: Side, value: number, base = effective): Widths {
    const next = { ...base, [side]: clamp(value, MIN[side], maximum(side, base)) }
    setPreferred(next)
    return next
  }

  function startDrag(side: Side, event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || width < 1200 || drag.current) return
    event.preventDefault()
    event.currentTarget.focus()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    drag.current = { side, pointerId: event.pointerId, startX: event.clientX, start: effective, last: effective, previous: preferred, element: event.currentTarget }
    setResizing(true)
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current
    if (!current || event.pointerId !== current.pointerId) return
    const direction = current.side === "sidebar" ? 1 : -1
    current.last = resize(current.side, current.start[current.side] + direction * (event.clientX - current.startX), effective)
  }

  function keyboardResize(side: Side, event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { finish(false); return }
    if (width < 1200 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
    event.preventDefault()
    const direction = side === "sidebar" ? 1 : -1
    const value = event.key === "Home" ? MIN[side] : event.key === "End" ? maximum(side) : effective[side] + (event.key === "ArrowRight" ? 16 : -16) * direction
    saveWidths(resize(side, value))
  }

  const style = width >= 1200 ? { "--sidebar-width": `${effective.sidebar}px`, "--inspector-width": `${effective.inspector}px` } as CSSProperties : undefined
  return (
    <div id={id} ref={attach} className={`${className} ${resizing ? "is-resizing" : ""}`} style={style}>
      {children}
      {!inspectorExpanded ? (["sidebar", "inspector"] as const).map((side) => side === "inspector" && inspectorCollapsed ? null : (
        <ColumnSeparator
          key={side}
          side={side}
          value={effective[side]}
          maximum={maximum(side)}
          controls={id}
          onStart={startDrag}
          onMove={moveDrag}
          onFinish={(event, commit) => { if (event.pointerId === drag.current?.pointerId) finish(commit) }}
          onKeyboard={keyboardResize}
          onReset={(side) => { if (width >= 1200) saveWidths(resize(side, defaultWidths(width)[side])) }}
        />
      )) : null}
      {resizing ? <div className="workbench-drag-shield" aria-hidden="true" /> : null}
    </div>
  )
}
