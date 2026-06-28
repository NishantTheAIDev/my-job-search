import { Logo } from '../shared/Logo'
import { NavMenu } from '../shared/NavMenu'
import { SearchBar } from '../shared/SearchBar'
import { ResumeUpload } from '../shared/ResumeUpload'
import { SOURCE_COLORS, SUPPORTED_BOARDS } from '../../lib/constants'

const STEPS = [
  {
    title: 'Search every board at once',
    body: 'One query fans out across LinkedIn, Indeed, Greenhouse, Lever and more — deduplicated into a single ranked list.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    ),
  },
  {
    title: 'AI scores & tailors your resume',
    body: 'Claude rates each role against your resume, then tailors your resume and drafts a cover letter for the ones you want to pursue.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
    ),
  },
  {
    title: 'Review, save, and apply',
    body: 'Nothing is ever submitted without your explicit approval. Review the tailored draft, save it for reference, then apply directly.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    ),
  },
]

const FEATURES = [
  {
    title: 'AI match scoring',
    body: 'Every job is rated against your resume so you spend time on roles that actually fit.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
    ),
    color: 'indigo',
  },
  {
    title: 'Tailored resume & cover letter',
    body: "Claude rewrites relevant sections of your resume and drafts a personalised cover letter — without inventing anything.",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    ),
    color: 'sky',
  },
  {
    title: 'Side-by-side diff review',
    body: 'See exactly what changed in your resume before you approve. Edit inline, compare versions, and export as PDF or DOCX.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
    ),
    color: 'violet',
  },
  {
    title: 'You stay in control',
    body: "The app never submits to a job board. Every application is saved in your account so you can apply yourself, whenever you're ready.",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    ),
    color: 'emerald',
  },
]

// Static lookup prevents Tailwind from purging dynamic class strings
const FEATURE_COLORS: Record<string, { bg: string; icon: string; ring: string }> = {
  indigo:  { bg: 'bg-indigo-50',  icon: 'text-indigo-600',  ring: 'ring-indigo-100' },
  sky:     { bg: 'bg-sky-50',     icon: 'text-sky-600',     ring: 'ring-sky-100' },
  violet:  { bg: 'bg-violet-50',  icon: 'text-violet-600',  ring: 'ring-violet-100' },
  emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-600', ring: 'ring-emerald-100' },
}

const STATS = [
  { value: '11', label: 'job boards searched' },
  { value: 'AI', label: 'match scoring per role' },
  { value: '100%', label: 'your data, your control' },
]

