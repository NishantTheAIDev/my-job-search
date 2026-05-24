import { create } from 'zustand'
import type { SearchCriteria } from '../types'

interface JobSearchState {
  criteria: SearchCriteria
  activeSearchJobId: string | null
  selectedJobId: string | null
  activeApplicationId: string | null
  resumeUploaded: boolean
  showApproval: boolean
  setCriteria: (c: Partial<SearchCriteria>) => void
  setActiveSearchJob: (id: string | null) => void
  setSelectedJob: (id: string | null) => void
  setActiveApplication: (id: string | null) => void
  setResumeUploaded: (v: boolean) => void
  setShowApproval: (v: boolean) => void
}

export const useJobSearchStore = create<JobSearchState>((set) => ({
  criteria: { query: '', remote_only: false, page: 1 },
  activeSearchJobId: null,
  selectedJobId: null,
  activeApplicationId: null,
  resumeUploaded: false,
  showApproval: false,
  setCriteria: (c) => set((s) => ({ criteria: { ...s.criteria, ...c } })),
  setActiveSearchJob: (id) => set({ activeSearchJobId: id }),
  setSelectedJob: (id) => set({ selectedJobId: id }),
  setActiveApplication: (id) => set({ activeApplicationId: id }),
  setResumeUploaded: (v) => set({ resumeUploaded: v }),
  setShowApproval: (v) => set({ showApproval: v }),
}))
