import type { NewsItem } from '../../types'
import { parseGdeltDate } from './currencyUtils'
import { EmptyState } from '../shared/EmptyState'

interface MarketNewsProps {
  news: NewsItem[]
}

// Defense-in-depth against javascript:/data: URIs from untrusted news sources
// (the backend also filters, see services/insights/news.py::_is_safe_url).
function isSafeUrl(url: string): boolean {
  return /^https?:\/\//i.test(url)
}

export function MarketNews({ news }: MarketNewsProps) {
  if (news.length === 0) {
    return (
      <EmptyState
        title="No news available"
        description="Market news could not be loaded right now. Check back later."
        icon={
          <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 0 0 2.25 2.25h13.5M6 7.5h3v3H6v-3Z" />
          </svg>
        }
      />
    )
  }

  return (
    <ul className="flex flex-col gap-3" aria-label="Market news articles">
      {news.map((item, idx) => (
        <li key={idx} className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)] transition hover:border-slate-300 hover:shadow-[0_2px_6px_0_rgb(0_0_0_/_0.06)]">
          {isSafeUrl(item.url) ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 rounded-lg"
              aria-label={`${item.title} (opens in new tab)`}
            >
              <p className="text-[14px] font-semibold leading-snug text-slate-900 group-hover:text-indigo-600">
                {item.title}
                {/* External link indicator — visible to screen readers */}
                <span className="sr-only"> (external link)</span>
                <svg
                  className="ml-1 inline-block h-3.5 w-3.5 shrink-0 text-slate-400 group-hover:text-indigo-500"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
              </p>
            </a>
          ) : (
            <p className="text-[14px] font-semibold leading-snug text-slate-900">{item.title}</p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <span className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
              {item.domain}
            </span>
            <span className="text-[11px] text-slate-400" aria-label={`Published ${parseGdeltDate(item.seendate)}`}>
              {parseGdeltDate(item.seendate)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  )
}
