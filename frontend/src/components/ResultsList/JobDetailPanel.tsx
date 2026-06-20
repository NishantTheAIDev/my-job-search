import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import { prepareApplication } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ScoreBadge } from './ScoreBadge'
import { formatPostedDate } from '../../lib/date'
import type { JobPosting } from '../../types'

function sanitizeDescription(raw: string): string {
  // Step 1: Decode HTML entities (Greenhouse and some other adapters store pre-escaped HTML
  // e.g. "&lt;p&gt;" must become "<p>" before we can parse it as markup)
  const decoder = document.createElement('textarea')
  decoder.innerHTML = raw
  let html = decoder.value

  // Step 2: Collapse 3+ consecutive <br> or blank lines to at most 2
  html = html.replace(/(\s*<br\s*\/?>\s*){3,}/gi, '<br><br>')
  html = html.replace(/\n{3,}/g, '\n\n')

  // Step 3: Convert markdown bold/italic to HTML
  html = html.replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>')
  html = html.replace(/__(.+?)__/gs, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/gs, '<em>$1</em>')
  html = html.replace(/_([^_\s][^_]*)_/gs, '<em>$1</em>')

  // Step 4: If still no HTML tags after all conversions, just convert newlines
  if (!/[<>]/.test(html)) {
    return html.replace(/\n/g, '<br>')
  }

  // Step 5: Parse, sanitize, and strip presentation attributes
  const doc = new DOMParser().parseFromString(html, 'text/html')

  // Remove dangerous/noisy elements entirely
  doc.querySelectorAll('script, style, iframe, form, object, embed, img').forEach((el) => el.remove())

  doc.querySelectorAll('*').forEach((el) => {
    // Strip all attributes except a safe allowlist
    const allowed = new Set(['href', 'target', 'rel', 'colspan', 'rowspan'])
    Array.from(el.attributes).forEach((attr) => {
      if (!allowed.has(attr.name)) el.removeAttribute(attr.name)
    })

    // Fix links: safe target + rel
    if (el.tagName === 'A') {
      const href = el.getAttribute('href') ?? ''
      // Drop javascript: and data: hrefs
      if (/^(javascript|data):/i.test(href)) {
        el.removeAttribute('href')
      }
      el.setAttribute('target', '_blank')
      el.setAttribute('rel', 'noopener noreferrer')
    }
  })

  return doc.body.innerHTML
}

const REMOTE_LABELS: Record<JobPosting['remote_status'], string | null> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
  unspecified: null,
}

const REMOTE_STYLES: Record<JobPosting['remote_status'], string> = {
  remote: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  hybrid: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  onsite: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  unspecified: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
}

interface JobDetailPanelProps {
  job: JobPosting
  onClose: () => void
}

