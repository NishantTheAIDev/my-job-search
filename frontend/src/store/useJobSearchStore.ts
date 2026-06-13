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
  setCriteria: (c: Partial<SearchCriteria>) => void
  setActiveSearchJob: (id: string | null) => void
  setSelectedJob: (job: JobPosting | null) => void
  setSelectedSources: (sources: string[]) => void
  setSelectedCompanies: (companies: string[]) => void
  setActiveApplication: (id: string | null) => void
  setResumeUploaded: (v: boolean) => void
  setShowApproval: (v: boolean) => void
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
  setCriteria: (c) => set((s) => ({ criteria: { ...s.criteria, ...c } })),
  setActiveSearchJob: (id) => set({ activeSearchJobId: id }),
  setSelectedJob: (job) => set({ selectedJob: job }),
  setSelectedSources: (sources) => set({ selectedSources: sources }),
  setSelectedCompanies: (companies) => set({ selectedCompanies: companies }),
  setActiveApplication: (id) => set({ activeApplicationId: id }),
  setResumeUploaded: (v) => set({ resumeUploaded: v }),
  setShowApproval: (v) => set({ showApproval: v }),
}))
