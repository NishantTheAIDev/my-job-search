interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <span className="mt-0.5 shrink-0 text-red-500" aria-hidden="true">
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
            clipRule="evenodd"
          />
        </svg>
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-red-800">Something went wrong</p>
        <p className="mt-0.5 text-sm text-red-700">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-red-700 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 rounded"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
