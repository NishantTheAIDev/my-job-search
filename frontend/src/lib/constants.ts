import type { JobFiltersResponse, SearchCriteria } from '../types'

/** True when a completed search has at least one source/company worth filtering on. */
export function hasFilters(filtersData: JobFiltersResponse | null): boolean {
  if (!filtersData) return false
  return filtersData.sources.length >= 2 || filtersData.companies.length > 0
}

/** Accent dot color per job board source. */
export const SOURCE_COLORS: Record<string, string> = {
  adzuna: 'bg-blue-500',
  greenhouse: 'bg-emerald-500',
  lever: 'bg-purple-500',
  linkedin: 'bg-sky-500',
  indeed: 'bg-blue-700',
  jsearch: 'bg-indigo-500',
  remotive: 'bg-teal-500',
  themuse: 'bg-rose-500',
  arbeitnow: 'bg-orange-500',
  jobicy: 'bg-green-500',
  weworkremotely: 'bg-cyan-600',
}

export const POSTED_WITHIN_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
]

/** Boards the app fans out across — shown on the landing page. */
export const SUPPORTED_BOARDS: { key: string; label: string }[] = [
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'indeed', label: 'Indeed' },
  { key: 'adzuna', label: 'Adzuna' },
  { key: 'jsearch', label: 'JSearch' },
  { key: 'greenhouse', label: 'Greenhouse' },
  { key: 'lever', label: 'Lever' },
  { key: 'remotive', label: 'Remotive' },
  { key: 'themuse', label: 'The Muse' },
  { key: 'arbeitnow', label: 'Arbeitnow' },
  { key: 'jobicy', label: 'Jobicy' },
  { key: 'weworkremotely', label: 'We Work Remotely' },
]

export function syncCriteriaToUrl(criteria: SearchCriteria) {
  const params = new URLSearchParams()
  if (criteria.query) params.set('q', criteria.query)
  if (criteria.location) params.set('location', criteria.location)
  if (criteria.remote_only) params.set('remote', '1')
  if (criteria.posted_within_days) params.set('posted', String(criteria.posted_within_days))
  const search = params.toString()
  window.history.replaceState(null, '', search ? `?${search}` : window.location.pathname)
}

export function parseCriteriaFromUrl(): Partial<SearchCriteria> {
  const params = new URLSearchParams(window.location.search)
  return {
    query: params.get('q') ?? '',
    location: params.get('location') ?? undefined,
    remote_only: params.get('remote') === '1',
    posted_within_days: params.get('posted') ? parseInt(params.get('posted')!, 10) : undefined,
  }
}
