"use client"

import { useId, useState, type HTMLAttributes, type ReactNode } from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

type Props = Omit<HTMLAttributes<HTMLDivElement>, "onChange"> & {
  summary: ReactNode
  summaryClassName?: string
  defaultOpen?: boolean
  onOpenChange?: (open: boolean) => void
}

export function Disclosure({ summary, summaryClassName, defaultOpen = false, onOpenChange, children, className, ...props }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const id = useId()
  return <div {...props} className={cn("disclosure", className)} data-open={open}>
    <button type="button" className={cn("disclosure-trigger", summaryClassName)} aria-expanded={open} aria-controls={id}
      onClick={() => { setOpen(!open); onOpenChange?.(!open) }}>
      <ChevronRight aria-hidden="true" size={13} className="disclosure-chevron" />
      <span className="min-w-0">{summary}</span>
    </button>
    <div id={id} className="disclosure-grid" inert={!open} aria-hidden={!open}>
      <div className="disclosure-clip"><div className="disclosure-content">{children}</div></div>
    </div>
  </div>
}
