import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSearchStatus } from '../../api/search'
import { listJobs, getJobFilters } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { EmptyState } from '../shared/EmptyState'
import { JobCard } from './JobCard'
import type { JobFiltersResponse } from '../../types'

const PAGE_SIZE = 20

interface ResultsListProps {
  onFiltersLoaded: (data: JobFiltersResponse) => void
}

function ChevronLeft() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M9.78 4.22a.75.75 0 0 1 0 1.06L7.06 8l2.72 2.72a.75.75 0 1 1-1.06 1.06L5.47 8.53a.75.75 0 0 1 0-1.06l3.25-3.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
    </svg>
  )
}

function ChevronRight() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
    </svg>
  )
}

function SearchIdleState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-8 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
        <svg
          className="h-7 w-7"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
          />
        </svg>
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-700">Search for jobs using the panel on the left</p>
        <p className="mt-1 text-xs text-slate-400">Results will appear here once a search completes.</p>
      </div>
    </div>
  )
}

export function ResultsList({ onFiltersLoaded }: ResultsListProps) {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const criteria = useJobSearchStore((s) => s.criteria)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const selectedSources = useJobSearchStore((s) => s.selectedSources)
  const selectedCompanies = useJobSearchStore((s) => s.selectedCompanies)
  const selectedJob = useJobSearchStore((s) => s.selectedJob)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)
  const page = criteria.page ?? 1

  useEffect(() => {
    setSelectedJob(null)
  }, [activeSearchJobId, setSelectedJob])

  useEffect(() => {
    document.getElementById('results-col')?.scrollTo({ top: 0 })
  }, [activeSearchJobId, selectedSources, selectedCompanies])

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

  const filtersQuery = useQuery({
    queryKey: ['jobFilters', activeSearchJobId],
    queryFn: () => getJobFilters(activeSearchJobId!),
    enabled: isSearchComplete && !!activeSearchJobId,
  })

  useEffect(() => {
    if (filtersQuery.data) onFiltersLoaded(filtersQuery.data)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersQuery.data])

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

  const liveRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    if (jobsQuery.data && liveRef.current) {
      liveRef.current.textContent = `${jobsQuery.data.total} results loaded.`
    }
  }, [jobsQuery.data])

  if (!activeSearchJobId) {
    return <SearchIdleState />
  }

  const isPolling = statusQuery.data?.status === 'queued' || statusQuery.data?.status === 'running'
  const isLoadingJobs = isSearchComplete && jobsQuery.isLoading

  if (statusQuery.isError) {
    return (
      <div className="p-5">
        <ErrorBanner message="Could not check search status. Please try again." />
      </div>
    )
  }

  if (isSearchFailed) {
    return (
      <div className="p-5">
        <ErrorBanner
          message={
            statusQuery.data?.error ??
            'The search failed. Please try again with different criteria.'
          }
        />
      </div>
    )
  }

  if (isPolling || isLoadingJobs) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner
          label={isPolling ? 'Searching job boards…' : 'Loading results…'}
          size="lg"
        />
      </div>
    )
  }

  if (jobsQuery.isError) {
    return (
      <div className="p-5">
        <ErrorBanner
          message="Failed to load job listings. Please try again."
          onRetry={() => jobsQuery.refetch()}
        />
      </div>
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

  const total = jobsQuery.data?.total ?? 0
  const totalPages = jobsQuery.data ? Math.ceil(total / PAGE_SIZE) : 0

  if (sortedJobs.length === 0) {
    return (
      <div className="p-5">
        <EmptyState
          title="No jobs found"
          description="No results matched your search. Try different keywords, remove filters, or expand your location."
        />
      </div>
    )
  }

  return (
    <section aria-label="Search results" className="flex flex-col">
      <p aria-live="polite" aria-atomic="true" className="sr-only" ref={liveRef} />

      {/* Results header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-4 py-2.5">
        <div className="flex items-baseline gap-1.5">
          <span className="text-[13px] font-semibold text-slate-800">{total}</span>
          <span className="text-[12px] text-slate-500">jobs found</span>
          {statusQuery.data?.total_results != null && (
            <span className="text-[11px] text-slate-400">
              of {statusQuery.data.total_results} scraped
            </span>
          )}
        </div>
        {totalPages > 1 && (
          <span className="text-[11px] text-slate-400">
            Page {page} of {totalPages}
          </span>
        )}
      </div>

      {/* Job list */}
      <ul className="flex flex-col gap-0 divide-y divide-slate-50" role="list" aria-label="Job listings">
        {sortedJobs.map((job) => (
          <li key={job.id} className="px-3 py-2.5">
            <JobCard
              job={job}
              onShowDetail={() => setSelectedJob(job)}
              isSelected={selectedJob?.id === job.id}
            />
          </li>
        ))}
      </ul>

      {/* Pagination */}
      {totalPages > 1 && (
        <nav
          aria-label="Results pagination"
          className="flex items-center justify-center gap-2 border-t border-slate-100 px-5 py-3.5"
        >
          <button
            onClick={() => setCriteria({ page: page - 1 })}
            disabled={page <= 1}
            aria-label="Previous page"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-600 transition hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft />
            Prev
          </button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let pageNum: number
              if (totalPages <= 7) {
                pageNum = i + 1
              } else if (page <= 4) {
                pageNum = i + 1
              } else if (page >= totalPages - 3) {
                pageNum = totalPages - 6 + i
              } else {
                pageNum = page - 3 + i
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setCriteria({ page: pageNum })}
                  aria-label={`Page ${pageNum}`}
                  aria-current={pageNum === page ? 'page' : undefined}
                  className={`h-7 w-7 rounded-lg text-[12px] font-medium transition focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    pageNum === page
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {pageNum}
                </button>
              )
            })}
          </div>
          <button
            onClick={() => setCriteria({ page: page + 1 })}
            disabled={page >= totalPages}
            aria-label="Next page"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-600 transition hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
            <ChevronRight />
          </button>
        </nav>
      )}
    </section>
  )
}
