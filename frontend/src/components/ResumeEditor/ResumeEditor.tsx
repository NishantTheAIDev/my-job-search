import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApplication, rejectApplication } from '../../api/applications'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { DiffView } from './DiffView'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import type { DiffHunk } from '../../types'

export function ResumeEditor() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const setShowApproval = useJobSearchStore((s) => s.setShowApproval)
  const queryClient = useQueryClient()

  const [showRejectConfirm, setShowRejectConfirm] = useState(false)

  const appQuery = useQuery({
    queryKey: ['application', activeApplicationId],
    queryFn: () => getApplication(activeApplicationId!),
    enabled: !!activeApplicationId,
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectApplication(activeApplicationId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setActiveApplication(null)
      setShowApproval(false)
    },
  })

  // Warn before close if pending
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

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30 bg-black/30"
        aria-hidden="true"
        onClick={handleClose}
      />

      {/* Slide-over panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Application review"
        className="fixed inset-y-0 right-0 z-40 flex w-full max-w-2xl flex-col bg-white shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Review Application</h2>
          <button
            onClick={handleClose}
            aria-label="Close application review panel"
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {appQuery.isLoading && <LoadingSpinner label="Loading application..." />}

          {appQuery.isError && (
            <ErrorBanner
              message="Could not load application details."
              onRetry={() => appQuery.refetch()}
            />
          )}

          {appQuery.data && (
            <div className="flex flex-col gap-6">
              {appQuery.data.tailoring_failed && (
                <div
                  role="alert"
                  className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800"
                >
                  Resume tailoring encountered issues. Review carefully before approving.
                </div>
              )}

              {/* Resume diff */}
              <section aria-labelledby="diff-heading">
                <h3 id="diff-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  Tailored Resume Changes
                </h3>
                <DiffView hunks={diffHunks} />
              </section>

              {/* Cover letter */}
              <section aria-labelledby="cover-letter-heading">
                <h3 id="cover-letter-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  Cover Letter
                </h3>
                <textarea
                  readOnly
                  value={appQuery.data.cover_letter_text}
                  rows={10}
                  aria-label="Cover letter text (read only)"
                  className="w-full resize-none rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-sm text-gray-800 focus:outline-none"
                />
              </section>
            </div>
          )}
        </div>

        {/* Footer actions */}
        {appQuery.data && isPending && (
          <div className="border-t border-gray-200 px-6 py-4">
            {showRejectConfirm ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-gray-700">
                  Are you sure you want to reject this application? This cannot be undone.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => rejectMutation.mutate()}
                    disabled={rejectMutation.isPending}
                    aria-busy={rejectMutation.isPending}
                    className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50"
                  >
                    {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Reject'}
                  </button>
                  <button
                    onClick={() => setShowRejectConfirm(false)}
                    disabled={rejectMutation.isPending}
                    className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2"
                  >
                    Cancel
                  </button>
                </div>
                {rejectMutation.isError && (
                  <p role="alert" className="text-xs text-red-600">
                    Failed to reject application. Please try again.
                  </p>
                )}
              </div>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setShowApproval(true)
                  }}
                  className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                >
                  Review &amp; Approve
                </button>
                <button
                  onClick={() => setShowRejectConfirm(true)}
                  className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        )}

        {appQuery.data && !isPending && (
          <div className="border-t border-gray-200 px-6 py-4">
            <p className="text-center text-sm capitalize text-gray-500">
              Application status:{' '}
              <span className="font-medium text-gray-800">{appQuery.data.status}</span>
            </p>
          </div>
        )}
      </aside>
    </>
  )
}
