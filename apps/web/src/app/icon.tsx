import { brandIcon } from "@/lib/brand-icon"

export const size = { width: 64, height: 64 }
export const contentType = "image/png"
export const dynamic = "force-static"
export default function Icon() { return brandIcon(size.width) }