export function LandingPage() {
  return (
    <div className="min-h-full bg-slate-50">

      {/* Top nav */}
      <nav className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-5 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] backdrop-blur-sm">
        <Logo />
        <NavMenu />
      </nav>

      {/* Hero */}
      <header className="relative overflow-hidden">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none">
          <div className="absolute -top-24 left-1/4 h-80 w-[36rem] -translate-x-1/2 rounded-full bg-gradient-to-br from-indigo-300/30 via-sky-200/20 to-transparent blur-3xl" />
          <div className="absolute -top-10 right-0 h-64 w-80 rounded-full bg-gradient-to-bl from-violet-200/25 via-indigo-100/15 to-transparent blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-3xl px-5 pb-12 pt-16 text-center sm:pt-24">
          <span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3.5 py-1.5 text-[12px] font-semibold text-indigo-600">
            <span className="relative flex h-2 w-2" aria-hidden="true">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
            </span>
            AI-powered job search and application assistant
          </span>

          <h1 className="mt-5 text-[2.5rem] font-bold leading-[1.15] tracking-tight text-slate-900 sm:text-5xl">
            Find the right role,
            <br className="hidden sm:block" />
            <span className="bg-gradient-to-r from-indigo-600 via-indigo-500 to-sky-500 bg-clip-text text-transparent">
              {' '}tailored to&nbsp;you.
            </span>
          </h1>

          <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-slate-500">
            Search across&nbsp;11 job boards at once. Let AI score each match against your resume,
            tailor your application, and draft a cover letter — you stay in control of every&nbsp;submission.
          </p>

          <div className="mx-auto mt-9 max-w-2xl text-left">
            <SearchBar variant="hero" autoFocus />
          </div>

          <div className="mx-auto mt-5 max-w-md">
            <ResumeUpload variant="card" />
          </div>
        </div>
      </header>

      {/* Stats ribbon */}
      <div className="border-y border-slate-200 bg-white">
        <dl className="mx-auto grid max-w-4xl grid-cols-3 divide-x divide-slate-200 px-5">
          {STATS.map(({ value, label }) => (
            <div key={label} className="flex flex-col items-center py-5 text-center">
              <dt className="text-2xl font-extrabold tracking-tight text-indigo-600 sm:text-3xl">
                {value}
              </dt>
              <dd className="mt-0.5 text-[12px] font-medium text-slate-500">{label}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* How it works */}
      <section aria-labelledby="how-it-works" className="mx-auto max-w-5xl px-5 py-16">
        <div className="mb-10 text-center">
          <p id="how-it-works" className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
            How it works
          </p>
          <p className="mt-2 text-xl font-semibold text-slate-800">
            From search to saved application in three steps
          </p>
        </div>

        <ol className="relative grid gap-6 sm:grid-cols-3">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-[calc(16.67%+1.5rem)] right-[calc(16.67%+1.5rem)] top-[2.75rem] hidden h-px bg-slate-200 sm:block"
          />

          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="relative flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]"
            >
              <span
                aria-hidden="true"
                className="absolute right-5 top-5 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600 text-[11px] font-bold text-white"
              >
                {i + 1}
              </span>

              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
                  {step.icon}
                </svg>
              </div>

              <h3 className="text-[15px] font-semibold text-slate-900">{step.title}</h3>
              <p className="mt-2 text-[13px] leading-relaxed text-slate-500">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Feature highlights */}
      <section aria-labelledby="features-heading" className="border-t border-slate-200 bg-white py-16">
        <div className="mx-auto max-w-5xl px-5">
          <div className="mb-10 text-center">
            <p id="features-heading" className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
              What you get
            </p>
            <p className="mt-2 text-xl font-semibold text-slate-800">
              Everything you need to apply with confidence
            </p>
          </div>

          <ul className="grid gap-5 sm:grid-cols-2">
            {FEATURES.map(({ title, body, icon, color }) => {
              const c = FEATURE_COLORS[color]
              return (
                <li
                  key={title}
                  className="flex gap-4 rounded-2xl border border-slate-100 bg-slate-50/60 p-5 transition hover:border-slate-200 hover:bg-white hover:shadow-[0_2px_8px_0_rgb(0_0_0_/_0.05)]"
                >
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset ${c.bg} ${c.ring}`}>
                    <svg className={`h-5 w-5 ${c.icon}`} fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
                      {icon}
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-[14px] font-semibold text-slate-900">{title}</h3>
                    <p className="mt-1 text-[13px] leading-relaxed text-slate-500">{body}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </section>

      {/* Supported boards */}
      <section aria-label="Supported job boards" className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto max-w-5xl px-5 py-10 text-center">
          <p className="mb-5 text-[11px] font-bold uppercase tracking-widest text-slate-400">
            Sourcing jobs from
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {SUPPORTED_BOARDS.map((board) => (
              <span
                key={board.key}
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-[12px] font-medium text-slate-600 shadow-[0_1px_2px_0_rgb(0_0_0_/_0.04)] transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
              >
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${SOURCE_COLORS[board.key] ?? 'bg-slate-400'}`} aria-hidden="true" />
                {board.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center">
        <p className="text-[12px] text-slate-400">
          Built with{' '}
          <span className="font-medium text-slate-500">Claude AI</span>
          {' '}·  All data stays in your account · No applications are submitted on your behalf
        </p>
      </footer>

    </div>
  )
}
