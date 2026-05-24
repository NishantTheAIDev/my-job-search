import { useState } from 'react'

interface ResultsFilterPanelProps {
  sources: string[]
  companies: string[]
  selectedSources: string[]
  selectedCompanies: string[]
  onSourceChange: (sources: string[]) => void
  onCompanyChange: (companies: string[]) => void
}

// Per-source brand colors: a small left-border dot rendered as an inline span.
const SOURCE_COLORS: Record<string, string> = {
  adzuna: 'bg-blue-500',
  greenhouse: 'bg-green-500',
  lever: 'bg-purple-500',
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const COMPANY_INITIAL_LIMIT = 8

export function ResultsFilterPanel({
  sources,
  companies,
  selectedSources,
  selectedCompanies,
  onSourceChange,
  onCompanyChange,
}: ResultsFilterPanelProps) {
  const [companiesExpanded, setCompaniesExpanded] = useState(false)

  const activeCount = selectedSources.length + selectedCompanies.length
  const hasActiveFilters = activeCount > 0

  function toggleSource(source: string) {
    if (selectedSources.includes(source)) {
      onSourceChange(selectedSources.filter((s) => s !== source))
    } else {
      onSourceChange([...selectedSources, source])
    }
  }

  function toggleCompany(company: string) {
    if (selectedCompanies.includes(company)) {
      onCompanyChange(selectedCompanies.filter((c) => c !== company))
    } else {
      onCompanyChange([...selectedCompanies, company])
    }
  }

  function clearAll() {
    onSourceChange([])
    onCompanyChange([])
  }

  const visibleCompanies =
    companies.length > COMPANY_INITIAL_LIMIT && !companiesExpanded
      ? companies.slice(0, COMPANY_INITIAL_LIMIT)
      : companies

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm"
      aria-label="Filter results"
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-800">
          Filters
          {hasActiveFilters && (
            <span
              className="ml-1.5 inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700"
              aria-label={`${activeCount} active filter${activeCount !== 1 ? 's' : ''}`}
            >
              {activeCount}
            </span>
          )}
        </h2>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearAll}
            className="text-xs text-blue-600 hover:text-blue-800 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded"
          >
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-col gap-4">
        {/* Sources section */}
        {sources.length > 0 && (
          <fieldset>
            <legend className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
              Source
            </legend>
            <div className="flex flex-col gap-1.5">
              {sources.map((source) => {
                const isSelected = selectedSources.includes(source)
                const dotColor = SOURCE_COLORS[source.toLowerCase()] ?? 'bg-gray-400'
                const inputId = `filter-source-${source}`
                return (
                  <label
                    key={source}
                    htmlFor={inputId}
                    className="flex cursor-pointer items-center gap-2 text-xs text-gray-700"
                  >
                    <input
                      id={inputId}
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSource(source)}
                      className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span
                      className={`inline-block h-2 w-2 shrink-0 rounded-full ${dotColor}`}
                      aria-hidden="true"
                    />
                    <span className={isSelected ? 'font-medium text-gray-900' : ''}>
                      {capitalize(source)}
                    </span>
                  </label>
                )
              })}
            </div>
          </fieldset>
        )}

        {/* Companies section */}
        {companies.length > 0 && (
          <fieldset>
            <legend className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
              Company
            </legend>
            <div className="flex flex-col gap-1.5">
              {visibleCompanies.map((company) => {
                const isSelected = selectedCompanies.includes(company)
                const inputId = `filter-company-${company}`
                return (
                  <label
                    key={company}
                    htmlFor={inputId}
                    className="flex cursor-pointer items-center gap-2 text-xs text-gray-700"
                  >
                    <input
                      id={inputId}
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleCompany(company)}
                      className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className={isSelected ? 'font-medium text-gray-900' : ''}>
                      {company}
                    </span>
                  </label>
                )
              })}
            </div>
            {companies.length > COMPANY_INITIAL_LIMIT && (
              <button
                type="button"
                onClick={() => setCompaniesExpanded((prev) => !prev)}
                className="mt-2 text-xs text-blue-600 hover:text-blue-800 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded"
                aria-expanded={companiesExpanded}
              >
                {companiesExpanded
                  ? 'Show fewer'
                  : `Show all (${companies.length})`}
              </button>
            )}
          </fieldset>
        )}
      </div>
    </div>
  )
}
