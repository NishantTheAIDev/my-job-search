import type { InsightsRegion } from '../../types'

const REGION_LOCALE: Record<InsightsRegion, string> = {
  in: 'en-IN',
  us: 'en-US',
  gb: 'en-GB',
  world: 'en-US',
}

const REGION_CURRENCY: Record<InsightsRegion, string> = {
  in: 'INR',
  us: 'USD',
  gb: 'GBP',
  world: 'USD',
}

/**
 * Format a salary value with the correct locale grouping and currency symbol.
 * Returns "—" when value is null/undefined.
 */
export function formatSalary(
  value: number | null | undefined,
  region: InsightsRegion,
  currency?: string,
): string {
  if (value == null) return '—'
  const resolvedCurrency = currency ?? REGION_CURRENCY[region]
  const locale = REGION_LOCALE[region]
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: resolvedCurrency,
      maximumFractionDigits: 0,
    }).format(value)
  } catch {
    // Fallback if currency code is unrecognised
    return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value)
  }
}

/** Format a plain number with locale grouping (no currency). */
export function formatNumber(value: number, locale = 'en-US'): string {
  return new Intl.NumberFormat(locale).format(value)
}

/** Parse a GDELT seendate string (YYYYMMDDThhmmssZ) to a readable date. */
export function parseGdeltDate(seendate: string): string {
  // e.g. "20260614T100000Z"
  if (!seendate || seendate.length < 8) return seendate
  const year = seendate.slice(0, 4)
  const month = seendate.slice(4, 6)
  const day = seendate.slice(6, 8)
  const isoString = `${year}-${month}-${day}T${seendate.slice(9, 11)}:${seendate.slice(11, 13)}:${seendate.slice(13, 15)}Z`
  try {
    return new Date(isoString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return `${day} ${new Date(`${year}-${month}-01`).toLocaleString('en-GB', { month: 'short' })} ${year}`
  }
}
