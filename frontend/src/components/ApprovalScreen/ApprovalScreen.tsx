import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getApplicationByJob,
  approveApplication,
  getResumeDownloadUrl,
  getCoverLetterDownloadUrl,
  RENDERCV_THEMES,
  DEFAULT_RENDERCV_THEME,
  PREPARE_POLL_MAX_RETRIES,
} from '../../api/applications'
import { getJob } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ConfirmationModal } from './ConfirmationModal'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { PrepProgress } from '../shared/PrepProgress'
import { DownloadMenu } from '../shared/DownloadMenu'
import { ScoreBadge } from '../ResultsList/ScoreBadge'
import type { AxiosError } from 'axios'

function SectionCard({
  children,
  id,
  label,
  action,
}: {
  children: React.ReactNode
  id?: string
  label?: string
  action?: React.ReactNode
}) {
  return (
    <section
      aria-labelledby={id}
      className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      {(label || action) && (
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3">
          <h2 id={id} className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
            {label}
          </h2>
          {action}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function ApprovalScreen() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const setShowApproval = useJobSearchStore((s) => s.setShowApproval)
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const queryClient = useQueryClient()

  const [showModal, setShowModal] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // activeApplicationId holds the job posting id; resolve the application the
  // prepare pipeline created for it (polling past the interim 404s).
  const appQuery = useQuery({
    queryKey: ['application', activeApplicationId],
    queryFn: () => getApplicationByJob(activeApplicationId!),
    enabled: !!activeApplicationId,
    retry: (failureCount, error) =>
      (error as AxiosError)?.response?.status === 404 && failureCount < PREPARE_POLL_MAX_RETRIES,
    retryDelay: 2000,
    refetchInterval: (query) => (query.state.data?.status === 'preparing' ? 2000 : false),
  })

  const jobQuery = useQuery({
    queryKey: ['job', appQuery.data?.job_posting_id],
    queryFn: () => getJob(appQuery.data!.job_posting_id),
    enabled: !!appQuery.data?.job_posting_id,
  })

  const approveMutation = useMutation({
    mutationFn: () => approveApplication(appQuery.data!.id),
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
  const isPreparing = application?.status === 'preparing'
  const prepFailed = application?.status === 'prep_failed'
  const isReady = !!application && !isPreparing && !prepFailed

  return (
    <div className="fixed inset-0 z-40 overflow-y-auto bg-slate-50 animate-fade-in">
      <div className="mx-auto max-w-2xl px-5 py-8">

        {/* Back link */}
        <button
          onClick={handleBack}
          aria-label="Back to application review"
          className="mb-7 inline-flex items-center gap-1.5 text-[13px] font-medium text-indigo-600 transition hover:text-indigo-800 focus:outline-none focus:underline"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M9.78 4.22a.75.75 0 0 1 0 1.06L7.06 8l2.72 2.72a.75.75 0 1 1-1.06 1.06L5.47 8.53a.75.75 0 0 1 0-1.06l3.25-3.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
          </svg>
          Back to review
        </button>

        <h1 className="mb-6 text-xl font-bold tracking-tight text-slate-900">
          Review &amp; Approve Application
        </h1>

        {/* Success banner */}
        {successMessage && (
          <div
            role="status"
            aria-live="polite"
            className="mb-6 flex items-center justify-between gap-4 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 text-white" aria-hidden="true">
                <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" />
                </svg>
              </span>
              <p className="text-[14px] font-semibold text-emerald-800">{successMessage}</p>
            </div>
            <button
              onClick={handleDone}
              className="shrink-0 rounded-lg bg-emerald-600 px-4 py-2 text-[12px] font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            >
              Done
            </button>
          </div>
        )}

        {isLoading && <LoadingSpinner label="Loading application details..." size="lg" />}

        {appQuery.isError && (
          <ErrorBanner message="Could not load application details." onRetry={() => appQuery.refetch()} />
        )}

        {isReady && jobQuery.isError && (
          <ErrorBanner message="Could not load the job details." onRetry={() => jobQuery.refetch()} />
        )}

        {isPreparing && <PrepProgress stage={application?.prep_stage ?? ''} />}

        {prepFailed && (
          <ErrorBanner
            message={
              application?.prep_error
                ? `Preparation failed: ${application.prep_error}`
                : 'Preparing this application failed. Please try again.'
            }
          />
        )}

        {isReady && application && job && (
          <div className="flex flex-col gap-5">

            {/* Job summary */}
            <SectionCard id="job-summary-heading" label="Job Summary">
              <div className="flex items-start gap-4">
                <ScoreBadge score={application.match_score} />
                <div className="flex-1 min-w-0">
                  <p className="text-[15px] font-semibold text-slate-900">{job.title}</p>
                  {job.company && (
                    <p className="mt-0.5 text-[13px] font-medium text-slate-500">{job.company}</p>
                  )}
                  {job.location && (
                    <p className="mt-1 flex items-center gap-1 text-[12px] text-slate-400">
                      <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                        <path fillRule="evenodd" d="M8 1.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM2 6a6 6 0 1 1 10.89 3.477l3.817 3.816a.75.75 0 0 1-1.06 1.061l-3.816-3.816A6 6 0 0 1 2 6Z" clipRule="evenodd" />
                      </svg>
                      {job.location}
                    </p>
                  )}
                  {application.match_rationale && (
                    <div className="mt-3 rounded-lg bg-indigo-50 px-3 py-2.5">
                      <p className="text-[12px] leading-relaxed text-indigo-800">
                        <span className="font-semibold text-indigo-900">Match rationale: </span>
                        {application.match_rationale}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </SectionCard>

            {/* Tailored resume */}
            <SectionCard
              id="resume-heading"
              label="Tailored Resume"
              action={
                <DownloadMenu
                  label="Download resume"
                  themes={RENDERCV_THEMES}
                  defaultTheme={DEFAULT_RENDERCV_THEME}
                  urlFor={(format, theme) =>
                    getResumeDownloadUrl(application.id, format, theme)
                  }
                />
              }
            >
              <div
                className="max-h-64 overflow-y-auto"
                tabIndex={0}
                aria-label="Tailored resume text (scrollable)"
              >
                <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-slate-700">
                  {application.tailored_resume_text}
                </pre>
              </div>
            </SectionCard>

            {/* Cover letter */}
            <SectionCard
              id="cover-letter-heading-approval"
              label="Cover Letter"
              action={
                <DownloadMenu
                  label="Download cover letter"
                  urlFor={(format) => getCoverLetterDownloadUrl(application.id, format)}
                />
              }
            >
              <div
                className="max-h-64 overflow-y-auto"
                tabIndex={0}
                aria-label="Cover letter text (scrollable)"
              >
                <pre className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-slate-700">
                  {application.cover_letter_text}
                </pre>
              </div>
            </SectionCard>

            {/* Action buttons */}
            {!successMessage && (
              <div className="flex items-center gap-3 pt-1">
                <button
                  onClick={handleApproveAndSubmit}
                  disabled={approveMutation.isPending}
                  aria-busy={approveMutation.isPending}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-[14px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                    <path d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" />
                  </svg>
                  Approve &amp; Submit
                </button>
                <button
                  onClick={handleBack}
                  className="rounded-xl border border-slate-200 px-6 py-3 text-[14px] font-medium text-slate-600 transition hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
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
