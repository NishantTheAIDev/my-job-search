interface ScoreBadgeProps {
  score: number | null
}

export function ScoreBadge({ score }: ScoreBadgeProps) {
  if (score === null) {
    return (
      <span
        className="inline-flex h-10 w-10 items-center justify-center rounded-full border-2 border-gray-200 bg-gray-50 text-xs font-bold text-gray-400"
        aria-label="No match score"
        title="No match score"
      >
        &mdash;
      </span>
    )
  }

  const colorClass =
    score >= 70
      ? 'border-green-400 bg-green-50 text-green-700'
      : score >= 50
        ? 'border-yellow-400 bg-yellow-50 text-yellow-700'
        : 'border-red-400 bg-red-50 text-red-700'

  return (
    <span
      className={`inline-flex h-10 w-10 items-center justify-center rounded-full border-2 text-xs font-bold ${colorClass}`}
      aria-label={`Match score: ${score} out of 100`}
      title={`Match score: ${score}/100`}
    >
      {score}
    </span>
  )
}
