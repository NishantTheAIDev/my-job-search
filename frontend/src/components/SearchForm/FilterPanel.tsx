import type { SearchCriteria } from '../../types'

interface FilterPanelProps {
  criteria: SearchCriteria
  onChange: (updates: Partial<SearchCriteria>) => void
  disabled?: boolean
}

const POSTED_WITHIN_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
]

export function FilterPanel({ criteria, onChange, disabled }: FilterPanelProps) {
  return (
    <fieldset disabled={disabled} className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-2">
      <legend className="sr-only">Search filters</legend>

      <div className="flex flex-col gap-1">
        <label htmlFor="filter-location" className="text-xs font-medium text-gray-600 uppercase tracking-wide">
          Location
        </label>
        <input
          id="filter-location"
          type="text"
          value={criteria.location ?? ''}
          onChange={(e) => onChange({ location: e.target.value || undefined })}
          placeholder="City, state, or remote"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:opacity-50"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="filter-posted-within" className="text-xs font-medium text-gray-600 uppercase tracking-wide">
          Posted within
        </label>
        <select
          id="filter-posted-within"
          value={criteria.posted_within_days?.toString() ?? ''}
          onChange={(e) =>
            onChange({ posted_within_days: e.target.value ? parseInt(e.target.value, 10) : undefined })
          }
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:opacity-50"
        >
          {POSTED_WITHIN_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </fieldset>
  )
}
