import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import { prepareApplication } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ScoreBadge } from './ScoreBadge'
import { formatPostedDate } from '../../lib/date'
import type { JobPosting } from '../../types'

interface JobCardProps {
  job: JobPosting
  onShowDetail: () => void
  isSelected?: boolean
}

const REMOTE_STATUS_LABELS: Record<JobPosting['remote_status'], string | null> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
  unspecified: null,
}

const REMOTE_STATUS_STYLES: Record<JobPosting['remote_status'], string> = {
  remote: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  hybrid: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  onsite: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  unspecified: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
}

const PREVIEW_LENGTH = 120

function stripToPlainText(raw: string): string {
  if (!raw) return ''
  // Decode HTML entities (handles pre-escaped HTML from adapters like Greenhouse)
  const decoder = document.createElement('textarea')
  decoder.innerHTML = raw
  const decoded = decoder.value
  // Use DOMParser to strip all tags and get readable text content
  const doc = new DOMParser().parseFromString(decoded, 'text/html')
  return doc.body.textContent ?? ''
}

function getDescriptionPreview(text: string): { preview: string; truncated: boolean } {
  const normalized = stripToPlainText(text).replace(/\s+/g, ' ').trim()
  if (normalized.length <= PREVIEW_LENGTH) return { preview: normalized, truncated: false }
  return { preview: normalized.slice(0, PREVIEW_LENGTH).trimEnd(), truncated: true }
}

function LocationIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M8 1.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM2 6a6 6 0 1 1 10.89 3.477l3.817 3.816a.75.75 0 0 1-1.06 1.061l-3.816-3.816A6 6 0 0 1 2 6Z" clipRule="evenodd" />
    </svg>
  )
}

function SalaryIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8.75 11V13h1.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1 0-1.5h1.5v-2A5.251 5.251 0 0 1 2.75 6a.75.75 0 0 1 1.5 0 3.75 3.75 0 0 0 7.5 0 .75.75 0 0 1 1.5 0A5.251 5.251 0 0 1 8.75 11Z" />
      <path d="M8 1a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" />
    </svg>
  )
}

export function JobCard({ job, onShowDetail, isSelected = false }: JobCardProps) {
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const queryClient = useQueryClient()
  const [prepareError, setPrepareError] = useState<string | null>(null)

  const prepareMutation = useMutation({
    mutationFn: () => prepareApplication(job.id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setActiveApplication(data.job_id)
    },
    onError: (err) => {
      const detail = (err as AxiosError<{ detail?: string }>)?.response?.data?.detail
      setPrepareError(detail ?? 'Failed to prepare application. Please try again.')
    },
  })

  const remoteLabel = REMOTE_STATUS_LABELS[job.remote_status]
  const { preview, truncated } = getDescriptionPreview(job.description)

  return (
    <article
      aria-label={`${job.title}${job.company ? ` at ${job.company}` : ''}`}
      className={`group rounded-xl border transition-all duration-150 ${
        isSelected
          ? 'border-indigo-300 bg-indigo-50 shadow-[0_0_0_3px_rgb(99_102_241_/_0.12)]'
          : 'border-slate-200 bg-white hover:border-indigo-200 hover:shadow-[0_2px_8px_0_rgb(0_0_0_/_0.08)]'
      }`}
    >
      {/* Clickable zone */}
      <div
        role="button"
        tabIndex={0}
        onClick={onShowDetail}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onShowDetail()
          }
        }}
        aria-label={`View details for ${job.title}${job.company ? ` at ${job.company}` : ''}`}
        className="cursor-pointer px-4 pt-4 pb-3"
      >
        <div className="flex items-start gap-3">
          <ScoreBadge score={job.match_score} size="sm" />

          <div className="min-w-0 flex-1">
            {/* Title + remote badge */}
            <div className="flex flex-wrap items-start justify-between gap-1.5">
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-[14px] font-semibold leading-snug text-slate-900">
                  {job.title}
                </h3>
                {job.company && (
                  <p className="mt-0.5 text-[12px] font-medium text-slate-500">{job.company}</p>
                )}
              </div>
              {remoteLabel && (
                <span
                  className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${REMOTE_STATUS_STYLES[job.remote_status]}`}
                >
                  {remoteLabel}
                </span>
              )}
            </div>

            {/* Description preview */}
            {preview && (
              <p className="mt-2 text-[12px] leading-relaxed text-slate-500">
                {preview}
                {truncated && (
                  <span className="font-medium text-indigo-500">… more</span>
                )}
              </p>
            )}

            {/* Meta row */}
            <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
              {job.location && (
                <span className="flex items-center gap-1">
                  <LocationIcon />
                  {job.location}
                </span>
              )}
              {job.compensation && (
                <span className="flex items-center gap-1">
                  <SalaryIcon />
                  {job.compensation}
                </span>
              )}
              {formatPostedDate(job.posted_date) && (
                <span>{formatPostedDate(job.posted_date)}</span>
              )}
              <span className="ml-auto rounded-full bg-slate-100 px-1.5 py-0.5 font-medium text-slate-400">
                {job.source}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Action row */}
      <div className="flex items-center justify-between gap-2 border-t border-slate-100 px-4 py-2.5">
        {prepareError && (
          <p role="alert" className="text-[11px] text-red-500">
            {prepareError}
          </p>
        )}
        <div className="ml-auto flex gap-2">
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
            aria-label={`View job posting for ${job.title} (opens in new tab)`}
          >
            View posting
          </a>
          <button
            onClick={() => {
              setPrepareError(null)
              prepareMutation.mutate()
            }}
            disabled={prepareMutation.isPending}
            aria-busy={prepareMutation.isPending}
            className="inline-flex items-center rounded-lg bg-indigo-600 px-3 py-1.5 text-[11px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {prepareMutation.isPending ? (
              <>
                <svg className="mr-1.5 h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                </svg>
                Preparing…
              </>
            ) : (
              'Prepare Application'
            )}
          </button>
        </div>
      </div>
    </article>
  )
}
