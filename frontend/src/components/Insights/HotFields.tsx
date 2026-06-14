import type { HotField, InsightsRegion } from '../../types'
import { formatSalary, formatNumber } from './currencyUtils'
import { EmptyState } from '../shared/EmptyState'

interface HotFieldsProps {
  fields: HotField[]
  region: InsightsRegion
}

export function HotFields({ fields, region }: HotFieldsProps) {
  if (fields.length === 0) {
    return (
      <EmptyState
        title="No field data"
        description="Hottest fields data is unavailable right now. Try a different region or check back later."
        icon={
          <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
          </svg>
        }
      />
    )
  }

  const maxOpenings = Math.max(...fields.map((f) => f.openings), 1)

  return (
    <ol className="flex flex-col gap-3" aria-label="Hottest job fields ranked by openings">
      {fields.map((field, idx) => {
        const barPct = Math.max((field.openings / maxOpenings) * 100, 2)
        return (
          <li
            key={field.tag}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                {/* Rank badge */}
                <span
                  aria-hidden="true"
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-[11px] font-bold text-indigo-600"
                >
                  {idx + 1}
                </span>
                <span className="truncate text-[14px] font-semibold text-slate-900">{field.label}</span>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-0.5">
                <span className="text-[13px] font-bold text-slate-800">
                  {formatNumber(field.openings)} openings
                </span>
                {field.mean_salary != null && (
                  <span className="text-[12px] text-slate-500">
                    avg {formatSalary(field.mean_salary, region, field.currency)}
                  </span>
                )}
              </div>
            </div>

            {/* Bar chart — openings proportional to max */}
            <div
              className="h-2 overflow-hidden rounded-full bg-slate-100"
              role="img"
              aria-label={`${field.label}: ${formatNumber(field.openings)} openings, ${Math.round(barPct)}% of top field`}
            >
              <div
                className="h-full rounded-full bg-indigo-500 transition-all duration-500"
                style={{ width: `${barPct}%` }}
              />
            </div>
          </li>
        )
      })}
    </ol>
  )
}
