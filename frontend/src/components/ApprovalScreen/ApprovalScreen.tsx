import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApplication, approveApplication } from '../../api/applications'
import { getJob } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ConfirmationModal } from './ConfirmationModal'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { ScoreBadge } from '../ResultsList/ScoreBadge'
import type { AxiosError } from 'axios'

export function ApprovalScreen() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const setShowApproval = useJobSearchStore((s) => s.setShowApproval)
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const queryClient = useQueryClient()

  const [showModal, setShowModal] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const appQuery = useQuery({
    queryKey: ['application', activeApplicationId],
    queryFn: () => getApplication(activeApplicationId!),
    enabled: !!activeApplicationId,
  })

  const jobQuery = useQuery({
    queryKey: ['job', appQuery.data?.job_posting_id],
    queryFn: () => getJob(appQuery.data!.job_posting_id),
    enabled: !!appQuery.data?.job_posting_id,
  })

  const approveMutation = useMutation({
    mutationFn: () => approveApplication(activeApplicationId!),
    onSuccess: (data) => {
      const company = jobQuery.data?.company ?? 'the company'
      setSuccessMessage(`Application submitted to ${company}!`)
      setShowModal(false)
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      queryClient.setQueryData(['application', activeApplicationId], data)
    },
    onError: (err) => {
      const axiosErr = err as AxiosError<{ detail?: string }>
      if (axiosErr.response?.status === 409) {
        setSubmitError(
          axiosErr.response.data?.detail ?? 'Application was already submitted or is in a conflicting state.'
        )
      } else {
        setSubmitError('Failed to submit application. Please try again.')
      }
    },
  })

  function handleBack() {
    setShowApproval(false)
  }

  function handleApproveAndSubmit() {
    setSubmitError(null)
    setShowModal(true)
  }

  function handleConfirm() {
    approveMutation.mutate()
  }

  function handleCancel() {
    setShowModal(false)
    setSubmitError(null)
  }

  function handleDone() {
    setActiveApplication(null)
    setShowApproval(false)
  }

  const isLoading = appQuery.isLoading || jobQuery.isLoading
  const application = appQuery.data
  const job = jobQuery.data

  return (
    <div className="fixed inset-0 z-40 overflow-y-auto bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Back button */}
        <button
          onClick={handleBack}
          aria-label="Back to application review"
          className="mb-6 flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700 focus:outline-none focus:underline"
        >
          <span aria-hidden="true">&larr;</span> Back to review
        </button>

        <h1 className="mb-6 text-2xl font-bold text-gray-900">Review &amp; Approve Application</h1>

        {/* Success banner */}
        {successMessage && (
          <div
            role="status"
            aria-live="polite"
            className="mb-6 flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-5 py-4"
          >
            <p className="font-medium text-green-800">{successMessage}</p>
            <button
              onClick={handleDone}
              className="ml-4 rounded-md bg-green-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-green-800 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
            >
              Done
            </button>
          </div>
        )}

        {isLoading && <LoadingSpinner label="Loading application details..." size="lg" />}

        {appQuery.isError && (
          <ErrorBanner message="Could not load application details." onRetry={() => appQuery.refetch()} />
        )}

        {application && job && (
          <div className="flex flex-col gap-6">
            {/* Job summary card */}
            <section
              aria-labelledby="job-summary-heading"
              className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
            >
              <h2 id="job-summary-heading" className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Job Summary
              </h2>
              <div className="flex items-start gap-4">
                <ScoreBadge score={application.match_score} />
                <div className="flex-1">
                  <p className="text-lg font-semibold text-gray-900">{job.title}</p>
                  {job.company && <p className="text-sm text-gray-600">{job.company}</p>}
                  {job.location && <p className="mt-1 text-sm text-gray-500">{job.location}</p>}
                  {application.match_rationale && (
                    <p className="mt-3 text-sm text-gray-700">
                      <span className="font-medium">Match rationale: </span>
                      {application.match_rationale}
                    </p>
                  )}
                </div>
              </div>
            </section>

            {/* Tailored resume */}
            <section aria-labelledby="resume-heading">
              <h2 id="resume-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Tailored Resume
              </h2>
              <div
                className="max-h-72 overflow-y-auto rounded-xl border border-gray-200 bg-white p-4 font-mono text-sm leading-relaxed text-gray-800 shadow-sm"
                tabIndex={0}
                aria-label="Tailored resume text (scrollable)"
              >
                <pre className="whitespace-pre-wrap break-words">{application.tailored_resume_text}</pre>
              </div>
            </section>

            {/* Cover letter */}
            <section aria-labelledby="cover-letter-heading-approval">
              <h2 id="cover-letter-heading-approval" className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Cover Letter
              </h2>
              <div
                className="max-h-72 overflow-y-auto rounded-xl border border-gray-200 bg-white p-4 text-sm leading-relaxed text-gray-800 shadow-sm"
                tabIndex={0}
                aria-label="Cover letter text (scrollable)"
              >
                <pre className="whitespace-pre-wrap break-words">{application.cover_letter_text}</pre>
              </div>
            </section>

            {/* Actions */}
            {!successMessage && (
              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleApproveAndSubmit}
                  disabled={approveMutation.isPending}
                  aria-busy={approveMutation.isPending}
                  className="rounded-md bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Approve &amp; Submit
                </button>
                <button
                  onClick={handleBack}
                  className="rounded-md border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2"
                >
                  Back
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Confirmation modal */}
      {showModal && job && (
        <ConfirmationModal
          company={job.company}
          title={job.title}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          isSubmitting={approveMutation.isPending}
          error={submitError}
        />
      )}
    </div>
  )
}
