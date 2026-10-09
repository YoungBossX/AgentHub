export function invoiceTotalCents(lines) {
  return lines.reduce((total, line) => total + line.priceCents * line.quantity, 0);
}
