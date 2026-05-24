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

  // Focus the cancel button on mount (safe default)
  useEffect(() => {
    cancelRef.current?.focus()
  }, [])

  // Trap focus within modal
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
      <div className="fixed inset-0 z-50 bg-black/50" aria-hidden="true" />

      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby="confirm-modal-desc"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
          <h2 id="confirm-modal-title" className="text-lg font-semibold text-gray-900">
            Confirm submission
          </h2>
          <p id="confirm-modal-desc" className="mt-2 text-sm text-gray-600">
            Submit application to <strong>{companyDisplay}</strong> for{' '}
            <strong>{title}</strong>? This cannot be undone.
          </p>

          {error && (
            <div
              role="alert"
              className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              {error}
            </div>
          )}

          <div className="mt-5 flex gap-3 justify-end">
            <button
              ref={cancelRef}
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isSubmitting}
              aria-busy={isSubmitting}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? 'Submitting...' : 'Confirm'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
