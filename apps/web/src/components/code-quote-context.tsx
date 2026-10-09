"use client"

import { createContext, useContext } from "react"

export const MAX_QUOTED_CODE_CHARS = 2400
export type CodeQuote = { artifactId: string; path: string; text: string }
export const CodeQuoteContext = createContext<((quote: CodeQuote) => void) | null>(null)
export const useCodeQuote = () => useContext(CodeQuoteContext)
