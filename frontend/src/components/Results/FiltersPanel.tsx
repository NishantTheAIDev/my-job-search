import { useState } from 'react'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { SOURCE_COLORS } from '../../lib/constants'
import type { JobFiltersResponse } from '../../types'

interface FiltersPanelProps {
  filtersData: JobFiltersResponse | null
}

const COMPANY_INITIAL_LIMIT = 8

export function FiltersPanel({ filtersData }: FiltersPanelProps) {
  const selectedSources = useJobSearchStore((s) => s.selectedSources)
  const setSelectedSources = useJobSearchStore((s) => s.setSelectedSources)
  const selectedCompanies = useJobSearchStore((s) => s.selectedCompanies)
  const setSelectedCompanies = useJobSearchStore((s) => s.setSelectedCompanies)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)

  const [companiesExpanded, setCompaniesExpanded] = useState(false)

  function toggleSource(source: string) {
    const next = selectedSources.includes(source)
      ? selectedSources.filter((s) => s !== source)
      : [...selectedSources, source]
    setSelectedSources(next)
    setCriteria({ page: 1 })
  }

  function toggleCompany(company: string) {
    const next = selectedCompanies.includes(company)
      ? selectedCompanies.filter((c) => c !== company)
      : [...selectedCompanies, company]
    setSelectedCompanies(next)
    setCriteria({ page: 1 })
  }

  const activeFilterCount = selectedSources.length + selectedCompanies.length
  const showSources = filtersData != null && filtersData.sources.length >= 2
  const showCompanies = filtersData != null && filtersData.companies.length > 0
  const visibleCompanies =
    filtersData && filtersData.companies.length > COMPANY_INITIAL_LIMIT && !companiesExpanded
      ? filtersData.companies.slice(0, COMPANY_INITIAL_LIMIT)
      : filtersData?.companies ?? []

  if (!showSources && !showCompanies) return null

  return (
    <div className="flex flex-col">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Filters</p>
          {activeFilterCount > 0 && (
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
              {activeFilterCount}
            </span>
          )}
        </div>
        {activeFilterCount > 0 && (
          <button
            onClick={() => { setSelectedSources([]); setSelectedCompanies([]); setCriteria({ page: 1 }) }}
            className="text-[11px] font-medium text-indigo-500 hover:text-indigo-700 focus:outline-none focus:underline"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="space-y-5">
        {showSources && (
          <fieldset>
            <legend className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-slate-400">Source</legend>
            <div className="flex flex-wrap gap-1.5">
              {filtersData!.sources.map((source) => {
                const dotColor = SOURCE_COLORS[source.toLowerCase()] ?? 'bg-slate-400'
                const isActive = selectedSources.includes(source)
                return (
                  <label
                    key={source}
                    className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
                      isActive
                        ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-300 hover:text-indigo-600'
                    }`}
                  >
                    <input type="checkbox" checked={isActive} onChange={() => toggleSource(source)} className="sr-only" />
                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} aria-hidden="true" />
                    {source.charAt(0).toUpperCase() + source.slice(1)}
                  </label>
                )
              })}
            </div>
          </fieldset>
        )}

        {showCompanies && (
          <fieldset>
            <legend className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-slate-400">Company</legend>
            <div className="space-y-1.5">
              {visibleCompanies.map((company) => {
                const isActive = selectedCompanies.includes(company)
                return (
                  <label key={company} className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 hover:bg-slate-50">
                    <div className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition ${
                      isActive ? 'border-indigo-500 bg-indigo-500 text-white' : 'border-slate-300 bg-white'
                    }`}>
                      {isActive && (
                        <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M1.5 5l2.5 2.5 5-5" />
                        </svg>
                      )}
                      <input type="checkbox" checked={isActive} onChange={() => toggleCompany(company)} className="sr-only" aria-label={company} />
                    </div>
                    <span className={`text-[12px] ${isActive ? 'font-semibold text-slate-800' : 'text-slate-600'}`}>{company}</span>
                  </label>
                )
              })}
            </div>
            {filtersData!.companies.length > COMPANY_INITIAL_LIMIT && (
              <button
                type="button"
                onClick={() => setCompaniesExpanded((v) => !v)}
                className="mt-2 flex items-center gap-1 text-[11px] font-medium text-indigo-500 hover:text-indigo-700 focus:outline-none focus:underline"
                aria-expanded={companiesExpanded}
              >
                {companiesExpanded ? 'Show fewer' : `Show all (${filtersData!.companies.length})`}
              </button>
            )}
          </fieldset>
        )}
      </div>
    </div>
  )
}
