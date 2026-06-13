import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createSearch } from '../../api/search'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { FilterPanel } from './FilterPanel'
import type { SearchCriteria } from '../../types'

function syncCriteriaToUrl(criteria: SearchCriteria) {
  const params = new URLSearchParams()
  if (criteria.query) params.set('q', criteria.query)
  if (criteria.location) params.set('location', criteria.location)
  if (criteria.remote_only) params.set('remote', '1')
  if (criteria.posted_within_days) params.set('posted', String(criteria.posted_within_days))
  const search = params.toString()
  window.history.replaceState(null, '', search ? `?${search}` : window.location.pathname)
}

function parseCriteriaFromUrl(): Partial<SearchCriteria> {
  const params = new URLSearchParams(window.location.search)
  return {
    query: params.get('q') ?? '',
    location: params.get('location') ?? undefined,
    remote_only: params.get('remote') === '1',
    posted_within_days: params.get('posted') ? parseInt(params.get('posted')!, 10) : undefined,
  }
}

export function SearchForm() {
  const criteria = useJobSearchStore((s) => s.criteria)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const setActiveSearchJob = useJobSearchStore((s) => s.setActiveSearchJob)

  const [localQuery, setLocalQuery] = useState(criteria.query)
  const [showFilters, setShowFilters] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Restore state from URL on mount
  useEffect(() => {
    const fromUrl = parseCriteriaFromUrl()
    if (fromUrl.query) setLocalQuery(fromUrl.query)
    setCriteria(fromUrl)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Debounce query input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setCriteria({ query: localQuery })
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [localQuery, setCriteria])

  // Sync all criteria to URL
  useEffect(() => {
    syncCriteriaToUrl(criteria)
  }, [criteria])

  const searchMutation = useMutation({
    mutationFn: createSearch,
    onSuccess: (data) => {
      setActiveSearchJob(data.job_id)
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!criteria.query.trim()) return
    searchMutation.mutate({ ...criteria, page: 1 })
  }

  function handleFilterChange(updates: Partial<SearchCriteria>) {
    setCriteria(updates)
  }

  const isSearching = searchMutation.isPending

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Job search"
      className="mx-auto mb-6 w-full max-w-3xl rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      {/* Main search row */}
      <div className="flex gap-2">
        <div className="flex-1">
          <label htmlFor="search-query" className="sr-only">
            Job title, role, or keywords
          </label>
          <input
            id="search-query"
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Job title, role, or keywords"
            required
            disabled={isSearching}
            aria-required="true"
            aria-describedby={searchMutation.isError ? 'search-error' : undefined}
            className="w-full rounded-md border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:opacity-50"
          />
        </div>

        {/* Remote-only toggle */}
        <div className="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-2">
          <input
            type="checkbox"
            id="remote-only"
            checked={criteria.remote_only ?? false}
            onChange={(e) => setCriteria({ remote_only: e.target.checked })}
            disabled={isSearching}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <label htmlFor="remote-only" className="cursor-pointer select-none text-sm text-gray-700 whitespace-nowrap">
            Remote only
          </label>
        </div>

        <button
          type="submit"
          disabled={isSearching || !criteria.query.trim()}
          aria-busy={isSearching}
          className="rounded-md bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSearching ? 'Searching...' : 'Search'}
        </button>
      </div>

      {/* Filters toggle */}
      <div className="mt-3">
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          aria-expanded={showFilters}
          aria-controls="filter-panel"
          className="flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700 focus:outline-none focus:underline"
        >
          <span aria-hidden="true">{showFilters ? '▲' : '▼'}</span>
          {showFilters ? 'Hide filters' : 'Show filters'}
        </button>
      </div>

      {showFilters && (
        <div id="filter-panel" className="mt-4 border-t border-gray-100 pt-4">
          <FilterPanel criteria={criteria} onChange={handleFilterChange} disabled={isSearching} />
        </div>
      )}

      {searchMutation.isError && (
        <p id="search-error" role="alert" className="mt-3 text-sm text-red-600">
          Search failed. Please try again.
        </p>
      )}
    </form>
  )
}
