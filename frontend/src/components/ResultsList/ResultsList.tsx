import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSearchStatus } from '../../api/search'
import { listJobs, getJobFilters } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { EmptyState } from '../shared/EmptyState'
import { JobCard } from './JobCard'
import { ResultsFilterPanel } from './ResultsFilterPanel'

const PAGE_SIZE = 20

export function ResultsList() {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const criteria = useJobSearchStore((s) => s.criteria)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const page = criteria.page ?? 1

  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [selectedCompanies, setSelectedCompanies] = useState<string[]>([])

  // Reset filter state whenever the active search changes
  useEffect(() => {
    setSelectedSources([])
    setSelectedCompanies([])
  }, [activeSearchJobId])

  // Poll search status
  const statusQuery = useQuery({
    queryKey: ['searchStatus', activeSearchJobId],
    queryFn: () => getSearchStatus(activeSearchJobId!),
    enabled: !!activeSearchJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'queued' || status === 'running' ? 2000 : false
    },
  })

  const isSearchComplete = statusQuery.data?.status === 'complete'
  const isSearchFailed = statusQuery.data?.status === 'failed'

  // Fetch available filter options once the search is done
  const filtersQuery = useQuery({
    queryKey: ['jobFilters', activeSearchJobId],
    queryFn: () => getJobFilters(activeSearchJobId!),
    enabled: isSearchComplete && !!activeSearchJobId,
  })

  // Fetch jobs once complete, re-fetch when filters or page change
  const jobsQuery = useQuery({
    queryKey: ['jobs', activeSearchJobId, page, selectedSources, selectedCompanies],
    queryFn: () =>
      listJobs({
        search_job_id: activeSearchJobId!,
        page,
        page_size: PAGE_SIZE,
        source: selectedSources.length ? selectedSources : undefined,
        company: selectedCompanies.length ? selectedCompanies : undefined,
      }),
    enabled: isSearchComplete && !!activeSearchJobId,
  })

  // Announce to screen readers when results arrive
  const liveRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    if (jobsQuery.data && liveRef.current) {
      liveRef.current.textContent = `${jobsQuery.data.total} results loaded.`
    }
  }, [jobsQuery.data])

  // Reset to page 1 when filters change
  function handleSourceChange(sources: string[]) {
    setSelectedSources(sources)
    setCriteria({ page: 1 })
  }

  function handleCompanyChange(companies: string[]) {
    setSelectedCompanies(companies)
    setCriteria({ page: 1 })
  }

  if (!activeSearchJobId) return null

  const isPolling = statusQuery.data?.status === 'queued' || statusQuery.data?.status === 'running'
  const isLoadingJobs = isSearchComplete && jobsQuery.isLoading

  if (statusQuery.isError) {
    return (
      <section aria-label="Search results" className="mx-auto w-full max-w-3xl">
        <ErrorBanner message="Could not check search status. Please try again." />
      </section>
    )
  }

  if (isSearchFailed) {
    return (
      <section aria-label="Search results" className="mx-auto w-full max-w-3xl">
        <ErrorBanner
          message={statusQuery.data?.error ?? 'The search failed. Please try again with different criteria.'}
        />
      </section>
    )
  }

  const sortedJobs = jobsQuery.data
    ? [...jobsQuery.data.items].sort((a, b) => {
        if (a.match_score === null && b.match_score === null) return 0
        if (a.match_score === null) return 1
        if (b.match_score === null) return -1
        return b.match_score - a.match_score
      })
    : []

  const totalPages = jobsQuery.data
    ? Math.ceil(jobsQuery.data.total / PAGE_SIZE)
    : 0

  // Show the filter panel only when there is meaningful filter data:
  // at least 2 distinct sources OR at least 1 company.
  const filtersData = filtersQuery.data
  const showFilterPanel =
    isSearchComplete &&
    filtersData != null &&
    (filtersData.sources.length >= 2 || filtersData.companies.length > 0)

  return (
    <section
      aria-label="Search results"
      className={`mx-auto w-full ${showFilterPanel ? 'max-w-5xl' : 'max-w-3xl'}`}
    >
      {/* Live region for screen readers */}
      <p aria-live="polite" aria-atomic="true" className="sr-only" ref={liveRef} />

      {(isPolling || isLoadingJobs) && (
        <LoadingSpinner
          label={isPolling ? 'Searching job boards...' : 'Loading results...'}
          size="lg"
        />
      )}

      {jobsQuery.isError && (
        <ErrorBanner
          message="Failed to load job listings. Please try again."
          onRetry={() => jobsQuery.refetch()}
        />
      )}

      {/* Search returned nothing at all and there are no filters to show */}
      {isSearchComplete && !isLoadingJobs && !jobsQuery.isError && sortedJobs.length === 0 && !showFilterPanel && (
        <EmptyState
          title="No jobs found"
          description="No results matched your search. Try different keywords, remove filters, or expand your location."
        />
      )}

      {/* Main layout: sidebar (when filters available) + results column */}
      {isSearchComplete && !isLoadingJobs && !jobsQuery.isError && (showFilterPanel || sortedJobs.length > 0) && (
        <div className={showFilterPanel ? 'flex gap-6 items-start' : undefined}>
          {/* Left sidebar — always shown when filter data exists, even if current filters yield 0 results */}
          {showFilterPanel && (
            <aside className="w-52 shrink-0 self-start sticky top-4">
              <ResultsFilterPanel
                sources={filtersData!.sources}
                companies={filtersData!.companies}
                selectedSources={selectedSources}
                selectedCompanies={selectedCompanies}
                onSourceChange={handleSourceChange}
                onCompanyChange={handleCompanyChange}
              />
            </aside>
          )}

          {/* Right — job list or filter-empty state */}
          <div className={showFilterPanel ? 'min-w-0 flex-1' : undefined}>
            {sortedJobs.length === 0 ? (
              <EmptyState
                title="No jobs match your filters"
                description="This source and company combination has no overlap. Try clearing one of the filters."
              />
            ) : (
              <>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm text-gray-600">
                    <span className="font-medium">{jobsQuery.data?.total}</span> jobs found
                    {statusQuery.data?.total_results !== null &&
                      statusQuery.data?.total_results !== undefined && (
                        <span className="text-gray-400"> (from {statusQuery.data.total_results} scraped)</span>
                      )}
                  </p>
                  <p className="text-sm text-gray-500">
                    Page {page} of {totalPages}
                  </p>
                </div>

                <ul className="flex flex-col gap-3" role="list" aria-label="Job listings">
                  {sortedJobs.map((job) => (
                    <li key={job.id}>
                      <JobCard job={job} />
                    </li>
                  ))}
                </ul>

                {/* Pagination */}
                {totalPages > 1 && (
                  <nav
                    aria-label="Results pagination"
                    className="mt-6 flex items-center justify-center gap-2"
                  >
                    <button
                      onClick={() => setCriteria({ page: page - 1 })}
                      disabled={page <= 1}
                      aria-label="Previous page"
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      &larr; Prev
                    </button>
                    <span className="text-sm text-gray-600">
                      {page} / {totalPages}
                    </span>
                    <button
                      onClick={() => setCriteria({ page: page + 1 })}
                      disabled={page >= totalPages}
                      aria-label="Next page"
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Next &rarr;
                    </button>
                  </nav>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
