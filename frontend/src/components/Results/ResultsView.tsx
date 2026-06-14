import { useQuery } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { getSearchStatus } from '../../api/search'
import { getJobFilters } from '../../api/jobs'
import { Logo } from '../shared/Logo'
import { SearchBar } from '../shared/SearchBar'
import { ResumeUpload } from '../shared/ResumeUpload'
import { ResultsList } from '../ResultsList/ResultsList'
import { FiltersPanel } from './FiltersPanel'
import { ErrorBoundary } from '../shared/ErrorBoundary'
import { hasFilters } from '../../lib/constants'

export function ResultsView() {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const resetToLanding = useJobSearchStore((s) => s.resetToLanding)
  const setShowInsights = useJobSearchStore((s) => s.setShowInsights)
  const setShowPasteJd = useJobSearchStore((s) => s.setShowPasteJd)
  const setShowSavedApplications = useJobSearchStore((s) => s.setShowSavedApplications)
  const selectedSources = useJobSearchStore((s) => s.selectedSources)
  const selectedCompanies = useJobSearchStore((s) => s.selectedCompanies)

  // Derive filter options straight from the TanStack Query cache (shared with
  // ResultsList via the same query keys). Reading from the cache rather than
  // holding local state means the filter rail survives this view unmounting and
  // remounting — e.g. a round trip through Market Insights — instead of vanishing.
  const statusQuery = useQuery({
    queryKey: ['searchStatus', activeSearchJobId],
    queryFn: () => getSearchStatus(activeSearchJobId!),
    enabled: !!activeSearchJobId,
  })
  const isSearchComplete = statusQuery.data?.status === 'complete'

  const filtersQuery = useQuery({
    queryKey: ['jobFilters', activeSearchJobId],
    queryFn: () => getJobFilters(activeSearchJobId!),
    enabled: isSearchComplete && !!activeSearchJobId,
  })
  const filtersData = filtersQuery.data ?? null

  const showRail = hasFilters(filtersData)

  return (
    // Pinned to the viewport (not just `h-full`) so this full-height layout never
    // contributes scroll height to the App's scrollable root. Otherwise, when the
    // filter rail expands ("Show all"), ResultsView can transiently overflow the
    // root, which then scrolls (via scroll anchoring) and leaves a blank viewport
    // until a reflow — the internal <aside>/<main> own all scrolling here.
    <div className="fixed inset-0 flex flex-col bg-slate-50">
      {/* Top bar: brand + live search + resume status */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
        <div className="hidden shrink-0 md:block">
          <Logo onClick={resetToLanding} />
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <SearchBar variant="compact" />
        </div>
        <ResumeUpload variant="inline" />
        <button
          onClick={() => setShowPasteJd(true)}
          className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
          aria-label="Tailor resume from job description"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
          Tailor from JD
        </button>
        <button
          onClick={() => setShowSavedApplications(true)}
          className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
          aria-label="View saved applications"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
          </svg>
          Saved Applications
        </button>
        <button
          onClick={() => setShowInsights(true)}
          className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
          aria-label="View job market insights"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
          </svg>
          Market Insights
        </button>
        <button
          onClick={resetToLanding}
          className="hidden shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
        >
          New search
        </button>
      </header>

      {/* Body */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {showRail && (
          <aside className="hidden w-64 shrink-0 overflow-y-auto overscroll-contain border-r border-slate-200 bg-white px-4 py-5 lg:block">
            <FiltersPanel filtersData={filtersData} />
          </aside>
        )}
        <main id="results-col" className="min-w-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="mx-auto max-w-3xl px-4 py-5 sm:px-6">
            <ErrorBoundary label="ResultsList" resetKeys={[activeSearchJobId, selectedSources, selectedCompanies]}>
              <ResultsList />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}
