interface LoadingSpinnerProps {
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingSpinner({ label = 'Loading...', size = 'md' }: LoadingSpinnerProps) {
  const ringSize = {
    sm: 'h-4 w-4 border-2',
    md: 'h-7 w-7 border-2',
    lg: 'h-11 w-11 border-[3px]',
  }[size]

  const textSize = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-sm',
  }[size]

  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-10"
      role="status"
      aria-label={label}
    >
      <div
        className={`${ringSize} animate-spin rounded-full border-slate-200 border-t-indigo-500`}
        aria-hidden="true"
      />
      <span className={`${textSize} font-medium text-slate-500`}>{label}</span>
    </div>
  )
}

interface SkeletonCardProps {
  count?: number
}

export function SkeletonCard({ count = 4 }: SkeletonCardProps) {
  return (
    <div className="flex flex-col gap-0 divide-y divide-slate-100" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="px-4 py-4">
          <div className="flex gap-3">
            {/* Score circle */}
            <div className="skeleton h-10 w-10 flex-shrink-0 rounded-full bg-slate-200" />
            <div className="flex-1 space-y-2">
              <div className="skeleton h-4 w-3/5 rounded bg-slate-200" />
              <div className="skeleton h-3 w-2/5 rounded bg-slate-200" />
              <div className="skeleton h-3 w-full rounded bg-slate-200" />
              <div className="skeleton h-3 w-4/5 rounded bg-slate-200" />
              <div className="mt-3 flex gap-2">
                <div className="skeleton h-6 w-20 rounded-md bg-slate-200" />
                <div className="skeleton h-6 w-28 rounded-md bg-slate-200" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
