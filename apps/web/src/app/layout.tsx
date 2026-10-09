import type { Metadata } from "next"
import type { ReactNode } from "react"
import Script from "next/script"
import { THEME_INIT_SCRIPT } from "@/lib/theme"

import "./globals.css"

export const metadata: Metadata = {
  title: "AgentHub",
  description: "IM-style coding-agent collaboration scaffold",
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <body>
        {children}
        <Script id="agenthub-theme" strategy="beforeInteractive">{THEME_INIT_SCRIPT}</Script>
      </body>
    </html>
  )
}
