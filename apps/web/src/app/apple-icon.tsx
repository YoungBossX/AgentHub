import { brandIcon } from "@/lib/brand-icon"

export const size = { width: 180, height: 180 }
export const contentType = "image/png"
export const dynamic = "force-static"
export default function AppleIcon() { return brandIcon(size.width) }
