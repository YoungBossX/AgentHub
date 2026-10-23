import { expect, it } from "vitest"
import { springPosition } from "./motion"

it("keeps 1200/80 drag feedback monotone without rebound", () => {
  const values = Array.from({ length: 121 }, (_, i) => springPosition(1200, 80, i / 120))
  expect(values[0]).toBe(0)
  expect(values.every((value, i) => value <= 1 && (!i || value >= values[i - 1]))).toBe(true)
  expect(values.at(-1)).toBeGreaterThan(.999)
})
it("gives 380/18 confirmation a small overshoot and then settles", () => {
  const values = Array.from({ length: 121 }, (_, i) => springPosition(380, 18, i / 120))
  expect(Math.max(...values)).toBeGreaterThan(1)
  expect(Math.max(...values)).toBeLessThan(1.25)
  expect(values.at(-1)).toBeCloseTo(1, 3)
})
