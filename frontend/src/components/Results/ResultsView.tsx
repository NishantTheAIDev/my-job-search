import { useEffect, useState } from 'react'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { Logo } from '../shared/Logo'
import { SearchBar } from '../shared/SearchBar'
import { ResumeUpload } from '../shared/ResumeUpload'
import { ResultsList } from '../ResultsList/ResultsList'
import { FiltersPanel } from './FiltersPanel'
import { hasFilters } from '../../lib/constants'
import type { JobFiltersResponse } from '../../types'

export function ResultsView() {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const resetToLanding = useJobSearchStore((s) => s.resetToLanding)
  const setShowInsights = useJobSearchStore((s) => s.setShowInsights)

  const [filtersData, setFiltersData] = useState<JobFiltersResponse | null>(null)

  // Reset the cached filter options whenever a new search starts.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFiltersData(null)
  }, [activeSearchJobId])

  const showRail = hasFilters(filtersData)

  return (
    <div className="flex h-full flex-col bg-slate-50">
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
          <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-slate-200 bg-white px-4 py-5 lg:block">
            <FiltersPanel filtersData={filtersData} />
          </aside>
        )}
        <main id="results-col" className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-5 sm:px-6">
            <ResultsList onFiltersLoaded={setFiltersData} />
          </div>
        </main>
      </div>
    </div>
  )
}
