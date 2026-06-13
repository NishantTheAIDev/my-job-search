import { useEffect, useRef } from 'react'

interface ConfirmationModalProps {
  company: string | null
  title: string
  onConfirm: () => void
  onCancel: () => void
  isSubmitting: boolean
  error: string | null
}

export function ConfirmationModal({
  company,
  title,
  onConfirm,
  onCancel,
  isSubmitting,
  error,
}: ConfirmationModalProps) {
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

  const companyDisplay = company ?? 'this company'

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-[2px] animate-fade-in" aria-hidden="true" />

      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby="confirm-modal-desc"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="animate-scale-in w-full max-w-md rounded-2xl bg-white p-6 shadow-[0_20px_40px_-8px_rgb(0_0_0_/_0.20)]">
          {/* Icon */}
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-indigo-100">
            <svg className="h-6 w-6 text-indigo-600" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
            </svg>
          </div>

          <h2 id="confirm-modal-title" className="text-[16px] font-bold text-slate-900">
            Confirm submission
          </h2>
          <p id="confirm-modal-desc" className="mt-1.5 text-[13px] leading-relaxed text-slate-600">
            You're about to submit your application to{' '}
            <strong className="font-semibold text-slate-800">{companyDisplay}</strong> for the{' '}
            <strong className="font-semibold text-slate-800">{title}</strong> role.
            This action cannot be undone.
          </p>

          {error && (
            <div
              role="alert"
              className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3.5"
            >
              <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-500" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-3.5a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3A.75.75 0 0 1 8 4.5ZM8 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
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
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                  </svg>
                  Submitting…
                </>
              ) : (
                'Confirm & Submit'
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
