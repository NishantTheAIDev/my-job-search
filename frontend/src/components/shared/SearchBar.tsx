import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createSearch } from '../../api/search'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import {
  POSTED_WITHIN_OPTIONS,
  parseCriteriaFromUrl,
  syncCriteriaToUrl,
} from '../../lib/constants'

interface SearchBarProps {
  variant: 'hero' | 'compact'
  autoFocus?: boolean
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    </svg>
  )
}

function PinIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M8 1.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM2 6a6 6 0 1 1 10.89 3.477l3.817 3.816a.75.75 0 0 1-1.06 1.061l-3.816-3.816A6 6 0 0 1 2 6Z" clipRule="evenodd" />
    </svg>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className ?? ''}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
    </svg>
  )
}

function RemoteToggle({ size }: { size: 'sm' | 'md' }) {
  const remoteOnly = useJobSearchStore((s) => s.criteria.remote_only ?? false)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const track = size === 'md' ? 'h-5 w-9' : 'h-4 w-7'
  const knob = size === 'md' ? 'h-4 w-4 peer-checked:translate-x-4' : 'h-3 w-3 peer-checked:translate-x-3'
  return (
    <label className="flex shrink-0 cursor-pointer items-center gap-2">
      <div className="relative">
        <input
          type="checkbox"
          checked={remoteOnly}
          onChange={(e) => setCriteria({ remote_only: e.target.checked })}
          className="peer sr-only"
          id="remote-only-toggle"
        />
        <div className={`${track} rounded-full bg-slate-200 transition peer-checked:bg-indigo-500 peer-focus-visible:ring-2 peer-focus-visible:ring-indigo-500 peer-focus-visible:ring-offset-1`} />
        <div className={`absolute left-0.5 top-0.5 ${knob} rounded-full bg-white shadow transition`} />
      </div>
      <span className="text-[13px] font-medium text-slate-600" id="remote-only-label">Remote only</span>
    </label>
  )
}

export function SearchBar({ variant, autoFocus = false }: SearchBarProps) {
  const criteria = useJobSearchStore((s) => s.criteria)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const setActiveSearchJob = useJobSearchStore((s) => s.setActiveSearchJob)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)
  const setSelectedSources = useJobSearchStore((s) => s.setSelectedSources)
  const setSelectedCompanies = useJobSearchStore((s) => s.setSelectedCompanies)
  const setActiveSavedSearchId = useJobSearchStore((s) => s.setActiveSavedSearchId)
  const setLastSearchCached = useJobSearchStore((s) => s.setLastSearchCached)

  const [localQuery, setLocalQuery] = useState(criteria.query)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hydratedRef = useRef(false)

  // On first mount, hydrate criteria from URL so a shared/refreshed search survives.
  useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    const fromUrl = parseCriteriaFromUrl()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (fromUrl.query) setLocalQuery(fromUrl.query)
    setCriteria(fromUrl)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setCriteria({ query: localQuery }), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [localQuery, setCriteria])

  useEffect(() => { syncCriteriaToUrl(criteria) }, [criteria])

  const searchMutation = useMutation({
    mutationFn: (criteria: Parameters<typeof createSearch>[0]) => createSearch(criteria),
    onSuccess: (data) => {
      // Ad-hoc search — not tied to a saved search, so clear any "new" badge context.
      setActiveSavedSearchId(null)
      setActiveSearchJob(data.job_id)
      setSelectedJob(null)
      setSelectedSources([])
      setSelectedCompanies([])
      setLastSearchCached(data.cached ?? false)
    },
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const query = localQuery.trim()
    if (!query) return
    searchMutation.mutate({ ...criteria, query, page: 1 })
  }

  const disabled = searchMutation.isPending || !localQuery.trim()

  if (variant === 'compact') {
    return (
      <form onSubmit={handleSearch} aria-label="Job search" className="flex flex-1 items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Job title or keywords…"
            aria-label="Job title or keywords"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-[13px] text-slate-800 placeholder:text-slate-400 transition focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        </div>
        <div className="relative hidden w-44 sm:block">
          <PinIcon className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={criteria.location ?? ''}
            onChange={(e) => setCriteria({ location: e.target.value || undefined })}
            placeholder="Location"
            aria-label="Location"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-[13px] text-slate-800 placeholder:text-slate-400 transition focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        </div>
        <div className="hidden lg:block"><RemoteToggle size="sm" /></div>
        <button
          type="submit"
          disabled={disabled}
          aria-busy={searchMutation.isPending}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {searchMutation.isPending && <Spinner className="h-4 w-4" />}
          <span className="hidden sm:inline">Search</span>
          {/* On the narrowest viewports the label is hidden, so keep an icon for affordance. */}
          {!searchMutation.isPending && <SearchIcon className="h-4 w-4 sm:hidden" />}
        </button>
      </form>
    )
  }

  // hero
  return (
    <form onSubmit={handleSearch} aria-label="Job search" className="w-full">
      <div className="rounded-2xl border border-slate-200 bg-white p-2.5 shadow-[0_8px_30px_-12px_rgb(0_0_0_/_0.18)]">
        <div className="flex flex-col gap-2 md:flex-row md:items-center">
          <div className="relative flex-1">
            <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              placeholder="Job title, skills, or keywords…"
              aria-label="Job title or keywords"
              autoFocus={autoFocus}
              className="w-full rounded-xl border border-transparent bg-slate-50 py-3.5 pl-11 pr-3 text-[15px] text-slate-900 placeholder:text-slate-400 transition focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>
          <div className="relative md:w-56">
            <PinIcon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={criteria.location ?? ''}
              onChange={(e) => setCriteria({ location: e.target.value || undefined })}
              placeholder="Location"
              aria-label="Location"
              className="w-full rounded-xl border border-transparent bg-slate-50 py-3.5 pl-10 pr-3 text-[15px] text-slate-900 placeholder:text-slate-400 transition focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>
          <button
            type="submit"
            disabled={disabled}
            aria-busy={searchMutation.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-7 py-3.5 text-[15px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {searchMutation.isPending ? <Spinner className="h-5 w-5" /> : <SearchIcon className="h-5 w-5" />}
            Search
          </button>
        </div>
      </div>

      {/* Secondary controls */}
      <div className="mt-3.5 flex flex-wrap items-center gap-x-5 gap-y-2 px-1">
        <RemoteToggle size="md" />
        <label className="flex items-center gap-2 text-[13px] font-medium text-slate-600">
          Posted
          <select
            value={criteria.posted_within_days?.toString() ?? ''}
            onChange={(e) => setCriteria({ posted_within_days: e.target.value ? parseInt(e.target.value, 10) : undefined })}
            aria-label="Posted within"
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] text-slate-700 transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          >
            {POSTED_WITHIN_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      </div>

      {searchMutation.isError && (
        <p role="alert" className="mt-3 text-[13px] text-red-500">Search failed. Please try again.</p>
      )}
    </form>
  )
}
