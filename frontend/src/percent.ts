/** toFixed+parseFloat avoids artifacts like "10.000000000000002%". */
export function pct(part: number, whole: number): string {
  return `${parseFloat(((part / whole) * 100).toFixed(2))}%`;
}
