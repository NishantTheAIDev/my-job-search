import { create } from 'zustand'
import type { SearchCriteria, JobPosting } from '../types'

interface JobSearchState {
  criteria: SearchCriteria
  activeSearchJobId: string | null
  selectedJob: JobPosting | null
  selectedSources: string[]
  selectedCompanies: string[]
  activeApplicationId: string | null
  resumeUploaded: boolean
  showApproval: boolean
  showInsights: boolean
  showPasteJd: boolean
  showSavedApplications: boolean
  showSavedSearches: boolean
  // The saved search whose re-run is currently active (drives the "new" badge).
  // null for ad-hoc searches that didn't originate from a saved search.
  activeSavedSearchId: string | null
  setCriteria: (c: Partial<SearchCriteria>) => void
  setActiveSearchJob: (id: string | null) => void
  setSelectedJob: (job: JobPosting | null) => void
  setSelectedSources: (sources: string[]) => void
  setSelectedCompanies: (companies: string[]) => void
  setActiveApplication: (id: string | null) => void
  setResumeUploaded: (v: boolean) => void
  setShowApproval: (v: boolean) => void
  setShowInsights: (v: boolean) => void
  setShowPasteJd: (v: boolean) => void
  setShowSavedApplications: (v: boolean) => void
  setShowSavedSearches: (v: boolean) => void
  setActiveSavedSearchId: (id: string | null) => void
  resetToLanding: () => void
}

export const useJobSearchStore = create<JobSearchState>((set) => ({
  criteria: { query: '', remote_only: false, page: 1 },
  activeSearchJobId: null,
  selectedJob: null,
  selectedSources: [],
  selectedCompanies: [],
  activeApplicationId: null,
  resumeUploaded: false,
  showApproval: false,
  showInsights: false,
  showPasteJd: false,
  showSavedApplications: false,
  showSavedSearches: false,
  activeSavedSearchId: null,
  setCriteria: (c) => set((s) => ({ criteria: { ...s.criteria, ...c } })),
  setActiveSearchJob: (id) => set({ activeSearchJobId: id }),
  setSelectedJob: (job) => set({ selectedJob: job }),
  setSelectedSources: (sources) => set({ selectedSources: sources }),
  setSelectedCompanies: (companies) => set({ selectedCompanies: companies }),
  setActiveApplication: (id) => set({ activeApplicationId: id }),
  setResumeUploaded: (v) => set({ resumeUploaded: v }),
  setShowApproval: (v) => set({ showApproval: v }),
  setShowInsights: (v) => set({ showInsights: v }),
  setShowPasteJd: (v) => set({ showPasteJd: v }),
  setShowSavedApplications: (v) => set({ showSavedApplications: v }),
  setShowSavedSearches: (v) => set({ showSavedSearches: v }),
  setActiveSavedSearchId: (id) => set({ activeSavedSearchId: id }),
  resetToLanding: () =>
    set({
      activeSearchJobId: null,
      selectedJob: null,
      selectedSources: [],
      selectedCompanies: [],
      activeApplicationId: null,
      showApproval: false,
      showInsights: false,
      showPasteJd: false,
      showSavedApplications: false,
      showSavedSearches: false,
      activeSavedSearchId: null,
      criteria: { query: '', remote_only: false, page: 1 },
    }),
}))
