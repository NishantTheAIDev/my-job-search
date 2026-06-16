import { api } from './client'
import type {
  RunSavedSearchResponse,
  SavedSearch,
  SavedSearchDiff,
  SearchCriteria,
} from '../types'

export async function listSavedSearches(): Promise<SavedSearch[]> {
  const response = await api.get<SavedSearch[]>('/saved-searches')
  return response.data
}

export async function createSavedSearch(
  name: string,
  criteria: SearchCriteria,
): Promise<SavedSearch> {
  const response = await api.post<SavedSearch>('/saved-searches', { name, criteria })
  return response.data
}

export async function deleteSavedSearch(id: string): Promise<void> {
  await api.delete(`/saved-searches/${id}`)
}

export async function runSavedSearch(id: string): Promise<RunSavedSearchResponse> {
  const response = await api.post<RunSavedSearchResponse>(`/saved-searches/${id}/run`)
  return response.data
}

// Idempotent per search_job_id — safe to call on each poll-to-complete. Advances
// the saved-search baseline so the next run diffs against this one.
export async function diffSavedSearch(
  id: string,
  searchJobId: string,
): Promise<SavedSearchDiff> {
  const response = await api.post<SavedSearchDiff>(
    `/saved-searches/${id}/diff?search_job_id=${searchJobId}`,
  )
  return response.data
}
