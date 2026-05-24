import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { prepareApplication } from '../../api/jobs'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ScoreBadge } from './ScoreBadge'
import type { JobPosting } from '../../types'

interface JobCardProps {
  job: JobPosting
}

const REMOTE_STATUS_LABELS: Record<JobPosting['remote_status'], string | null> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
  unspecified: null,
}

const REMOTE_STATUS_COLORS: Record<JobPosting['remote_status'], string> = {
  remote: 'bg-green-100 text-green-800',
  hybrid: 'bg-yellow-100 text-yellow-800',
  onsite: 'bg-gray-100 text-gray-700',
  unspecified: 'bg-gray-100 text-gray-500',
}

export function JobCard({ job }: JobCardProps) {
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const queryClient = useQueryClient()
  const [prepareError, setPrepareError] = useState<string | null>(null)

  const prepareMutation = useMutation({
    mutationFn: () => prepareApplication(job.id),
    onSuccess: (data) => {
      // Invalidate applications list so polling can pick up the new entry
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setActiveApplication(data.job_id)
    },
    onError: () => {
      setPrepareError('Failed to prepare application. Please try again.')
    },
  })

  const remoteLabel = REMOTE_STATUS_LABELS[job.remote_status]

  return (
    <article
      aria-label={`${job.title}${job.company ? ` at ${job.company}` : ''}`}
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <ScoreBadge score={job.match_score} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold text-gray-900">{job.title}</h3>
              {job.company && (
                <p className="mt-0.5 text-sm text-gray-600">{job.company}</p>
              )}
            </div>
            <div className="flex shrink-0 flex-wrap gap-1.5">
              {remoteLabel && (
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${REMOTE_STATUS_COLORS[job.remote_status]}`}
                >
                  {remoteLabel}
                </span>
              )}
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
            {job.location && (
              <span className="flex items-center gap-1">
                <span aria-hidden="true">&#x1F4CD;</span>
                {job.location}
              </span>
            )}
            {job.compensation && (
              <span className="flex items-center gap-1">
                <span aria-hidden="true">&#x1F4B0;</span>
                {job.compensation}
              </span>
            )}
            {job.posted_date && (
              <span>
                Posted{' '}
                {new Date(job.posted_date).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </span>
            )}
            <span className="text-gray-400">{job.source}</span>
          </div>

          {prepareError && (
            <p role="alert" className="mt-2 text-xs text-red-600">
              {prepareError}
            </p>
          )}

          <div className="mt-3 flex gap-2">
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
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
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {prepareMutation.isPending ? 'Preparing...' : 'Prepare Application'}
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}
