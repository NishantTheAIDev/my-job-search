interface ScoreBadgeProps {
  score: number | null
  size?: 'sm' | 'md'
}

export function ScoreBadge({ score, size = 'md' }: ScoreBadgeProps) {
  const dim = size === 'sm' ? 'h-9 w-9 text-[11px]' : 'h-11 w-11 text-xs'

  if (score === null) {
    return (
      <span
        className={`inline-flex ${dim} items-center justify-center rounded-full border-2 border-slate-200 bg-slate-50 font-bold text-slate-400`}
        aria-label="No match score"
        title="No match score"
      >
        —
      </span>
    )
  }

  const ring =
    score >= 70
      ? 'border-emerald-400'
      : score >= 50
        ? 'border-amber-400'
        : 'border-rose-400'

  const fill =
    score >= 70
      ? 'bg-emerald-50 text-emerald-700'
      : score >= 50
        ? 'bg-amber-50 text-amber-700'
        : 'bg-rose-50 text-rose-700'

  return (
    <span
      className={`inline-flex ${dim} items-center justify-center rounded-full border-2 font-bold ${ring} ${fill}`}
      aria-label={`Match score: ${score} out of 100`}
      title={`Match score: ${score}/100`}
    >
      {score}
    </span>
  )
}
