import Image from "next/image"
import { BRAND_IMAGE_FRAME, BRAND_IMAGE_SRC } from "@/lib/brand"

export function BrandMark() {
  return <span aria-hidden="true" data-brand="agenthub" className="relative block h-10 w-10 shrink-0 overflow-hidden rounded-xl">
    <Image src={BRAND_IMAGE_SRC} alt="" width={64} height={64} sizes="52px" loading="eager"
      className="absolute max-w-none" style={BRAND_IMAGE_FRAME} />
  </span>
}
