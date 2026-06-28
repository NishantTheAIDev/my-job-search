import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import {
  getApplicationByJob,
  rejectApplication,
  saveApplication,
  reviseApplication,
  editApplicationContent,
  revertApplicationContent,
  cancelApplication,
  getResumeDownloadUrl,
  getCoverLetterDownloadUrl,
  RENDERCV_THEMES,
  DEFAULT_RENDERCV_THEME,
  PREPARE_POLL_MAX_RETRIES,
} from '../../api/applications'
import type { ReviseTarget, RevertTo } from '../../api/applications'
import { getJob } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { DiffView } from '../ResumeEditor/DiffView'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { PrepProgress } from '../shared/PrepProgress'
import { DownloadMenu } from '../shared/DownloadMenu'
import { ScoreBadge } from '../ResultsList/ScoreBadge'
import { ConfirmationModal } from '../shared/ConfirmationModal'
import type { DiffHunk } from '../../types'

// ── Status display helpers ───────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  preparing: 'Preparing',
  prep_failed: 'Failed',
  pending: 'Pending review',
  submitted: 'Submitted',
  rejected: 'Rejected',
  failed: 'Failed',
  saved: 'Saved',
  cancelled: 'Cancelled',
}

const STATUS_STYLES: Record<string, string> = {
  preparing: 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200',
  prep_failed: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
  pending: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  submitted: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  rejected: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  failed: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
  saved: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  cancelled: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
}

// ── Small shared UI pieces ───────────────────────────────────────────────────

