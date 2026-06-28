import { create } from 'zustand'
import type { SearchCriteria, JobPosting } from '../types'

// Where the ApplicationWorkspace was opened from.
// Used by handleClose to decide where to return the user.
export type WorkspaceOrigin = 'results' | 'home' | null

interface JobSearchState {
  criteria: SearchCriteria
  activeSearchJobId: string | null
  selectedJob: JobPosting | null
  selectedSources: string[]
  selectedCompanies: string[]
  activeApplicationId: string | null
  resumeUploaded: boolean
  showInsights: boolean
  showPasteJd: boolean
  showSavedApplications: boolean
  showSavedSearches: boolean
  showInProgressApplications: boolean
  // The saved search whose re-run is currently active (drives the "new" badge).
  // null for ad-hoc searches that didn't originate from a saved search.
  activeSavedSearchId: string | null
  // Tracks what surface opened the ApplicationWorkspace so handleClose
  // can navigate back to the right place.
  workspaceOrigin: WorkspaceOrigin
  setCriteria: (c: Partial<SearchCriteria>) => void
  setActiveSearchJob: (id: string | null) => void
  setSelectedJob: (job: JobPosting | null) => void
  setSelectedSources: (sources: string[]) => void
  setSelectedCompanies: (companies: string[]) => void
  setActiveApplication: (id: string | null) => void
  setResumeUploaded: (v: boolean) => void
  setShowInsights: (v: boolean) => void
  setShowPasteJd: (v: boolean) => void
  setShowSavedApplications: (v: boolean) => void
  setShowSavedSearches: (v: boolean) => void
  setShowInProgressApplications: (v: boolean) => void
  setActiveSavedSearchId: (id: string | null) => void
  setWorkspaceOrigin: (origin: WorkspaceOrigin) => void
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
  showInsights: false,
  showPasteJd: false,
  showSavedApplications: false,
  showSavedSearches: false,
  showInProgressApplications: false,
  activeSavedSearchId: null,
  workspaceOrigin: null,
  setCriteria: (c) => set((s) => ({ criteria: { ...s.criteria, ...c } })),
  // Clearing workspaceOrigin here ensures that once the user starts a new
  // search, App.tsx switches back to showing ResultsView rather than
  // holding the post-home-origin LandingPage.
  setActiveSearchJob: (id) => set({ activeSearchJobId: id, workspaceOrigin: null }),
  setSelectedJob: (job) => set({ selectedJob: job }),
  setSelectedSources: (sources) => set({ selectedSources: sources }),
  setSelectedCompanies: (companies) => set({ selectedCompanies: companies }),
  setActiveApplication: (id) => set({ activeApplicationId: id }),
  setResumeUploaded: (v) => set({ resumeUploaded: v }),
  setShowInsights: (v) => set({ showInsights: v }),
  setShowPasteJd: (v) => set({ showPasteJd: v }),
  setShowSavedApplications: (v) => set({ showSavedApplications: v }),
  setShowSavedSearches: (v) => set({ showSavedSearches: v }),
  setShowInProgressApplications: (v) => set({ showInProgressApplications: v }),
  setActiveSavedSearchId: (id) => set({ activeSavedSearchId: id }),
  setWorkspaceOrigin: (origin) => set({ workspaceOrigin: origin }),
  resetToLanding: () =>
    set({
      activeSearchJobId: null,
      selectedJob: null,
      selectedSources: [],
      selectedCompanies: [],
      activeApplicationId: null,
      showInsights: false,
      showPasteJd: false,
      showSavedApplications: false,
      showSavedSearches: false,
      showInProgressApplications: false,
      activeSavedSearchId: null,
      workspaceOrigin: null,
      criteria: { query: '', remote_only: false, page: 1 },
    }),
}))
