import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { getInsights } from '../../api/insights'
import type { InsightsRegion } from '../../types'
import { ErrorBanner } from '../shared/ErrorBanner'
import { Logo } from '../shared/Logo'
import { MarketNews } from './MarketNews'
import { SalaryTable } from './SalaryTable'
import { HotFields } from './HotFields'
import { HiringTrends } from './HiringTrends'

// ── Region config ─────────────────────────────────────────────────────────────

interface RegionOption {
  value: InsightsRegion
  label: string
  flag: string
}

const REGIONS: RegionOption[] = [
  { value: 'in', label: 'India', flag: '🇮🇳' },
  { value: 'us', label: 'United States', flag: '🇺🇸' },
  { value: 'gb', label: 'United Kingdom', flag: '🇬🇧' },
  { value: 'world', label: 'Worldwide', flag: '🌍' },
]

// ── Skeleton for loading ──────────────────────────────────────────────────────

function InsightsSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-hidden="true">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-5 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]">
          <div className="mb-4 h-4 w-32 rounded bg-slate-200 animate-pulse" />
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((j) => (
              <div key={j} className="h-10 rounded-lg bg-slate-100 animate-pulse" style={{ width: `${70 + j * 8}%` }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Section card wrapper ──────────────────────────────────────────────────────

interface SectionProps {
  id: string
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}

function Section({ id, title, icon, children }: SectionProps) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="flex items-center gap-2 text-[16px] font-bold text-slate-900">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600" aria-hidden="true">
          {icon}
        </span>
        {title}
      </h2>
      {children}
    </section>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function InsightsPage() {
  const setShowInsights = useJobSearchStore((s) => s.setShowInsights)
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const [region, setRegion] = useState<InsightsRegion>('in')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['insights', region],
    queryFn: () => getInsights(region),
    staleTime: 60 * 60 * 1000, // 1 hour — backend caches ~24h, keep client fresh
    retry: 2,
  })

  function handleBack() {
    setShowInsights(false)
  }

  // Parse generated_at for a readable caption
  const generatedAt = data?.generated_at
    ? (() => {
        try {
          return new Date(data.generated_at).toLocaleString('en-GB', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })
        } catch {
          return data.generated_at
        }
      })()
    : null

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Top nav */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
        <div className="hidden shrink-0 md:block">
          <Logo />
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          {/* Page title */}
          <div className="flex min-w-0 flex-col">
            <span className="text-[15px] font-semibold leading-tight text-slate-900">Market Insights</span>
            {generatedAt && (
              <span className="text-[11px] text-slate-400">Updated {generatedAt}</span>
            )}
          </div>
        </div>

        {/* Region selector */}
        <div className="flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-0.5" role="group" aria-label="Select region">
          {REGIONS.map((r) => (
            <button
              key={r.value}
              onClick={() => setRegion(r.value)}
              aria-pressed={region === r.value}
              aria-label={r.label}
              className={`rounded-md px-2.5 py-1.5 text-[12px] font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                region === r.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <span aria-hidden="true">{r.flag}</span>
              <span className="ml-1 hidden sm:inline">{r.label}</span>
            </button>
          ))}
        </div>

        {/* Back button */}
        <button
          onClick={handleBack}
          aria-label={activeSearchJobId ? 'Back to results' : 'Back to home'}
          className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {activeSearchJobId ? 'Back to results' : 'Back to home'}
        </button>

        {/* Mobile back button (icon only) */}
        <button
          onClick={handleBack}
          aria-label={activeSearchJobId ? 'Back to results' : 'Back to home'}
          className="flex shrink-0 items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:hidden"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
        </button>
      </header>

      {/* Page body */}
      <main id="insights-main" className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
          {isLoading ? (
            <InsightsSkeleton />
          ) : error ? (
            <div className="py-6">
              <ErrorBanner
                message="Could not load market insights. Please check your connection and try again."
                onRetry={() => refetch()}
              />
            </div>
          ) : data ? (
            <div className="flex flex-col gap-10">
              {/* Market News */}
              <Section
                id="news-heading"
                title="Market News"
                icon={
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 0 0 2.25 2.25h13.5M6 7.5h3v3H6v-3Z" />
                  </svg>
                }
              >
                <MarketNews news={data.news} />
              </Section>

              {/* Hottest Fields */}
              <Section
                id="hotfields-heading"
                title="Hottest Fields"
                icon={
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 0 1-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 0 0 6.16-12.12A14.98 14.98 0 0 0 9.631 8.41m5.96 5.96a14.926 14.926 0 0 1-5.841 2.58m-.119-8.54a6 6 0 0 0-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 0 0-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 0 1-2.448-2.448 14.9 14.9 0 0 1 .06-.312m-2.24 2.39a4.493 4.493 0 0 0-1.757 4.306 4.493 4.493 0 0 0 4.306-1.758M16.5 9a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z" />
                  </svg>
                }
              >
                <HotFields fields={data.hottest_fields} region={region} />
              </Section>

              {/* Salary Benchmarks */}
              <Section
                id="salary-heading"
                title="Salary Benchmarks"
                icon={
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                }
              >
                <SalaryTable salaries={data.salaries} region={region} />
              </Section>

              {/* Hiring Trends */}
              <Section
                id="trends-heading"
                title="Hiring Trends"
                icon={
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
                  </svg>
                }
              >
                <HiringTrends trends={data.trends} region={region} />
              </Section>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  )
}
