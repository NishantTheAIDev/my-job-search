import type { PrepStage } from '../../types'

const STAGES: { key: Exclude<PrepStage, ''>; label: string }[] = [
  { key: 'parsing', label: 'Analyzing the job description' },
  { key: 'scoring', label: 'Scoring your resume against the role' },
  { key: 'tailoring', label: 'Tailoring your resume' },
  { key: 'drafting', label: 'Drafting your cover letter' },
]

/**
 * Staged progress for an application still in the `preparing` state. Shows each
 * pipeline step with a done / in-progress / upcoming indicator, driven by the
 * `prep_stage` the backend advances as the LLM pipeline runs.
 */
export function PrepProgress({ stage }: { stage: PrepStage }) {
  const currentIndex = STAGES.findIndex((s) => s.key === stage)

  return (
    <div className="flex flex-col gap-4 py-6" role="status" aria-live="polite">
      <p className="text-[13px] font-medium text-slate-500">
        Preparing your application — this usually takes under a minute.
      </p>
      <ol className="flex flex-col gap-3">
        {STAGES.map((s, i) => {
          // Before the first stage marker arrives, treat the first step as active.
          const idx = currentIndex === -1 ? 0 : currentIndex
          const state = i < idx ? 'done' : i === idx ? 'active' : 'upcoming'
          return (
            <li key={s.key} className="flex items-center gap-3">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center" aria-hidden="true">
                {state === 'done' && (
                  <svg className="h-5 w-5 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0l-3.5-3.5a1 1 0 1 1 1.4-1.4l2.8 2.8 6.8-6.8a1 1 0 0 1 1.4 0Z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
                {state === 'active' && (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
                )}
                {state === 'upcoming' && (
                  <span className="h-2 w-2 rounded-full bg-slate-300" />
                )}
              </span>
              <span
                className={`text-[13px] ${
                  state === 'done'
                    ? 'text-slate-500'
                    : state === 'active'
                      ? 'font-medium text-slate-900'
                      : 'text-slate-400'
                }`}
              >
                {s.label}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
