import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import type { ButtonHTMLAttributes } from "react"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex h-10 items-center justify-center gap-2 rounded px-4 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-[var(--primary-strong)]",
        secondary:
          "border border-[var(--border)] bg-white text-[var(--foreground)] hover:bg-slate-50",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({
  asChild = false,
  className,
  variant,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button"
  return <Comp className={cn(buttonVariants({ variant, className }))} {...props} />
}
