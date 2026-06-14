import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { listSavedApplications } from '../../api/applications'
import { Logo } from '../shared/Logo'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { EmptyState } from '../shared/EmptyState'
import { ScoreBadge } from '../ResultsList/ScoreBadge'
import { SavedApplicationDetail } from './SavedApplicationDetail'
import { formatPostedDate } from '../../lib/date'

export function SavedApplicationsPage() {
  const setShowSavedApplications = useJobSearchStore((s) => s.setShowSavedApplications)
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)

  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['applications', 'saved'],
    queryFn: listSavedApplications,
    staleTime: 30_000,
  })

  function handleBack() {
    setShowSavedApplications(false)
  }

  // When a row is selected, show the detail panel instead of the list
  if (selectedId) {
    return (
      <div className="flex h-full flex-col bg-slate-50">
        {/* Reuse the same header */}
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
          <div className="hidden shrink-0 md:block">
            <Logo />
          </div>
          <div className="flex min-w-0 flex-1 items-center">
            <span className="text-[15px] font-semibold leading-tight text-slate-900">
              Saved Applications
            </span>
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

        <main className="flex-1 overflow-hidden">
          <div className="mx-auto max-w-2xl h-full px-0 sm:px-0">
            <SavedApplicationDetail
              applicationId={selectedId}
              onClose={() => setSelectedId(null)}
            />
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Top nav — mirrors InsightsPage header */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
        <div className="hidden shrink-0 md:block">
          <Logo />
        </div>

        <div className="flex min-w-0 flex-1 items-center">
          <div className="flex min-w-0 flex-col">
            <span className="text-[15px] font-semibold leading-tight text-slate-900">Saved Applications</span>
            {data && (
              <span className="text-[11px] text-slate-400">
                {data.length} {data.length === 1 ? 'application' : 'applications'}
              </span>
            )}
          </div>
        </div>

        {/* Back button — desktop */}
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

        {/* Back button — mobile icon only */}
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

          {isLoading && (
            <LoadingSpinner label="Loading saved applications..." size="lg" />
          )}

          {isError && (
            <ErrorBanner
              message="Could not load saved applications. Please check your connection and try again."
              onRetry={() => refetch()}
            />
          )}

          {!isLoading && !isError && data?.length === 0 && (
            <EmptyState
              title="No saved applications yet"
              description="Use 'Tailor from JD' or click 'Approve & Save' on any prepared application to save it here."
              icon={
                <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
                </svg>
              }
            />
          )}

          {!isLoading && !isError && data && data.length > 0 && (
            <ul
              className="flex flex-col divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
              aria-label="Saved applications list"
            >
              {data.map((item) => {
                const savedDate = formatPostedDate(item.saved_at)
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => setSelectedId(item.id)}
                      aria-label={`View saved application: ${item.job_title}${item.company ? ` at ${item.company}` : ''}`}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-slate-50 focus:outline-none focus-visible:bg-indigo-50"
                    >
                      <ScoreBadge score={item.match_score} size="sm" />

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[14px] font-semibold text-slate-900">
                          {item.job_title}
                        </p>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                          {item.company && (
                            <span className="text-[12px] font-medium text-slate-500">{item.company}</span>
                          )}
                          {item.company && item.location && (
                            <span className="text-[12px] text-slate-300" aria-hidden="true">·</span>
                          )}
                          {item.location && (
                            <span className="text-[12px] text-slate-400">{item.location}</span>
                          )}
                        </div>
                        {savedDate && (
                          <p className="mt-1 text-[11px] text-slate-400">
                            Saved {savedDate}
                          </p>
                        )}
                      </div>

                      {/* Chevron */}
                      <svg className="h-4 w-4 shrink-0 text-slate-300" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                        <path fillRule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </main>
    </div>
  )
}
