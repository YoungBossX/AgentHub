import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { ImageResponse } from "next/og"
import { BRAND_IMAGE_FRAME } from "./brand"

export async function brandIcon(size: number) {
  const bytes = await readFile(join(process.cwd(), "public", "brand", "agenthub.png"))
  return new ImageResponse(
    <div style={{ display: "flex", position: "relative", width: size, height: size, overflow: "hidden", borderRadius: size * .25 }}>
      {/* Metadata rendering embeds the fixed local source, with no optimizer or remote fetch. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img alt="" src={`data:image/png;base64,${bytes.toString("base64")}`} style={{ position: "absolute", ...BRAND_IMAGE_FRAME }} />
    </div>, { width: size, height: size },
  )
}
