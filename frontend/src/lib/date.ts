/**
 * Format a posting date for display. Returns null for missing/unparseable input
 * so callers can skip rendering rather than show "Invalid Date" — and so a bad
 * date string can never throw during render.
 */
export function formatPostedDate(raw: string | null | undefined): string | null {
  if (!raw) return null
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return null
  try {
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return null
  }
}
