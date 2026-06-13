import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import {
  getApplicationByJob,
  rejectApplication,
  getResumeDownloadUrl,
  getCoverLetterDownloadUrl,
  PREPARE_POLL_MAX_RETRIES,
} from '../../api/applications'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { DiffView } from './DiffView'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { PrepProgress } from '../shared/PrepProgress'
import { DownloadMenu } from '../shared/DownloadMenu'
import type { DiffHunk } from '../../types'

const STATUS_LABELS: Record<string, string> = {
  preparing: 'Preparing',
  prep_failed: 'Failed',
  pending: 'Pending review',
  approved: 'Approved',
  submitted: 'Submitted',
  rejected: 'Rejected',
  failed: 'Failed',
}

const STATUS_STYLES: Record<string, string> = {
  preparing: 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200',
  prep_failed: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
  pending: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  approved: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  submitted: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  rejected: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  failed: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
}

export function ResumeEditor() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const setShowApproval = useJobSearchStore((s) => s.setShowApproval)
  const queryClient = useQueryClient()

  const [showRejectConfirm, setShowRejectConfirm] = useState(false)
  const [activeTab, setActiveTab] = useState<'diff' | 'cover'>('diff')

  // activeApplicationId holds the job posting id. The prepare pipeline creates
  // the Application row up front in the `preparing` state, then advances
  // prep_stage as it runs — so poll while preparing and render real progress.
  // A short 404 retry covers the brief gap before the background task inserts
  // the row.
  const appQuery = useQuery({
    queryKey: ['application', activeApplicationId],
    queryFn: () => getApplicationByJob(activeApplicationId!),
    enabled: !!activeApplicationId,
    retry: (failureCount, error) =>
      (error as AxiosError)?.response?.status === 404 && failureCount < PREPARE_POLL_MAX_RETRIES,
    retryDelay: 2000,
    refetchInterval: (query) => (query.state.data?.status === 'preparing' ? 2000 : false),
  })

  const isPreparing = appQuery.data?.status === 'preparing'
  const prepFailed = appQuery.data?.status === 'prep_failed'

  const rejectMutation = useMutation({
    mutationFn: () => rejectApplication(appQuery.data!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setActiveApplication(null)
      setShowApproval(false)
    },
  })

  useEffect(() => {
    const isPending = appQuery.data?.status === 'pending'
    if (!isPending) return
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [appQuery.data?.status])

  if (!activeApplicationId) return null

  function handleClose() {
    if (appQuery.data?.status === 'pending') {
      const confirmed = window.confirm(
        'This application is still pending. Are you sure you want to close it without approving or rejecting?'
      )
      if (!confirmed) return
    }
    setActiveApplication(null)
    setShowApproval(false)
  }

  let diffHunks: DiffHunk[] = []
  if (appQuery.data?.resume_diff_json) {
    try {
      diffHunks = JSON.parse(appQuery.data.resume_diff_json) as DiffHunk[]
    } catch {
      diffHunks = []
    }
  }

  const isPending = appQuery.data?.status === 'pending'
  const isReady = !!appQuery.data && !isPreparing && !prepFailed
  const status = appQuery.data?.status ?? 'pending'
  const appId = appQuery.data?.id
  // Downloads become available as soon as the underlying content exists — the
  // tailored resume is persisted right after the tailoring stage, the cover
  // letter once drafting finishes — even while the application is still
  // `preparing`.
  const canDownloadResume = !!appId && !!appQuery.data?.tailored_resume_text
  const canDownloadCoverLetter = !!appId && !!appQuery.data?.cover_letter_text

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-[2px] animate-fade-in"
        aria-hidden="true"
        onClick={handleClose}
      />

      {/* Slide-over panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Application review"
        className="animate-slide-in-right fixed inset-y-0 right-0 z-40 flex w-full max-w-[640px] flex-col bg-white shadow-2xl"
      >
        {/* Header: title row */}
        <div className="flex items-center justify-between border-b border-slate-100 bg-white px-6 py-4">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-[15px] font-semibold text-slate-900 truncate">Review Application</h2>
            {appQuery.data && (
              <span className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${STATUS_STYLES[status] ?? STATUS_STYLES['pending']}`}>
                {STATUS_LABELS[status] ?? status}
              </span>
            )}
          </div>
          <button
            onClick={handleClose}
            aria-label="Close application review panel"
            className="ml-3 shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Download toolbar — shown once at least one download is available */}
        {(canDownloadResume || canDownloadCoverLetter) && (
          <div className="flex items-center gap-2 border-b border-slate-100 bg-slate-50 px-6 py-2.5">
            <span className="mr-1 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
              Download
            </span>
            {canDownloadResume && (
              <DownloadMenu
                label="Resume"
                urlFor={(format) => getResumeDownloadUrl(appId!, format)}
              />
            )}
            {canDownloadCoverLetter && (
              <DownloadMenu
                label="Cover letter"
                urlFor={(format) => getCoverLetterDownloadUrl(appId!, format)}
              />
            )}
          </div>
        )}

        {/* Tab bar */}
        {isReady && (
          <div className="flex border-b border-slate-100 bg-white px-6" role="tablist" aria-label="Application sections">
            {(['diff', 'cover'] as const).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`-mb-px border-b-2 px-1 py-3 text-[13px] font-medium transition mr-5 last:mr-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                  activeTab === tab
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                {tab === 'diff' ? 'Resume Changes' : 'Cover Letter'}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {appQuery.isLoading && <LoadingSpinner label="Loading application…" />}

          {appQuery.isError && (
            <ErrorBanner
              message="Could not load application details."
              onRetry={() => appQuery.refetch()}
            />
          )}

          {isPreparing && <PrepProgress stage={appQuery.data?.prep_stage ?? ''} />}

          {prepFailed && (
            <ErrorBanner
              message={
                appQuery.data?.prep_error
                  ? `Preparation failed: ${appQuery.data.prep_error}`
                  : 'Preparing this application failed. Please try again.'
              }
            />
          )}

          {isReady && (
            <div className="flex flex-col gap-5">
              {appQuery.data!.tailoring_failed && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5"
                >
                  <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z" clipRule="evenodd" />
                  </svg>
                  <p className="text-[12px] font-medium text-amber-800">
                    Resume tailoring encountered issues. Review carefully before approving.
                  </p>
                </div>
              )}

              {/* Tab content */}
              <div role="tabpanel" aria-label={activeTab === 'diff' ? 'Resume Changes' : 'Cover Letter'}>
                {activeTab === 'diff' ? (
                  <section aria-labelledby="diff-heading">
                    <h3 id="diff-heading" className="sr-only">Tailored Resume Changes</h3>
                    <DiffView hunks={diffHunks} />
                  </section>
                ) : (
                  <section aria-labelledby="cover-letter-heading">
                    <h3 id="cover-letter-heading" className="sr-only">Cover Letter</h3>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <textarea
                        readOnly
                        value={appQuery.data!.cover_letter_text}
                        rows={16}
                        aria-label="Cover letter text (read only)"
                        className="w-full resize-none bg-transparent text-[13px] leading-relaxed text-slate-700 focus:outline-none"
                      />
                    </div>
                  </section>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {appQuery.data && isPending && (
          <div className="border-t border-slate-100 bg-white px-6 py-4">
            {showRejectConfirm ? (
              <div className="space-y-3">
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3.5">
                  <p className="text-[13px] font-medium text-rose-800">
                    Reject this application? This cannot be undone.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => rejectMutation.mutate()}
                    disabled={rejectMutation.isPending}
                    aria-busy={rejectMutation.isPending}
                    className="rounded-lg bg-rose-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-2 disabled:opacity-50"
                  >
                    {rejectMutation.isPending ? 'Rejecting…' : 'Yes, Reject'}
                  </button>
                  <button
                    onClick={() => setShowRejectConfirm(false)}
                    disabled={rejectMutation.isPending}
                    className="rounded-lg border border-slate-200 px-4 py-2 text-[13px] font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
                  >
                    Cancel
                  </button>
                </div>
                {rejectMutation.isError && (
                  <p role="alert" className="text-[11px] text-red-500">
                    Failed to reject application. Please try again.
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowApproval(true)}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                    <path d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" />
                  </svg>
                  Review &amp; Approve
                </button>
                <button
                  onClick={() => setShowRejectConfirm(true)}
                  className="rounded-lg border border-rose-200 px-4 py-2.5 text-[13px] font-medium text-rose-600 transition hover:bg-rose-50 hover:border-rose-300 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        )}

        {appQuery.data && !isPending && (
          <div className="border-t border-slate-100 bg-slate-50 px-6 py-3">
            <p className="text-center text-[12px] text-slate-500">
              Application status:{' '}
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${STATUS_STYLES[status] ?? STATUS_STYLES['pending']}`}>
                {STATUS_LABELS[status] ?? status}
              </span>
            </p>
          </div>
        )}
      </aside>
    </>
  )
}
