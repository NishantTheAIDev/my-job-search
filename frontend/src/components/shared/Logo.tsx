function BriefcaseIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    </svg>
  )
}

interface LogoProps {
  /** Optional click handler — when provided the logo becomes a button (e.g. "back to landing"). */
  onClick?: () => void
}

export function Logo({ onClick }: LogoProps) {
  const content = (
    <>
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
        <BriefcaseIcon />
      </div>
      <span className="text-[15px] font-semibold tracking-tight text-slate-900">Job Search Assistant</span>
      <span className="ml-1 inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-600">
        AI
      </span>
    </>
  )

  if (onClick) {
    return (
      <button
        onClick={onClick}
        aria-label="Start a new search"
        className="flex items-center gap-2.5 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        {content}
      </button>
    )
  }

  return <div className="flex items-center gap-2.5">{content}</div>
}
