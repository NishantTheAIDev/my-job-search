interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <span className="mt-0.5 shrink-0 text-lg leading-none" aria-hidden="true">
        &#x26A0;
      </span>
      <div className="flex-1">
        <p className="font-medium">Something went wrong</p>
        <p className="mt-1 text-sm">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 text-sm font-medium underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
