// Mass = 1. Sample the analytic damped spring once, not on every animation frame.
export function springPosition(stiffness: number, damping: number, seconds: number) {
  const frequency = Math.sqrt(stiffness)
  const decay = damping / 2
  if (decay > frequency) {
    const root = Math.sqrt(decay * decay - stiffness)
    const slow = -decay + root
    const fast = -decay - root
    return 1 + (fast * Math.exp(slow * seconds) - slow * Math.exp(fast * seconds)) / (slow - fast)
  }
  const oscillation = Math.sqrt(stiffness - decay * decay)
  if (!oscillation) return 1 - Math.exp(-decay * seconds) * (1 + decay * seconds)
  return 1 - Math.exp(-decay * seconds) * (Math.cos(oscillation * seconds) + decay / oscillation * Math.sin(oscillation * seconds))
}

function spring(stiffness: number, damping: number) {
  const decay = damping / 2
  const slowest = decay > Math.sqrt(stiffness) ? decay - Math.sqrt(decay * decay - stiffness) : decay
  const duration = Math.ceil(1000 * Math.log(1000) / slowest)
  const samples = Array.from({ length: 61 }, (_, i) => i === 60 ? 1 : Number(springPosition(stiffness, damping, duration * i / 60_000).toFixed(5)))
  return { duration: `${duration}ms`, easing: `linear(${samples.join(", ")})` }
}

const firm = spring(1200, 80)
const confirm = spring(380, 18)
export const MOTION_STYLE = {
  "--spring-firm": firm.easing,
  "--spring-firm-duration": firm.duration,
  "--spring-confirm": confirm.easing,
  "--spring-confirm-duration": confirm.duration,
}
