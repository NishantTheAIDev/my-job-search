import { Logo } from '../shared/Logo'
import { SearchBar } from '../shared/SearchBar'
import { ResumeUpload } from '../shared/ResumeUpload'
import { SOURCE_COLORS, SUPPORTED_BOARDS } from '../../lib/constants'
import { useJobSearchStore } from '../../store/useJobSearchStore'

const STEPS = [
  {
    title: 'Search every board at once',
    body: 'One query fans out across LinkedIn, Indeed, Greenhouse, Lever and more — deduplicated into a single list.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    ),
  },
  {
    title: 'AI scores & tailors',
    body: 'Claude rates each role against your resume, then tailors your resume and drafts a cover letter for the ones you like.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
    ),
  },
  {
    title: 'You approve, then apply',
    body: 'Nothing is ever submitted without your explicit approval. Review the tailored draft, then send it with one click.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    ),
  },
]

export function LandingPage() {
  const setShowInsights = useJobSearchStore((s) => s.setShowInsights)
  const setShowPasteJd = useJobSearchStore((s) => s.setShowPasteJd)
  const setShowSavedApplications = useJobSearchStore((s) => s.setShowSavedApplications)
  const setShowSavedSearches = useJobSearchStore((s) => s.setShowSavedSearches)

  return (
    <div className="min-h-full bg-slate-50">
      {/* Top nav */}
      <nav className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-5 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)]">
        <Logo />
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPasteJd(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Tailor resume from job description"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
            Tailor from JD
          </button>
          <button
            onClick={() => setShowSavedSearches(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="View saved searches"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            Saved Searches
          </button>
          <button
            onClick={() => setShowSavedApplications(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="View saved applications"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
            </svg>
            Saved Applications
          </button>
          <button
            onClick={() => setShowInsights(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="View job market insights"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
            </svg>
            Market Insights
          </button>
        </div>
      </nav>

      {/* Hero */}
      <header className="relative overflow-hidden">
        {/* Soft decorative gradient backdrop */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute -top-32 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-gradient-to-br from-indigo-200/50 via-sky-200/40 to-transparent blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-3xl px-5 pb-10 pt-16 text-center sm:pt-24">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[12px] font-semibold text-indigo-600">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
            AI-powered job search & apply
          </span>
          <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
            Find the right role,
            <br className="hidden sm:block" />
            <span className="bg-gradient-to-r from-indigo-600 to-sky-500 bg-clip-text text-transparent"> tailored to you.</span>
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-slate-500">
            Search across 11 job boards at once. Let AI score each match against your resume,
            tailor your application, and draft a cover letter — you stay in control of every submission.
          </p>

          <div className="mx-auto mt-8 max-w-2xl text-left">
            <SearchBar variant="hero" autoFocus />
          </div>

          <div className="mx-auto mt-6 max-w-md">
            <ResumeUpload variant="card" />
          </div>
        </div>
      </header>

      {/* How it works */}
      <section aria-labelledby="how-it-works" className="mx-auto max-w-5xl px-5 py-14">
        <h2 id="how-it-works" className="mb-8 text-center text-[13px] font-bold uppercase tracking-widest text-slate-400">
          How it works
        </h2>
        <ol className="grid gap-5 sm:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="relative rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
                  {step.icon}
                </svg>
              </div>
              <span className="absolute right-5 top-5 text-[13px] font-bold text-slate-200">0{i + 1}</span>
              <h3 className="text-[15px] font-semibold text-slate-900">{step.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-slate-500">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Supported boards */}
      <section aria-label="Supported job boards" className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-5 py-10 text-center">
          <p className="mb-5 text-[12px] font-semibold uppercase tracking-widest text-slate-400">
            Sourcing jobs from
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            {SUPPORTED_BOARDS.map((board) => (
              <span
                key={board.key}
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] font-medium text-slate-600"
              >
                <span className={`h-1.5 w-1.5 rounded-full ${SOURCE_COLORS[board.key] ?? 'bg-slate-400'}`} aria-hidden="true" />
                {board.label}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