export function JobDetailPanel({ job, onClose }: JobDetailPanelProps) {
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const queryClient = useQueryClient()
  const [prepareError, setPrepareError] = useState<string | null>(null)

  const prepareMutation = useMutation({
    mutationFn: () => prepareApplication(job.id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setActiveApplication(data.job_id)
      // Close this detail slide-over (z-50) so the ResumeEditor (z-40) hosting
      // the prep pipeline and approve/reject controls becomes visible.
      onClose()
    },
    onError: (err) => {
      const detail = (err as AxiosError<{ detail?: string }>)?.response?.data?.detail
      setPrepareError(detail ?? 'Failed to prepare application. Please try again.')
    },
  })

  const remoteLabel = REMOTE_LABELS[job.remote_status]

  return (
    <div
      role="region"
      aria-label={`Job detail: ${job.title}`}
      className="px-8 py-7"
    >
      <div className="mx-auto max-w-2xl">

        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold leading-snug tracking-tight text-slate-900">
              {job.title}
            </h1>
            {job.company && (
              <p className="mt-1 text-base font-medium text-slate-500">{job.company}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <ScoreBadge score={job.match_score} />
            <button
              onClick={onClose}
              aria-label="Close job detail"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
              </svg>
            </button>
          </div>
        </div>

        {/* Meta pills */}
        <div className="mb-7 flex flex-wrap items-center gap-2 text-sm">
          {remoteLabel && (
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[12px] font-semibold uppercase tracking-wide ${REMOTE_STYLES[job.remote_status]}`}>
              {remoteLabel}
            </span>
          )}
          {job.location && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-600">
              <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M8 1.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM2 6a6 6 0 1 1 10.89 3.477l3.817 3.816a.75.75 0 0 1-1.06 1.061l-3.816-3.816A6 6 0 0 1 2 6Z" clipRule="evenodd" />
              </svg>
              {job.location}
            </span>
          )}
          {job.compensation && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-600">
              <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M8.75 11V13h1.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1 0-1.5h1.5v-2A5.251 5.251 0 0 1 2.75 6a.75.75 0 0 1 1.5 0 3.75 3.75 0 0 0 7.5 0 .75.75 0 0 1 1.5 0A5.251 5.251 0 0 1 8.75 11Z" />
                <path d="M8 1a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" />
              </svg>
              {job.compensation}
            </span>
          )}
          {formatPostedDate(job.posted_date) && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-600">
              <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M5.75 7.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM5 10.25a.75.75 0 1 1 1.5 0 .75.75 0 0 1-1.5 0ZM10.25 7.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM9.5 10.25a.75.75 0 1 1 1.5 0 .75.75 0 0 1-1.5 0ZM8 7.5a.75.75 0 1 0 0 1.5A.75.75 0 0 0 8 7.5Z" />
                <path fillRule="evenodd" d="M4.75 1a.75.75 0 0 1 .75.75V3h5V1.75a.75.75 0 0 1 1.5 0V3h.25A2.75 2.75 0 0 1 15 5.75v7.5A2.75 2.75 0 0 1 12.25 16h-8.5A2.75 2.75 0 0 1 1 13.25v-7.5A2.75 2.75 0 0 1 3.75 3H4V1.75A.75.75 0 0 1 4.75 1ZM3.75 4.5c-.69 0-1.25.56-1.25 1.25v.5h11v-.5c0-.69-.56-1.25-1.25-1.25h-8.5Zm-1.25 3.25v5.5c0 .69.56 1.25 1.25 1.25h8.5c.69 0 1.25-.56 1.25-1.25v-5.5h-11Z" clipRule="evenodd" />
              </svg>
              {formatPostedDate(job.posted_date)}
            </span>
          )}
          <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-indigo-500">
            {job.source}
          </span>
        </div>

        {/* Divider */}
        <hr className="mb-7 border-slate-100" />

        {/* Description */}
        <div className="mb-8">
          <h2 className="mb-4 text-[13px] font-semibold uppercase tracking-widest text-slate-400">
            Job Description
          </h2>
          {job.description ? (
            <div
              className="prose-description text-[14px] leading-7 text-slate-700 [&_p]:mb-3 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_strong]:font-bold [&_b]:font-bold [&_h1]:mb-2 [&_h1]:mt-4 [&_h1]:text-base [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-sm [&_h2]:font-bold [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:text-sm [&_h3]:font-semibold [&_a]:text-indigo-600 [&_a]:underline [&_br]:block"
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: sanitizeDescription(job.description) }}
            />
          ) : (
            <p className="italic text-slate-400">No description available.</p>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={() => { setPrepareError(null); prepareMutation.mutate() }}
            disabled={prepareMutation.isPending}
            aria-busy={prepareMutation.isPending}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {prepareMutation.isPending ? (
              <>
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                </svg>
                Preparing…
              </>
            ) : (
              <>
                <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M7.25 3.688L4.5 6.439A1.25 1.25 0 0 1 2.75 5.19L6.5.44A.75.75 0 0 1 7 .25h2a.75.75 0 0 1 .53.22l3.72 3.72a1.25 1.25 0 0 1-1.768 1.768L9 3.482V11.5a.75.75 0 0 1-1.5 0V3.688Z" />
                  <path d="M1.5 14a.5.5 0 0 0 .5.5h12a.5.5 0 0 0 0-1H2a.5.5 0 0 0-.5.5Z" />
                </svg>
                Prepare Application
              </>
            )}
          </button>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`View original job posting for ${job.title} (opens in new tab)`}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-3.5 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
          >
            <svg className="h-4 w-4 text-slate-400" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
              <path d="M6.22 8.72a.75.75 0 0 0 1.06 1.06l5.22-5.22v1.69a.75.75 0 0 0 1.5 0v-3.5a.75.75 0 0 0-.75-.75h-3.5a.75.75 0 0 0 0 1.5h1.69L6.22 8.72Z" />
              <path d="M3.5 6.75c0-.69.56-1.25 1.25-1.25H7A.75.75 0 0 0 7 4H4.75A2.75 2.75 0 0 0 2 6.75v4.5A2.75 2.75 0 0 0 4.75 14h4.5A2.75 2.75 0 0 0 12 11.25V9a.75.75 0 0 0-1.5 0v2.25c0 .69-.56 1.25-1.25 1.25h-4.5c-.69 0-1.25-.56-1.25-1.25v-4.5Z" />
            </svg>
            View Original
          </a>
        </div>

        {prepareError && (
          <p role="alert" className="mt-3 text-sm text-red-600">{prepareError}</p>
        )}
      </div>
    </div>
  )
}
