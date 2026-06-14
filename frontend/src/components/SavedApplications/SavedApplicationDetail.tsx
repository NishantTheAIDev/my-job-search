import { useQuery } from '@tanstack/react-query'
import { getApplication, getResumeDownloadUrl, getCoverLetterDownloadUrl, RENDERCV_THEMES, DEFAULT_RENDERCV_THEME } from '../../api/applications'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { ErrorBanner } from '../shared/ErrorBanner'
import { ScoreBadge } from '../ResultsList/ScoreBadge'
import { DownloadMenu } from '../shared/DownloadMenu'

// Reusable read-only section card (same visual contract as ApprovalScreen's SectionCard)
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

interface SavedApplicationDetailProps {
  applicationId: string
  onClose: () => void
}

export function SavedApplicationDetail({ applicationId, onClose }: SavedApplicationDetailProps) {
  const { data: application, isLoading, isError, refetch } = useQuery({
    queryKey: ['application-detail', applicationId],
    queryFn: () => getApplication(applicationId),
    staleTime: 60_000,
  })

  const gaps = application?.match_gaps ?? []

  return (
    <div className="flex h-full flex-col">
      {/* Panel header */}
      <div className="flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-4">
        <button
          onClick={onClose}
          aria-label="Close application detail"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-indigo-600 transition hover:text-indigo-800 focus:outline-none focus:underline"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M9.78 4.22a.75.75 0 0 1 0 1.06L7.06 8l2.72 2.72a.75.75 0 1 1-1.06 1.06L5.47 8.53a.75.75 0 0 1 0-1.06l3.25-3.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
          </svg>
          Back to list
        </button>
      </div>

      {/* Panel body */}
      <div className="flex-1 overflow-y-auto px-5 py-6">
        {isLoading && <LoadingSpinner label="Loading application details..." size="lg" />}

        {isError && (
          <ErrorBanner
            message="Could not load application details."
            onRetry={() => refetch()}
          />
        )}

        {application && (
          <div className="flex flex-col gap-5">
            {/* Score + rationale */}
            <SectionCard id="saved-detail-summary" label="Job Summary">
              <div className="flex items-start gap-4">
                <ScoreBadge score={application.match_score} />
                <div className="flex-1 min-w-0">
                  {application.match_rationale && (
                    <div className="rounded-lg bg-indigo-50 px-3 py-2.5">
                      <p className="text-[12px] leading-relaxed text-indigo-800">
                        <span className="font-semibold text-indigo-900">Match rationale: </span>
                        {application.match_rationale}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </SectionCard>

            {/* Gaps */}
            {gaps.length > 0 && (
              <SectionCard id="saved-detail-gaps" label="Gaps to Address">
                <ul className="flex flex-col gap-2" aria-label="Match gaps list">
                  {gaps.map((gap, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-600" aria-hidden="true">
                        <svg className="h-2.5 w-2.5" viewBox="0 0 16 16" fill="currentColor">
                          <path fillRule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-3.5a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3A.75.75 0 0 1 8 4.5ZM8 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
                        </svg>
                      </span>
                      <span className="text-[13px] leading-relaxed text-slate-700">{gap}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}

            {/* Tailored resume */}
            <SectionCard
              id="saved-detail-resume"
              label="Tailored Resume"
              action={
                <DownloadMenu
                  label="Download resume"
                  themes={RENDERCV_THEMES}
                  defaultTheme={DEFAULT_RENDERCV_THEME}
                  urlFor={(format, theme) => getResumeDownloadUrl(application.id, format, theme)}
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
              id="saved-detail-cover-letter"
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
          </div>
        )}
      </div>
    </div>
  )
}
