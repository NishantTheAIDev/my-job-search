import { useQuery } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { getSearchStatus } from '../../api/search'
import { getJobFilters } from '../../api/jobs'
import { Logo } from '../shared/Logo'
import { SearchBar } from '../shared/SearchBar'
import { ResumeUpload } from '../shared/ResumeUpload'
import { NavMenu } from '../shared/NavMenu'
import { ResultsList } from '../ResultsList/ResultsList'
import { FiltersPanel } from './FiltersPanel'
import { ErrorBoundary } from '../shared/ErrorBoundary'
import { hasFilters } from '../../lib/constants'

export function ResultsView() {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const resetToLanding = useJobSearchStore((s) => s.resetToLanding)
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
      {/* Top bar: brand + live search + resume status + menu */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
        <div className="hidden shrink-0 lg:block">
          <Logo onClick={resetToLanding} />
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <SearchBar variant="compact" />
        </div>
        <ResumeUpload variant="inline" />
        <NavMenu />
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
