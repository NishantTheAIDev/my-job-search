import { api } from './client'
import type { SearchCriteria, SearchStatusResponse } from '../types'

export interface CreateSearchResponse {
  job_id: string
  status: string
}

export async function createSearch(criteria: SearchCriteria): Promise<CreateSearchResponse> {
  const response = await api.post<CreateSearchResponse>('/search', criteria)
  return response.data
}

export async function getSearchStatus(jobId: string): Promise<SearchStatusResponse> {
  const response = await api.get<SearchStatusResponse>(`/search/${jobId}/status`)
  return response.data
}
