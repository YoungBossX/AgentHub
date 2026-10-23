import type { Metadata } from "next"
import type { ReactNode } from "react"
import Script from "next/script"
import { THEME_INIT_SCRIPT } from "@/lib/theme"
import { MOTION_STYLE } from "@/lib/motion"
import type { CSSProperties } from "react"

import "./globals.css"

export const metadata: Metadata = {
  title: "AgentHub",
  description: "IM-style coding-agent collaboration scaffold",
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" data-theme="light" suppressHydrationWarning>
      <body style={MOTION_STYLE as CSSProperties}>
        {children}
        <Script id="agenthub-theme" strategy="beforeInteractive">{THEME_INIT_SCRIPT}</Script>
      </body>
    </html>
  )
}