function InlineSpinner() {
  return (
    <svg
      className="h-3.5 w-3.5 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

function SectionCard({
  children,
  headingId,
  label,
  action,
}: {
  children: React.ReactNode
  headingId?: string
  label?: string
  action?: React.ReactNode
}) {
  return (
    <section
      aria-labelledby={headingId}
      className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      {(label || action) && (
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3">
          {label && (
            <h2
              id={headingId}
              className="text-[11px] font-bold uppercase tracking-widest text-slate-400"
            >
              {label}
            </h2>
          )}
          {action}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

// ── Revert confirmation modal ────────────────────────────────────────────────

interface RevertModalProps {
  target: ReviseTarget
  to: RevertTo
  onConfirm: () => void
  onCancel: () => void
  isSubmitting: boolean
  error: string | null
}

function RevertModal({ target, to, onConfirm, onCancel, isSubmitting, error }: RevertModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    cancelRef.current?.focus()
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isSubmitting) onCancel()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isSubmitting, onCancel])

  const isResume = target === 'resume'
  const isAiDraft = to === 'ai_draft'

  const heading = isAiDraft
    ? `Undo your edits to the ${isResume ? 'resume' : 'cover letter'}?`
    : 'Revert to your original resume?'

  const description = isAiDraft
    ? `This will replace the current ${isResume ? 'resume' : 'cover letter'} with the AI-generated draft. Your manual edits will be lost. This cannot be undone.`
    : 'This will replace the current tailored resume with your original uploaded resume. All AI tailoring and manual edits will be lost. This cannot be undone.'

  const confirmLabel = isAiDraft ? 'Yes, undo my edits' : 'Yes, revert to original'

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-[2px] animate-fade-in"
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="revert-modal-title"
        aria-describedby="revert-modal-desc"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="animate-scale-in w-full max-w-md rounded-2xl bg-white p-6 shadow-[0_20px_40px_-8px_rgb(0_0_0_/_0.20)]">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-rose-100">
            <svg
              className="h-5 w-5 text-rose-600"
              viewBox="0 0 16 16"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"
                clipRule="evenodd"
              />
            </svg>
          </div>

          <h2 id="revert-modal-title" className="text-[16px] font-bold text-slate-900">
            {heading}
          </h2>
          <p id="revert-modal-desc" className="mt-1.5 text-[13px] leading-relaxed text-slate-600">
            {description}
          </p>

          {error && (
            <div
              role="alert"
              className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3.5"
            >
              <svg
                className="mt-0.5 h-4 w-4 shrink-0 text-red-500"
                viewBox="0 0 16 16"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-3.5a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3A.75.75 0 0 1 8 4.5ZM8 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-[12px] font-medium text-red-700">{error}</p>
            </div>
          )}

          <div className="mt-5 flex justify-end gap-2.5">
            <button
              ref={cancelRef}
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-lg border border-slate-200 px-4 py-2 text-[13px] font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isSubmitting}
              aria-busy={isSubmitting}
              className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <InlineSpinner />
                  Reverting…
                </>
              ) : (
                confirmLabel
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Revert button group ──────────────────────────────────────────────────────

interface RevertButtonGroupProps {
  tab: 'diff' | 'cover'
  isPending: boolean
  isAiDraftCurrent: boolean // true when live text already equals AI snapshot
  onRevert: (to: RevertTo) => void
  disabled: boolean
}

function RevertButtonGroup({
  tab,
  isPending,
  isAiDraftCurrent,
  onRevert,
  disabled,
}: RevertButtonGroupProps) {
  if (!isPending) return null

  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={() => onRevert('ai_draft')}
        disabled={disabled || isAiDraftCurrent}
        title={isAiDraftCurrent ? 'Already at the AI draft' : 'Undo your manual edits, restore AI draft'}
        aria-label={
          tab === 'diff'
            ? 'Undo my edits to resume (restore AI draft)'
            : 'Undo my edits to cover letter (restore AI draft)'
        }
        className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <svg className="h-3 w-3" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path
            fillRule="evenodd"
            d="M1.22 6.28a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L2.5 3.94V2.75a.75.75 0 0 0-1.5 0v3c0 .414.336.75.75.75H4.5a.75.75 0 0 0 0-1.5H3.28l-.01-.01L1.22 6.28Z"
            clipRule="evenodd"
          />
          <path d="M7.25 4.75a.75.75 0 0 1 .75-.75h5.25a.75.75 0 0 1 0 1.5H8a.75.75 0 0 1-.75-.75Zm-5.5 8a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H2.5a.75.75 0 0 1-.75-.75Zm3-4a.75.75 0 0 1 .75-.75h7.5a.75.75 0 0 1 0 1.5h-7.5a.75.75 0 0 1-.75-.75Z" />
        </svg>
        Undo my edits
      </button>

      {tab === 'diff' && (
        <button
          type="button"
          onClick={() => onRevert('original')}
          disabled={disabled}
          title="Discard all AI tailoring, restore your original uploaded resume"
          aria-label="Revert resume to original uploaded version"
          className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg className="h-3 w-3" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path
              fillRule="evenodd"
              d="M8 2.75a5.25 5.25 0 1 0 0 10.5 5.25 5.25 0 0 0 0-10.5ZM1.25 8a6.75 6.75 0 1 1 13.5 0 6.75 6.75 0 0 1-13.5 0Z"
              clipRule="evenodd"
            />
            <path d="M8 5.75a.75.75 0 0 1 .75.75v2.69l1.72-1.72a.75.75 0 1 1 1.06 1.06l-3 3a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 1 1 1.06-1.06l1.72 1.72V6.5A.75.75 0 0 1 8 5.75Z" />
          </svg>
          Revert to original
        </button>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export function ApplicationWorkspace() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const workspaceOrigin = useJobSearchStore((s) => s.workspaceOrigin)
  const queryClient = useQueryClient()

  // Tab
  const [activeTab, setActiveTab] = useState<'diff' | 'cover'>('diff')

  // Cache-busting version counter
  const [downloadVersion, setDownloadVersion] = useState(0)

  // Resume direct-edit state
  const [resumeEditMode, setResumeEditMode] = useState(false)
  const [resumeEditText, setResumeEditText] = useState('')

  // Cover letter direct-edit state
  const [coverEditMode, setCoverEditMode] = useState(false)
  const [coverEditText, setCoverEditText] = useState('')

  // Request-changes inputs
  const [resumeReviseInput, setResumeReviseInput] = useState('')
  const [coverReviseInput, setCoverReviseInput] = useState('')

  // Approve/save modal + outcome
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Reject inline confirm
  const [showRejectConfirm, setShowRejectConfirm] = useState(false)

  // Revert confirmation: { target, to } or null
  const [pendingRevert, setPendingRevert] = useState<{
    target: ReviseTarget
    to: RevertTo
  } | null>(null)
  const [revertError, setRevertError] = useState<string | null>(null)

  // ── Queries ──────────────────────────────────────────────────────────────

  const appQuery = useQuery({
    queryKey: ['application', activeApplicationId],
    queryFn: () => getApplicationByJob(activeApplicationId!),
    enabled: !!activeApplicationId,
    retry: (failureCount, error) =>
      (error as AxiosError)?.response?.status === 404 && failureCount < PREPARE_POLL_MAX_RETRIES,
    retryDelay: 2000,
    refetchInterval: (query) =>
      query.state.data?.status === 'preparing' ? 2000 : false,
  })

  const jobQuery = useQuery({
    queryKey: ['job', appQuery.data?.job_posting_id],
    queryFn: () => getJob(appQuery.data!.job_posting_id),
    enabled: !!appQuery.data?.job_posting_id,
  })

  const isPreparing = appQuery.data?.status === 'preparing'
  const prepFailed = appQuery.data?.status === 'prep_failed'
  const isPending = appQuery.data?.status === 'pending'
  const isReady = !!appQuery.data && !isPreparing && !prepFailed
  const status = appQuery.data?.status ?? 'pending'
  const appId = appQuery.data?.id
  const job = jobQuery.data

  const canDownloadResume = !!appId && !!appQuery.data?.tailored_resume_text
  const canDownloadCoverLetter = !!appId && !!appQuery.data?.cover_letter_text

  // ── Edit-buffer sync ─────────────────────────────────────────────────────

  const servedResumeText = appQuery.data?.tailored_resume_text ?? ''
  const servedCoverText = appQuery.data?.cover_letter_text ?? ''
  const prevResumeRef = useRef(servedResumeText)
  const prevCoverRef = useRef(servedCoverText)

  // Sync buffers when server text changes (e.g. after revise/edit/revert),
  // but don't clobber in-progress edits.
  useEffect(() => {
    if (servedResumeText !== prevResumeRef.current) {
      prevResumeRef.current = servedResumeText
      if (!resumeEditMode) setResumeEditText(servedResumeText)
    }
  }, [servedResumeText, resumeEditMode])

  useEffect(() => {
    if (servedCoverText !== prevCoverRef.current) {
      prevCoverRef.current = servedCoverText
      if (!coverEditMode) setCoverEditText(servedCoverText)
    }
  }, [servedCoverText, coverEditMode])

  // Seed buffers on first load
  useEffect(() => {
    if (appQuery.data && resumeEditText === '') setResumeEditText(appQuery.data.tailored_resume_text)
    if (appQuery.data && coverEditText === '') setCoverEditText(appQuery.data.cover_letter_text)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appQuery.data])

  // ── beforeunload guard ───────────────────────────────────────────────────

  useEffect(() => {
    if (!isPending) return
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isPending])

  // ── Mutations ────────────────────────────────────────────────────────────

  const rejectMutation = useMutation({
    mutationFn: () => rejectApplication(appQuery.data!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setActiveApplication(null)
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelApplication(appQuery.data!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      queryClient.invalidateQueries({ queryKey: ['applications', 'in-progress'] })
      setActiveApplication(null)
    },
    onError: (err) => {
      const axiosErr = err as AxiosError<{ detail?: string }>
      if (axiosErr.response?.status === 409) {
        // Preparation already finished — refetch so the workspace shows the
        // ready state instead of the now-stale preparing UI.
        appQuery.refetch()
      }
    },
  })

  const reviseMutation = useMutation({
    mutationFn: ({ target, instructions }: { target: ReviseTarget; instructions: string }) =>
      reviseApplication(appQuery.data!.id, target, instructions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', activeApplicationId] })
      setResumeReviseInput('')
      setCoverReviseInput('')
      setDownloadVersion((v) => v + 1)
    },
  })

  const editMutation = useMutation({
    mutationFn: ({ target, text }: { target: ReviseTarget; text: string }) =>
      editApplicationContent(appQuery.data!.id, target, text),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['application', activeApplicationId] })
      setDownloadVersion((v) => v + 1)
      if (variables.target === 'resume') {
        setResumeEditMode(false)
      } else {
        setCoverEditMode(false)
      }
    },
  })

  const saveMutation = useMutation({
    mutationFn: () => saveApplication(appQuery.data!.id),
    onSuccess: (data) => {
      const company = job?.company ?? 'the company'
      setSuccessMessage(`Application saved for ${company}!`)
      setShowSaveModal(false)
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      queryClient.invalidateQueries({ queryKey: ['applications', 'saved'] })
      queryClient.setQueryData(['application', activeApplicationId], data)
    },
    onError: (err) => {
      const axiosErr = err as AxiosError<{ detail?: string }>
      if (axiosErr.response?.status === 409) {
        setSaveError(
          axiosErr.response.data?.detail ??
            'Application is not in a pending state and cannot be saved.'
        )
      } else {
        setSaveError('Failed to save application. Please try again.')
      }
    },
  })

  const revertMutation = useMutation({
    mutationFn: ({ target, to }: { target: ReviseTarget; to: RevertTo }) =>
      revertApplicationContent(appQuery.data!.id, target, to),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', activeApplicationId] })
      setPendingRevert(null)
      setRevertError(null)
      setDownloadVersion((v) => v + 1)
    },
    onError: (err) => {
      const axiosErr = err as AxiosError<{ detail?: string }>
      setRevertError(
        axiosErr.response?.data?.detail ?? 'Revert failed. Please try again.'
      )
    },
  })

  // ── Helpers ──────────────────────────────────────────────────────────────

  if (!activeApplicationId) return null

  function versioned(url: string) {
    if (downloadVersion === 0) return url
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}v=${downloadVersion}`
  }

  function handleClose() {
    if (isPreparing) {
      const confirmed = window.confirm(
        "This application is still being prepared in the background. Leaving won't stop it — you can return to it from the 'In Progress' menu. Leave anyway?"
      )
      if (!confirmed) return
    } else if (isPending) {
      const confirmed = window.confirm(
        'This application is still pending. Are you sure you want to close without approving or rejecting?'
      )
      if (!confirmed) return
    }
    // workspaceOrigin is preserved in the store — App.tsx reads it to decide
    // whether to show LandingPage ('home') or ResultsView ('results') after
    // activeApplicationId is cleared.
    setActiveApplication(null)
  }

  let diffHunks: DiffHunk[] = []
  if (appQuery.data?.resume_diff_json) {
    try {
      diffHunks = JSON.parse(appQuery.data.resume_diff_json) as DiffHunk[]
    } catch {
      diffHunks = []
    }
  }

  const resumeRevising =
    reviseMutation.isPending && reviseMutation.variables?.target === 'resume'
  const coverRevising =
    reviseMutation.isPending && reviseMutation.variables?.target === 'cover_letter'
  const resumeSaving =
    editMutation.isPending && editMutation.variables?.target === 'resume'
  const coverSaving =
    editMutation.isPending && editMutation.variables?.target === 'cover_letter'

  const reviseError =
    reviseMutation.isError
      ? (reviseMutation.error as AxiosError<{ detail?: string }>)?.response?.data?.detail ??
        'Request failed. Please try again.'
      : null
  const editError =
    editMutation.isError
      ? (editMutation.error as AxiosError<{ detail?: string }>)?.response?.data?.detail ??
        'Save failed. Please try again.'
      : null

  // Revert "undo" disabled when live text already equals AI snapshot
  const resumeIsAtAiDraft =
    (appQuery.data?.tailored_resume_text ?? '') ===
    (appQuery.data?.ai_tailored_resume_text ?? '')
  const coverIsAtAiDraft =
    (appQuery.data?.cover_letter_text ?? '') ===
    (appQuery.data?.ai_cover_letter_text ?? '')

  const gaps = appQuery.data?.match_gaps ?? []

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-slate-50 animate-fade-in">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="shrink-0 flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-4 shadow-sm">
        <button
          onClick={handleClose}
          aria-label={workspaceOrigin === 'home' ? 'Close workspace and return to home' : 'Close workspace and return to results'}
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-indigo-600 transition hover:text-indigo-800 focus:outline-none focus:underline"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path
              fillRule="evenodd"
              d="M9.78 4.22a.75.75 0 0 1 0 1.06L7.06 8l2.72 2.72a.75.75 0 1 1-1.06 1.06L5.47 8.53a.75.75 0 0 1 0-1.06l3.25-3.25a.75.75 0 0 1 1.06 0Z"
              clipRule="evenodd"
            />
          </svg>
          Back
        </button>

        <div className="h-4 w-px bg-slate-200" aria-hidden="true" />

        <h1 className="min-w-0 flex-1 truncate text-[15px] font-semibold text-slate-900">
          {job ? `${job.title}${job.company ? ` — ${job.company}` : ''}` : 'Application Workspace'}
        </h1>

        {appQuery.data && (
          <span
            className={`shrink-0 inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
              STATUS_STYLES[status] ?? STATUS_STYLES['pending']
            }`}
          >
            {STATUS_LABELS[status] ?? status}
          </span>
        )}
      </header>

      {/* ── Main scrollable body ────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-5 py-6">

          {/* Loading / error / prep states */}
          {appQuery.isLoading && <LoadingSpinner label="Loading application…" size="lg" />}

          {appQuery.isError && (
            <ErrorBanner
              message="Could not load application details."
              onRetry={() => appQuery.refetch()}
            />
          )}

          {isPreparing && (
            <div className="flex flex-col gap-5">
              <PrepProgress stage={appQuery.data?.prep_stage ?? ''} />

              {/* Cancel preparation */}
              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={() => {
                    if (
                      window.confirm(
                        'Cancel preparing this application? Anything generated so far will be discarded.'
                      )
                    ) {
                      cancelMutation.mutate()
                    }
                  }}
                  disabled={cancelMutation.isPending}
                  aria-busy={cancelMutation.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-4 py-2 text-[13px] font-medium text-slate-600 transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {cancelMutation.isPending ? (
                    <>
                      <InlineSpinner />
                      Cancelling…
                    </>
                  ) : (
                    <>
                      <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                        <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z" />
                      </svg>
                      Cancel preparation
                    </>
                  )}
                </button>
              </div>

              {/* Show the job description while the pipeline runs so the user has
                  context to read instead of staring at a bare progress bar. */}
              {job?.description && (
                <SectionCard headingId="prep-jd-heading" label="Job Description">
                  <div
                    className="max-h-[28rem] overflow-y-auto"
                    tabIndex={0}
                    aria-label="Job description (scrollable)"
                  >
                    <p className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-slate-700">
                      {job.description}
                    </p>
                  </div>
                </SectionCard>
              )}
            </div>
          )}

          {prepFailed && (
            <ErrorBanner
              message={
                appQuery.data?.prep_error
                  ? `Preparation failed: ${appQuery.data.prep_error}`
                  : 'Preparing this application failed. Please try again.'
              }
            />
          )}

          {/* ── Ready content ─────────────────────────────────────────── */}
          {isReady && (
            <div className="flex flex-col gap-5">

              {/* Success banner */}
              {successMessage && (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-center justify-between gap-4 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 text-white"
                      aria-hidden="true"
                    >
                      <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" />
                      </svg>
                    </span>
                    <p className="text-[14px] font-semibold text-emerald-800">{successMessage}</p>
                  </div>
                  <button
                    onClick={() => setActiveApplication(null)}
                    className="shrink-0 rounded-lg bg-emerald-600 px-4 py-2 text-[12px] font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                  >
                    Done
                  </button>
                </div>
              )}

              {/* Tailoring-failed warning */}
              {appQuery.data!.tailoring_failed && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5"
                >
                  <svg
                    className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
                    viewBox="0 0 16 16"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <p className="text-[12px] font-medium text-amber-800">
                    Resume tailoring encountered issues. Review carefully before approving.
                  </p>
                </div>
              )}

              {/* ── Job summary card ──────────────────────────────────── */}
              {job && (
                <SectionCard headingId="job-summary-heading" label="Job Summary">
                  <div className="flex items-start gap-4">
                    <ScoreBadge score={appQuery.data!.match_score} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] font-semibold text-slate-900">{job.title}</p>
                      {job.company && (
                        <p className="mt-0.5 text-[13px] font-medium text-slate-500">
                          {job.company}
                        </p>
                      )}
                      {job.location && (
                        <p className="mt-1 flex items-center gap-1 text-[12px] text-slate-400">
                          <svg
                            className="h-3.5 w-3.5"
                            viewBox="0 0 16 16"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path
                              fillRule="evenodd"
                              d="M8 1.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM2 6a6 6 0 1 1 10.89 3.477l3.817 3.816a.75.75 0 0 1-1.06 1.061l-3.816-3.816A6 6 0 0 1 2 6Z"
                              clipRule="evenodd"
                            />
                          </svg>
                          {job.location}
                        </p>
                      )}
                      {appQuery.data!.match_rationale && (
                        <div className="mt-3 rounded-lg bg-indigo-50 px-3 py-2.5">
                          <p className="text-[12px] leading-relaxed text-indigo-800">
                            <span className="font-semibold text-indigo-900">Match rationale: </span>
                            {appQuery.data!.match_rationale}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </SectionCard>
              )}

              {/* Gaps to address */}
              {gaps.length > 0 && (
                <SectionCard headingId="gaps-heading" label="Gaps to Address">
                  <ul className="flex flex-col gap-2" aria-label="Match gaps list">
                    {gaps.map((gap, i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <span
                          className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-600"
                          aria-hidden="true"
                        >
                          <svg className="h-2.5 w-2.5" viewBox="0 0 16 16" fill="currentColor">
                            <path
                              fillRule="evenodd"
                              d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-3.5a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3A.75.75 0 0 1 8 4.5ZM8 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </span>
                        <span className="text-[13px] leading-relaxed text-slate-700">{gap}</span>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              )}

              {/* ── Download toolbar ──────────────────────────────────── */}
              {(canDownloadResume || canDownloadCoverLetter) && (
                <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <span className="mr-1 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                    Download
                  </span>
                  {canDownloadResume && (
                    <DownloadMenu
                      label="Resume"
                      themes={RENDERCV_THEMES}
                      defaultTheme={DEFAULT_RENDERCV_THEME}
                      urlFor={(format, theme) =>
                        versioned(getResumeDownloadUrl(appId!, format, theme))
                      }
                    />
                  )}
                  {canDownloadCoverLetter && (
                    <DownloadMenu
                      label="Cover letter"
                      urlFor={(format) =>
                        versioned(getCoverLetterDownloadUrl(appId!, format))
                      }
                    />
                  )}
                </div>
              )}

              {/* ── Tab bar ───────────────────────────────────────────── */}
              <div
                className="flex border-b border-slate-200"
                role="tablist"
                aria-label="Application sections"
              >
                {(['diff', 'cover'] as const).map((tab) => (
                  <button
                    key={tab}
                    role="tab"
                    aria-selected={activeTab === tab}
                    aria-controls={`tabpanel-${tab}`}
                    id={`tab-${tab}`}
                    onClick={() => setActiveTab(tab)}
                    className={`-mb-px border-b-2 px-1 py-3 text-[13px] font-medium transition mr-6 last:mr-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                      activeTab === tab
                        ? 'border-indigo-500 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {tab === 'diff' ? 'Resume Changes' : 'Cover Letter'}
                  </button>
                ))}
              </div>

              {/* ── Tab panels ────────────────────────────────────────── */}

              {/* Resume Changes tab */}
              <div
                role="tabpanel"
                id="tabpanel-diff"
                aria-labelledby="tab-diff"
                hidden={activeTab !== 'diff'}
              >
                <section aria-labelledby="diff-section-heading">
                  <h2 id="diff-section-heading" className="sr-only">
                    Tailored Resume Changes
                  </h2>

                  {/* Edit controls row */}
                  {isPending && (
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                          {resumeEditMode ? 'Editing resume' : 'Resume diff'}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            if (resumeEditMode) {
                              setResumeEditText(servedResumeText)
                              setResumeEditMode(false)
                            } else {
                              setResumeEditText(servedResumeText)
                              setResumeEditMode(true)
                            }
                          }}
                          disabled={resumeSaving || resumeRevising}
                          className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-[12px] font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50"
                        >
                          {resumeEditMode ? (
                            <>
                              <svg
                                className="h-3 w-3"
                                viewBox="0 0 16 16"
                                fill="currentColor"
                                aria-hidden="true"
                              >
                                <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z" />
                              </svg>
                              Cancel edit
                            </>
                          ) : (
                            <>
                              <svg
                                className="h-3 w-3"
                                viewBox="0 0 16 16"
                                fill="currentColor"
                                aria-hidden="true"
                              >
                                <path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm.176 4.823L9.75 4.81l-6.286 6.287a.253.253 0 0 0-.064.108l-.558 1.953 1.953-.558a.253.253 0 0 0 .108-.064Zm1.238-3.763a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354Z" />
                              </svg>
                              Edit content
                            </>
                          )}
                        </button>
                      </div>

                      {!resumeEditMode && (
                        <RevertButtonGroup
                          tab="diff"
                          isPending={isPending}
                          isAiDraftCurrent={resumeIsAtAiDraft}
                          onRevert={(to) => {
                            setRevertError(null)
                            setPendingRevert({ target: 'resume', to })
                          }}
                          disabled={revertMutation.isPending || resumeRevising}
                        />
                      )}
                    </div>
                  )}

                  {/* Resume direct-edit textarea */}
                  {resumeEditMode && isPending ? (
                    <div className="flex flex-col gap-2">
                      <div className="rounded-xl border border-indigo-200 bg-white ring-1 ring-indigo-100">
                        <textarea
                          value={resumeEditText}
                          onChange={(e) => setResumeEditText(e.target.value)}
                          rows={20}
                          aria-label="Edit tailored resume text"
                          disabled={resumeSaving}
                          className="w-full resize-y rounded-xl bg-transparent p-4 font-mono text-[12px] leading-relaxed text-slate-700 focus:outline-none disabled:opacity-60"
                        />
                      </div>
                      {editError && editMutation.variables?.target === 'resume' && (
                        <p role="alert" className="text-[11px] text-rose-600">
                          {editError}
                        </p>
                      )}
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            editMutation.mutate({ target: 'resume', text: resumeEditText })
                          }
                          disabled={resumeSaving || resumeEditText.trim() === ''}
                          aria-busy={resumeSaving}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
                        >
                          {resumeSaving && <InlineSpinner />}
                          {resumeSaving ? 'Saving…' : 'Save resume'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setResumeEditText(servedResumeText)
                            setResumeEditMode(false)
                          }}
                          disabled={resumeSaving}
                          className="rounded-lg border border-slate-200 px-3.5 py-2 text-[13px] font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <DiffView hunks={diffHunks} />
                  )}

                  {/* Request changes — resume */}
                  {isPending && !resumeEditMode && (
                    <form
                      className="mt-4 flex flex-col gap-2"
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (!resumeReviseInput.trim()) return
                        reviseMutation.mutate({
                          target: 'resume',
                          instructions: resumeReviseInput,
                        })
                      }}
                      aria-label="Request changes to resume"
                    >
                      <label
                        htmlFor="resume-revise-input"
                        className="text-[11px] font-semibold uppercase tracking-widest text-slate-400"
                      >
                        Request changes
                      </label>
                      <div className="flex gap-2">
                        <input
                          id="resume-revise-input"
                          type="text"
                          value={resumeReviseInput}
                          onChange={(e) => setResumeReviseInput(e.target.value)}
                          placeholder="e.g. Emphasise Python experience more"
                          disabled={resumeRevising}
                          className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-[13px] text-slate-700 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-60"
                        />
                        <button
                          type="submit"
                          disabled={resumeRevising || !resumeReviseInput.trim()}
                          aria-busy={resumeRevising}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
                        >
                          {resumeRevising && <InlineSpinner />}
                          {resumeRevising ? 'Applying…' : 'Request changes'}
                        </button>
                      </div>
                      {reviseError && reviseMutation.variables?.target === 'resume' && (
                        <p role="alert" className="text-[11px] text-rose-600">
                          {reviseError}
                        </p>
                      )}
                    </form>
                  )}
                </section>
              </div>

              {/* Cover Letter tab */}
              <div
                role="tabpanel"
                id="tabpanel-cover"
                aria-labelledby="tab-cover"
                hidden={activeTab !== 'cover'}
              >
                <section aria-labelledby="cover-section-heading">
                  <h2 id="cover-section-heading" className="sr-only">
                    Cover Letter
                  </h2>

                  {/* Edit controls row */}
                  {isPending && (
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                          {coverEditMode ? 'Editing cover letter' : 'Cover letter'}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            if (coverEditMode) {
                              setCoverEditText(servedCoverText)
                              setCoverEditMode(false)
                            } else {
                              setCoverEditText(servedCoverText)
                              setCoverEditMode(true)
                            }
                          }}
                          disabled={coverSaving || coverRevising}
                          className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-[12px] font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50"
                        >
                          {coverEditMode ? (
                            <>
                              <svg
                                className="h-3 w-3"
                                viewBox="0 0 16 16"
                                fill="currentColor"
                                aria-hidden="true"
                              >
                                <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z" />
                              </svg>
                              Cancel edit
                            </>
                          ) : (
                            <>
                              <svg
                                className="h-3 w-3"
                                viewBox="0 0 16 16"
                                fill="currentColor"
                                aria-hidden="true"
                              >
                                <path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm.176 4.823L9.75 4.81l-6.286 6.287a.253.253 0 0 0-.064.108l-.558 1.953 1.953-.558a.253.253 0 0 0 .108-.064Zm1.238-3.763a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354Z" />
                              </svg>
                              Edit content
                            </>
                          )}
                        </button>
                      </div>

                      {!coverEditMode && (
                        <RevertButtonGroup
                          tab="cover"
                          isPending={isPending}
                          isAiDraftCurrent={coverIsAtAiDraft}
                          onRevert={(to) => {
                            setRevertError(null)
                            setPendingRevert({ target: 'cover_letter', to })
                          }}
                          disabled={revertMutation.isPending || coverRevising}
                        />
                      )}
                    </div>
                  )}

                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <textarea
                      readOnly={!coverEditMode || !isPending}
                      value={
                        coverEditMode && isPending
                          ? coverEditText
                          : appQuery.data!.cover_letter_text
                      }
                      onChange={(e) => setCoverEditText(e.target.value)}
                      rows={18}
                      aria-label={
                        coverEditMode && isPending
                          ? 'Edit cover letter text'
                          : 'Cover letter text (read only)'
                      }
                      disabled={coverSaving}
                      className={`w-full resize-none bg-transparent text-[13px] leading-relaxed text-slate-700 focus:outline-none disabled:opacity-60 ${
                        coverEditMode && isPending
                          ? 'rounded-lg border border-indigo-200 bg-white px-3 py-2 ring-1 ring-indigo-100'
                          : ''
                      }`}
                    />
                  </div>

                  {coverEditMode && isPending && (
                    <div className="mt-2 flex flex-col gap-2">
                      {editError && editMutation.variables?.target === 'cover_letter' && (
                        <p role="alert" className="text-[11px] text-rose-600">
                          {editError}
                        </p>
                      )}
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            editMutation.mutate({ target: 'cover_letter', text: coverEditText })
                          }
                          disabled={coverSaving || coverEditText.trim() === ''}
                          aria-busy={coverSaving}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
                        >
                          {coverSaving && <InlineSpinner />}
                          {coverSaving ? 'Saving…' : 'Save cover letter'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setCoverEditText(servedCoverText)
                            setCoverEditMode(false)
                          }}
                          disabled={coverSaving}
                          className="rounded-lg border border-slate-200 px-3.5 py-2 text-[13px] font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Request changes — cover letter */}
                  {isPending && !coverEditMode && (
                    <form
                      className="mt-4 flex flex-col gap-2"
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (!coverReviseInput.trim()) return
                        reviseMutation.mutate({
                          target: 'cover_letter',
                          instructions: coverReviseInput,
                        })
                      }}
                      aria-label="Request changes to cover letter"
                    >
                      <label
                        htmlFor="cover-revise-input"
                        className="text-[11px] font-semibold uppercase tracking-widest text-slate-400"
                      >
                        Request changes
                      </label>
                      <div className="flex gap-2">
                        <input
                          id="cover-revise-input"
                          type="text"
                          value={coverReviseInput}
                          onChange={(e) => setCoverReviseInput(e.target.value)}
                          placeholder="e.g. Make the opening paragraph more concise"
                          disabled={coverRevising}
                          className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-[13px] text-slate-700 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-60"
                        />
                        <button
                          type="submit"
                          disabled={coverRevising || !coverReviseInput.trim()}
                          aria-busy={coverRevising}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
                        >
                          {coverRevising && <InlineSpinner />}
                          {coverRevising ? 'Applying…' : 'Request changes'}
                        </button>
                      </div>
                      {reviseError && reviseMutation.variables?.target === 'cover_letter' && (
                        <p role="alert" className="text-[11px] text-rose-600">
                          {reviseError}
                        </p>
                      )}
                    </form>
                  )}
                </section>
              </div>

              {/* Bottom padding for sticky footer */}
              <div className="h-2" aria-hidden="true" />
            </div>
          )}
        </div>
      </main>

      {/* ── Sticky footer ──────────────────────────────────────────────────── */}
      {appQuery.data && (
        <>
          {isPending && !successMessage && (
            <footer className="shrink-0 border-t border-slate-200 bg-white px-5 py-4 shadow-[0_-1px_3px_0_rgb(0_0_0_/_0.06)]">
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
                <div className="mx-auto flex max-w-3xl items-center gap-2">
                  <button
                    onClick={() => {
                      setSaveError(null)
                      setShowSaveModal(true)
                    }}
                    disabled={saveMutation.isPending}
                    aria-busy={saveMutation.isPending}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-[14px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <svg
                      className="h-4 w-4"
                      viewBox="0 0 16 16"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <path d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" />
                    </svg>
                    Approve &amp; Save
                  </button>
                  <button
                    onClick={() => setShowRejectConfirm(true)}
                    className="rounded-xl border border-rose-200 px-5 py-3 text-[14px] font-medium text-rose-600 transition hover:border-rose-300 hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
                  >
                    Reject
                  </button>
                </div>
              )}
            </footer>
          )}

          {!isPending && !isPreparing && !prepFailed && (
            <footer className="shrink-0 border-t border-slate-100 bg-slate-50 px-5 py-3">
              <p className="text-center text-[12px] text-slate-500">
                Application status:{' '}
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                    STATUS_STYLES[status] ?? STATUS_STYLES['pending']
                  }`}
                >
                  {STATUS_LABELS[status] ?? status}
                </span>
              </p>
            </footer>
          )}
        </>
      )}

      {/* ── Approve & Save confirmation modal ──────────────────────────────── */}
      {showSaveModal && job && (
        <ConfirmationModal
          company={job.company}
          title={job.title}
          onConfirm={() => saveMutation.mutate()}
          onCancel={() => {
            setShowSaveModal(false)
            setSaveError(null)
          }}
          isSubmitting={saveMutation.isPending}
          error={saveError}
        />
      )}

      {/* ── Revert confirmation modal ───────────────────────────────────────── */}
      {pendingRevert && (
        <RevertModal
          target={pendingRevert.target}
          to={pendingRevert.to}
          onConfirm={() =>
            revertMutation.mutate({ target: pendingRevert.target, to: pendingRevert.to })
          }
          onCancel={() => {
            setPendingRevert(null)
            setRevertError(null)
          }}
          isSubmitting={revertMutation.isPending}
          error={revertError}
        />
      )}
    </div>
  )
}
