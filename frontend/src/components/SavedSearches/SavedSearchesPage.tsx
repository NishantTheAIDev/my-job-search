import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import {
  deleteSavedSearch,
  listSavedSearches,
  runSavedSearch,
} from '../../api/savedSearches'
import { Logo } from '../shared/Logo'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { EmptyState } from '../shared/EmptyState'
import { formatPostedDate } from '../../lib/date'
import type { SavedSearch } from '../../types'

function summarizeCriteria(s: SavedSearch): string {
  const parts: string[] = [`"${s.criteria.query}"`]
  if (s.criteria.location) parts.push(s.criteria.location)
  if (s.criteria.remote_only) parts.push('Remote only')
  return parts.join(' · ')
}

export function SavedSearchesPage() {
  const setShowSavedSearches = useJobSearchStore((s) => s.setShowSavedSearches)
  const setActiveSearchJob = useJobSearchStore((s) => s.setActiveSearchJob)
  const setActiveSavedSearchId = useJobSearchStore((s) => s.setActiveSavedSearchId)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)
  const setSelectedSources = useJobSearchStore((s) => s.setSelectedSources)
  const setSelectedCompanies = useJobSearchStore((s) => s.setSelectedCompanies)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const queryClient = useQueryClient()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['savedSearches'],
    queryFn: listSavedSearches,
    staleTime: 30_000,
  })

  const runMutation = useMutation({
    mutationFn: (saved: SavedSearch) => runSavedSearch(saved.id),
    onSuccess: (res, saved) => {
      // Navigate into the results view; ResultsList will poll + diff for "new".
      setCriteria(saved.criteria)
      setActiveSavedSearchId(saved.id)
      setActiveSearchJob(res.search_job_id)
      setSelectedJob(null)
      setSelectedSources([])
      setSelectedCompanies([])
      setShowSavedSearches(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSavedSearch(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })

  function handleBack() {
    setShowSavedSearches(false)
  }

  const runningId = runMutation.isPending ? runMutation.variables?.id : null

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Top nav — mirrors SavedApplicationsPage header */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
        <div className="hidden shrink-0 md:block">
          <Logo />
        </div>
        <div className="flex min-w-0 flex-1 items-center">
          <div className="flex min-w-0 flex-col">
            <span className="text-[15px] font-semibold leading-tight text-slate-900">Saved Searches</span>
            {data && (
              <span className="text-[11px] text-slate-400">
                {data.length} {data.length === 1 ? 'search' : 'searches'}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={handleBack}
          aria-label={activeSearchJobId ? 'Back to results' : 'Back to home'}
          className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {activeSearchJobId ? 'Back to results' : 'Back to home'}
        </button>
        <button
          onClick={handleBack}
          aria-label={activeSearchJobId ? 'Back to results' : 'Back to home'}
          className="flex shrink-0 items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:hidden"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
        </button>
      </header>

      {/* Page body */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
          {isLoading && <LoadingSpinner label="Loading saved searches..." size="lg" />}

          {isError && (
            <ErrorBanner
              message="Could not load saved searches. Please check your connection and try again."
              onRetry={() => refetch()}
            />
          )}

          {!isLoading && !isError && data?.length === 0 && (
            <EmptyState
              title="No saved searches yet"
              description="Run a search, then click 'Save search' in the results header to save it here and re-run it any time."
              icon={
                <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
                </svg>
              }
            />
          )}

          {!isLoading && !isError && data && data.length > 0 && (
            <ul
              className="flex flex-col divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
              aria-label="Saved searches list"
            >
              {data.map((item) => {
                const lastRun = formatPostedDate(item.last_run_at)
                return (
                  <li key={item.id} className="flex items-center gap-4 px-5 py-4">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[14px] font-semibold text-slate-900">{item.name}</p>
                      <p className="mt-0.5 truncate text-[12px] text-slate-500">
                        {summarizeCriteria(item)}
                      </p>
                      <p className="mt-1 text-[11px] text-slate-400">
                        {lastRun ? `Last run ${lastRun}` : 'Not run yet'}
                      </p>
                    </div>

                    <button
                      onClick={() => runMutation.mutate(item)}
                      disabled={runMutation.isPending}
                      aria-label={`Run saved search: ${item.name}`}
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-[12px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {runningId === item.id ? 'Running…' : 'Run'}
                    </button>

                    <button
                      onClick={() => {
                        if (window.confirm(`Delete saved search "${item.name}"?`)) {
                          deleteMutation.mutate(item.id)
                        }
                      }}
                      aria-label={`Delete saved search: ${item.name}`}
                      className="inline-flex shrink-0 items-center justify-center rounded-lg border border-slate-200 p-1.5 text-slate-400 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                      </svg>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}

          {runMutation.isError && (
            <p role="alert" className="mt-3 text-[13px] text-red-500">
              Could not run that search. Please try again.
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
