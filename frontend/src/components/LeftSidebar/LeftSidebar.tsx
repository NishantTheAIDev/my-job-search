import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadResume } from '../../api/resume'
import { createSearch } from '../../api/search'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import type { JobFiltersResponse, SearchCriteria } from '../../types'

interface LeftSidebarProps {
  filtersData: JobFiltersResponse | null
}

const POSTED_WITHIN_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
]

const SOURCE_COLORS: Record<string, string> = {
  adzuna: 'bg-blue-500',
  greenhouse: 'bg-emerald-500',
  lever: 'bg-purple-500',
  linkedin: 'bg-sky-500',
  indeed: 'bg-blue-700',
  jsearch: 'bg-indigo-500',
  remotive: 'bg-teal-500',
  themuse: 'bg-rose-500',
  arbeitnow: 'bg-orange-500',
  jobicy: 'bg-green-500',
  weworkremotely: 'bg-cyan-600',
}

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

const COMPANY_INITIAL_LIMIT = 8

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
      {children}
    </p>
  )
}

export function LeftSidebar({ filtersData }: LeftSidebarProps) {
  const criteria = useJobSearchStore((s) => s.criteria)
  const setCriteria = useJobSearchStore((s) => s.setCriteria)
  const setActiveSearchJob = useJobSearchStore((s) => s.setActiveSearchJob)
  const resumeUploaded = useJobSearchStore((s) => s.resumeUploaded)
  const setResumeUploaded = useJobSearchStore((s) => s.setResumeUploaded)
  const selectedSources = useJobSearchStore((s) => s.selectedSources)
  const setSelectedSources = useJobSearchStore((s) => s.setSelectedSources)
  const selectedCompanies = useJobSearchStore((s) => s.selectedCompanies)
  const setSelectedCompanies = useJobSearchStore((s) => s.setSelectedCompanies)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)

  const queryClient = useQueryClient()
  const [localQuery, setLocalQuery] = useState(criteria.query)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [companiesExpanded, setCompaniesExpanded] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const fromUrl = parseCriteriaFromUrl()
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
    mutationFn: createSearch,
    onSuccess: (data) => {
      setActiveSearchJob(data.job_id)
      setSelectedJob(null)
      setSelectedSources([])
      setSelectedCompanies([])
      setCompaniesExpanded(false)
    },
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!criteria.query.trim()) return
    searchMutation.mutate({ ...criteria, page: 1 })
  }

  const uploadMutation = useMutation({
    mutationFn: uploadResume,
    onSuccess: () => {
      setResumeUploaded(true)
      setUploadError(null)
      queryClient.invalidateQueries({ queryKey: ['resume'] })
    },
    onError: () => {
      setUploadError('Upload failed. Please check the file and try again.')
    },
  })
  const isUploading = uploadMutation.isPending

  function handleUpload() {
    if (!selectedFile) { setUploadError('Please select a file first.'); return }
    setUploadError(null)
    uploadMutation.mutate(selectedFile)
  }

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

  /* ---- Shared input/control styles ---- */
  const inputBase =
    'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-slate-800 placeholder:text-slate-400 transition focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20'

  return (
    <div className="flex flex-col">

      {/* ---- Resume section ---- */}
      <div className="px-4 py-4 border-b border-slate-100">
        {!resumeUploaded ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4">
            <p className="mb-0.5 text-[13px] font-semibold text-slate-700">Upload your resume</p>
            <p className="mb-3 text-[11px] text-slate-400">PDF, DOCX, or TXT · Max 5 MB</p>

            <label
              className={`mb-3 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed p-4 transition ${
                selectedFile
                  ? 'border-indigo-300 bg-indigo-50'
                  : 'border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50'
              }`}
              aria-label="Choose resume file"
            >
              <svg
                className={`h-6 w-6 ${selectedFile ? 'text-indigo-400' : 'text-slate-300'}`}
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
                />
              </svg>
              <span className={`text-[12px] font-medium ${selectedFile ? 'text-indigo-600' : 'text-slate-500'}`}>
                {selectedFile ? selectedFile.name : 'Click to choose file'}
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => { setSelectedFile(e.target.files?.[0] ?? null); setUploadError(null) }}
                disabled={isUploading}
                aria-label="Resume file input"
              />
            </label>

            <button
              onClick={handleUpload}
              disabled={isUploading || !selectedFile}
              className="w-full rounded-lg bg-indigo-600 py-2 text-[12px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUploading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                  </svg>
                  Uploading…
                </span>
              ) : 'Upload Resume'}
            </button>
            {uploadError && (
              <p role="alert" className="mt-2 text-[11px] text-red-500">{uploadError}</p>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2.5 ring-1 ring-emerald-200">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white" aria-hidden="true">
              <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
              </svg>
            </span>
            <span className="text-[12px] font-semibold text-emerald-700">Resume uploaded</span>
          </div>
        )}
      </div>

      {/* ---- Search section ---- */}
      <div className="px-4 py-4 border-b border-slate-100">
        <form onSubmit={handleSearch} aria-label="Job search">
          <SectionLabel>Search</SectionLabel>

          <div className="relative">
            <svg
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            <input
              id="sidebar-query"
              type="text"
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              placeholder="Job title or keywords…"
              required
              aria-required="true"
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-8 pr-3 text-[13px] text-slate-800 placeholder:text-slate-400 transition focus:border-indigo-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          <label className="mt-2.5 flex cursor-pointer items-center gap-2">
            <div className="relative">
              <input
                type="checkbox"
                checked={criteria.remote_only ?? false}
                onChange={(e) => setCriteria({ remote_only: e.target.checked })}
                className="peer sr-only"
                id="remote-only-toggle"
              />
              <div className="h-4 w-7 rounded-full bg-slate-200 transition peer-checked:bg-indigo-500 peer-focus-visible:ring-2 peer-focus-visible:ring-indigo-500 peer-focus-visible:ring-offset-1" />
              <div className="absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-white shadow transition peer-checked:translate-x-3" />
            </div>
            <span className="text-[12px] font-medium text-slate-600" id="remote-only-label">
              Remote only
            </span>
          </label>

          <button
            type="submit"
            disabled={searchMutation.isPending || !criteria.query.trim()}
            aria-busy={searchMutation.isPending}
            className="mt-3 w-full rounded-lg bg-indigo-600 py-2 text-[13px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {searchMutation.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                </svg>
                Searching…
              </span>
            ) : 'Search Jobs'}
          </button>

          {searchMutation.isError && (
            <p role="alert" className="mt-2 text-[11px] text-red-500">
              Search failed. Please try again.
            </p>
          )}
        </form>
      </div>

      {/* ---- Filters section ---- */}
      <div className="px-4 py-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SectionLabel>Filters</SectionLabel>
            {activeFilterCount > 0 && (
              <span className="mb-2 inline-flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
                {activeFilterCount}
              </span>
            )}
          </div>
          {activeFilterCount > 0 && (
            <button
              onClick={() => { setSelectedSources([]); setSelectedCompanies([]); setCriteria({ page: 1 }) }}
              className="mb-2 text-[11px] font-medium text-indigo-500 hover:text-indigo-700 focus:outline-none focus:underline"
            >
              Clear all
            </button>
          )}
        </div>

        <div className="space-y-5 text-sm">

          {/* Location */}
          <div>
            <label htmlFor="filter-location" className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Location
            </label>
            <input
              id="filter-location"
              type="text"
              value={criteria.location ?? ''}
              onChange={(e) => setCriteria({ location: e.target.value || undefined, page: 1 })}
              placeholder="City, country, or remote"
              className={inputBase}
            />
          </div>

          {/* Posted within */}
          <div>
            <label htmlFor="filter-posted" className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Posted Within
            </label>
            <select
              id="filter-posted"
              value={criteria.posted_within_days?.toString() ?? ''}
              onChange={(e) => setCriteria({ posted_within_days: e.target.value ? parseInt(e.target.value, 10) : undefined, page: 1 })}
              className={inputBase}
            >
              {POSTED_WITHIN_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {/* Dynamic: Sources */}
          {showSources && (
            <fieldset>
              <legend className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Source
              </legend>
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
                      <input
                        type="checkbox"
                        checked={isActive}
                        onChange={() => toggleSource(source)}
                        className="sr-only"
                      />
                      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} aria-hidden="true" />
                      {source.charAt(0).toUpperCase() + source.slice(1)}
                    </label>
                  )
                })}
              </div>
            </fieldset>
          )}

          {/* Dynamic: Companies */}
          {showCompanies && (
            <fieldset>
              <legend className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Company
              </legend>
              <div className="space-y-1.5">
                {visibleCompanies.map((company) => {
                  const isActive = selectedCompanies.includes(company)
                  return (
                    <label key={company} className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 hover:bg-slate-50">
                      <div
                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition ${
                          isActive
                            ? 'border-indigo-500 bg-indigo-500 text-white'
                            : 'border-slate-300 bg-white'
                        }`}
                      >
                        {isActive && (
                          <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M1.5 5l2.5 2.5 5-5" />
                          </svg>
                        )}
                        <input
                          type="checkbox"
                          checked={isActive}
                          onChange={() => toggleCompany(company)}
                          className="sr-only"
                          aria-label={company}
                        />
                      </div>
                      <span className={`text-[12px] ${isActive ? 'font-semibold text-slate-800' : 'text-slate-600'}`}>
                        {company}
                      </span>
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
                  {companiesExpanded ? (
                    <>Show fewer</>
                  ) : (
                    <>Show all ({filtersData!.companies.length})</>
                  )}
                </button>
              )}
            </fieldset>
          )}
        </div>
      </div>
    </div>
  )
}
