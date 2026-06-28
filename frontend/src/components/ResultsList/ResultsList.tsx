import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { createSearch, getSearchStatus } from '../../api/search'
import { listJobs } from '../../api/jobs'
import { diffSavedSearch } from '../../api/savedSearches'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { EmptyState } from '../shared/EmptyState'
import { SaveSearchButton } from '../shared/SaveSearchButton'
import { JobCard } from './JobCard'

const PAGE_SIZE = 20

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

export function ResultsList() {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const criteria = useJobSearchStore((s) => s.criteria)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const selectedSources = useJobSearchStore((s) => s.selectedSources)
  const selectedCompanies = useJobSearchStore((s) => s.selectedCompanies)
  const selectedJob = useJobSearchStore((s) => s.selectedJob)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)
  const activeSavedSearchId = useJobSearchStore((s) => s.activeSavedSearchId)
  const setActiveSavedSearchId = useJobSearchStore((s) => s.setActiveSavedSearchId)
  const setActiveSearchJob = useJobSearchStore((s) => s.setActiveSearchJob)
  const setSelectedSources = useJobSearchStore((s) => s.setSelectedSources)
  const setSelectedCompanies = useJobSearchStore((s) => s.setSelectedCompanies)
  const lastSearchCached = useJobSearchStore((s) => s.lastSearchCached)
  const setLastSearchCached = useJobSearchStore((s) => s.setLastSearchCached)
  const page = criteria.page ?? 1

  // Local ephemeral state — mirrors how source/company filters are handled.
  // Reset when the active search changes so a new search starts filtered.
  const [showLowRelevance, setShowLowRelevance] = useState(false)
  const [showNewOnly, setShowNewOnly] = useState(false)

  useEffect(() => {
    setSelectedJob(null)
    setShowLowRelevance(false)
    setShowNewOnly(false)
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
  const isSearchRunning =
    statusQuery.data?.status === 'running' || statusQuery.data?.status === 'queued'

  const jobsQuery = useQuery({
    queryKey: ['jobs', activeSearchJobId, page, selectedSources, selectedCompanies, showLowRelevance],
    queryFn: () =>
      listJobs({
        search_job_id: activeSearchJobId!,
        page,
        page_size: PAGE_SIZE,
        min_relevance: showLowRelevance ? 0 : undefined,
        source: selectedSources.length ? selectedSources : undefined,
        company: selectedCompanies.length ? selectedCompanies : undefined,
      }),
    enabled: !!activeSearchJobId && (isSearchRunning || isSearchComplete),
    // Poll on the same 2 s cadence as statusQuery while the search is still running.
    refetchInterval: isSearchRunning ? 2000 : false,
  })

  // "New since last run" — only when this run originated from a saved search.
  // The diff endpoint is idempotent per search_job_id, so it's safe to call once
  // the run completes; it advances the saved-search baseline as a side effect.
  const diffQuery = useQuery({
    queryKey: ['savedSearchDiff', activeSavedSearchId, activeSearchJobId],
    queryFn: () => diffSavedSearch(activeSavedSearchId!, activeSearchJobId!),
    enabled: !!activeSavedSearchId && !!activeSearchJobId && isSearchComplete,
    staleTime: Infinity,
  })

  const newIds = useMemo(
    () => new Set(diffQuery.data?.new_posting_ids ?? []),
    [diffQuery.data],
  )

  // Re-search: forces a fresh scrape bypassing same-day cache. Mirrors
  // SearchBar's searchMutation — once setActiveSearchJob fires, the existing
  // statusQuery polling automatically kicks in for the new job id.
  const reSearchMutation = useMutation({
    mutationFn: () => createSearch({ ...criteria, page: 1 }, true),
    onSuccess: (data) => {
      setActiveSavedSearchId(null)
      setActiveSearchJob(data.job_id)
      setSelectedJob(null)
      setSelectedSources([])
      setSelectedCompanies([])
      setLastSearchCached(data.cached ?? false)
    },
  })

  const liveRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    if (jobsQuery.data && liveRef.current) {
      liveRef.current.textContent = `${jobsQuery.data.total} results loaded.`
    }
  }, [jobsQuery.data])

  // ResultsList only renders inside ResultsView, which mounts after a search
  // starts — but guard defensively in case it's rendered without one.
  if (!activeSearchJobId) return null

  // Show a full-screen spinner only when we have zero results yet and the search
  // is still running (i.e. the very first poll hasn't delivered anything yet).
  const hasNoResultsYet = !jobsQuery.data || jobsQuery.data.items.length === 0
  const isInitialLoad = isSearchRunning && hasNoResultsYet && !jobsQuery.isError

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

  if (isInitialLoad) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner label="Searching job boards…" size="lg" />
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

  // "New only" filter — applied after sorting so relevance order is preserved
  const displayedJobs = showNewOnly ? sortedJobs.filter((j) => newIds.has(j.id)) : sortedJobs

  const total = jobsQuery.data?.total ?? 0
  const totalPages = jobsQuery.data ? Math.ceil(total / PAGE_SIZE) : 0

  if (sortedJobs.length === 0) {
    return (
      <div className="p-5">
        <EmptyState
          title="No jobs found"
          description={
            !showLowRelevance
              ? 'No relevant results matched your search. Try enabling "Show low-relevance" above, remove filters, or search with different keywords.'
              : 'No results matched your search. Try different keywords, remove filters, or expand your location.'
          }
        />
      </div>
    )
  }

  return (
    <section aria-label="Search results" className="flex flex-col">
      <p aria-live="polite" aria-atomic="true" className="sr-only" ref={liveRef} />

      {/* Results header */}
      <div className="sticky top-0 z-10 border-b border-slate-100 bg-white px-4 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-baseline gap-1.5">
            <span className="text-[13px] font-semibold text-slate-800">{total}</span>
            <span className="text-[12px] text-slate-500">jobs found</span>
            {statusQuery.data?.total_results != null && (
              <span className="text-[11px] text-slate-400">
                of {statusQuery.data.total_results} scraped
              </span>
            )}
            {activeSavedSearchId && isSearchComplete && (diffQuery.data?.new_count ?? 0) > 0 && (
              <span className="ml-1 inline-flex items-center rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
                {diffQuery.data!.new_count} new
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* Re-search: force a fresh scrape bypassing the same-day cache */}
            <button
              type="button"
              onClick={() => reSearchMutation.mutate()}
              disabled={reSearchMutation.isPending || isSearchRunning}
              aria-busy={reSearchMutation.isPending}
              aria-label="Re-run this search, bypassing cached results"
              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              {reSearchMutation.isPending ? 'Searching…' : 'Re-search'}
            </button>
            <SaveSearchButton />
            {/* "New only" toggle — only shown for saved-search runs with new results */}
            {activeSavedSearchId && isSearchComplete && newIds.size > 0 && (
              <label className="flex cursor-pointer items-center gap-1.5 select-none">
                <div
                  role="checkbox"
                  aria-checked={showNewOnly}
                  tabIndex={0}
                  onClick={() => setShowNewOnly((v) => !v)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setShowNewOnly((v) => !v)
                    }
                  }}
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 ${
                    showNewOnly
                      ? 'border-indigo-500 bg-indigo-500 text-white'
                      : 'border-slate-300 bg-white'
                  }`}
                  aria-label="Show new results only"
                >
                  {showNewOnly && (
                    <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M1.5 5l2.5 2.5 5-5" />
                    </svg>
                  )}
                </div>
                <span className="text-[11px] text-slate-500">New only</span>
              </label>
            )}
            <label className="flex cursor-pointer items-center gap-1.5 select-none">
              <div
                role="checkbox"
                aria-checked={showLowRelevance}
                tabIndex={0}
                onClick={() => setShowLowRelevance((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setShowLowRelevance((v) => !v)
                  }
                }}
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 ${
                  showLowRelevance
                    ? 'border-indigo-500 bg-indigo-500 text-white'
                    : 'border-slate-300 bg-white'
                }`}
                aria-label="Show low-relevance results"
              >
                {showLowRelevance && (
                  <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M1.5 5l2.5 2.5 5-5" />
                  </svg>
                )}
              </div>
              <span className="text-[11px] text-slate-500">Show low-relevance</span>
            </label>
            {totalPages > 1 && (
              <span className="text-[11px] text-slate-400">
                Page {page} of {totalPages}
              </span>
            )}
          </div>
        </div>

        {/* Cached notice — shown when results were served from same-day cache */}
        {lastSearchCached && isSearchComplete && (
          <p className="mt-1 text-[11px] text-slate-400 italic">
            Showing saved results from earlier today
          </p>
        )}

        {/* Inline progress indicator — visible while the search is still running */}
        {isSearchRunning && statusQuery.data && statusQuery.data.total_adapters > 0 && (
          <p
            aria-live="polite"
            aria-atomic="true"
            className="mt-1 text-[11px] text-slate-400"
          >
            Searching… {statusQuery.data.completed_adapters}/{statusQuery.data.total_adapters} boards
          </p>
        )}
      </div>

      {/* Job list */}
      <ul className="flex flex-col gap-0 divide-y divide-slate-50" role="list" aria-label="Job listings">
        {displayedJobs.map((job) => (
          <li key={job.id} className="px-3 py-2.5">
            <JobCard
              job={job}
              onShowDetail={() => setSelectedJob(job)}
              isSelected={selectedJob?.id === job.id}
              isNew={newIds.has(job.id)}
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
