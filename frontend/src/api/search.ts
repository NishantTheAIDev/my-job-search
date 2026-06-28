import { api } from './client'
import type { SearchCriteria, SearchStatusResponse } from '../types'

export interface CreateSearchResponse {
  job_id: string
  status: string
  cached: boolean
}

export async function createSearch(
  criteria: SearchCriteria,
  force = false,
): Promise<CreateSearchResponse> {
  const url = force ? '/search?force=true' : '/search'
  const response = await api.post<CreateSearchResponse>(url, criteria)
  return response.data
}

export async function getSearchStatus(jobId: string): Promise<SearchStatusResponse> {
  const response = await api.get<SearchStatusResponse>(`/search/${jobId}/status`)
  return response.data
}
