import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { SalaryStat, InsightsRegion } from '../../types'
import { getSalary } from '../../api/insights'
import { formatSalary } from './currencyUtils'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { EmptyState } from '../shared/EmptyState'

interface SalaryTableProps {
  salaries: SalaryStat[]
  region: InsightsRegion
}

export function SalaryTable({ salaries, region }: SalaryTableProps) {
  const [roleInput, setRoleInput] = useState('')
  const [searchRole, setSearchRole] = useState('')

  const {
    data: searchResult,
    isFetching: isSearching,
    error: searchError,
    refetch,
  } = useQuery({
    queryKey: ['insights-salary', searchRole, region],
    queryFn: () => getSalary(searchRole, region),
    enabled: searchRole.trim().length > 0,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = roleInput.trim()
    if (!trimmed) return
    if (trimmed === searchRole) {
      refetch()
    } else {
      setSearchRole(trimmed)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Role search */}
      <form onSubmit={handleSearch} className="flex gap-2" aria-label="Search salary for a specific role">
        <div className="relative flex-1">
          <label htmlFor="salary-role-input" className="sr-only">Job role</label>
          <input
            id="salary-role-input"
            type="text"
            value={roleInput}
            onChange={(e) => setRoleInput(e.target.value)}
            placeholder="Search any role, e.g. Data Engineer…"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[14px] text-slate-800 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        </div>
        <button
          type="submit"
          disabled={!roleInput.trim()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Look up
        </button>
      </form>

      {/* Inline search result */}
      {searchRole && (
        <div className="rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-3">
          {isSearching ? (
            <LoadingSpinner label="Fetching salary data…" size="sm" />
          ) : searchError ? (
            <p className="text-sm text-red-600">Could not fetch salary — try again.</p>
          ) : searchResult ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[13px] font-semibold text-slate-700">{searchResult.role}</span>
              <span className="text-[20px] font-bold text-indigo-700">
                {formatSalary(searchResult.median, region, searchResult.currency)}
              </span>
              {searchResult.median == null && (
                <span className="text-[12px] text-slate-500">No salary data available for this role.</span>
              )}
              {searchResult.sample_size > 0 && (
                <span className="text-[12px] text-slate-500">
                  Based on {searchResult.sample_size.toLocaleString()} postings
                </span>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Default salary table */}
      {salaries.length === 0 ? (
        <EmptyState
          title="No salary data"
          description="Salary benchmarks are unavailable right now. Try a different region or check back later."
          icon={
            <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm" aria-label="Median salary by role">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th scope="col" className="px-4 py-3 text-left text-[12px] font-semibold uppercase tracking-wide text-slate-500">
                  Role
                </th>
                <th scope="col" className="px-4 py-3 text-right text-[12px] font-semibold uppercase tracking-wide text-slate-500">
                  Median salary
                </th>
                <th scope="col" className="hidden px-4 py-3 text-right text-[12px] font-semibold uppercase tracking-wide text-slate-500 sm:table-cell">
                  Sample size
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {salaries.map((row) => (
                <tr key={row.role} className="transition hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{row.role}</td>
                  <td className="px-4 py-3 text-right font-semibold text-indigo-700">
                    {formatSalary(row.median, region, row.currency)}
                  </td>
                  <td className="hidden px-4 py-3 text-right text-slate-500 sm:table-cell">
                    {row.sample_size > 0 ? row.sample_size.toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
