import { api } from './client'
import type { JobPosting, JobsListResponse, JobFiltersResponse, PrepareApplicationResponse } from '../types'

export interface ListJobsParams {
  search_job_id: string
  page?: number
  page_size?: number
  min_score?: number
  source?: string[]
  company?: string[]
}

export async function listJobs(params: ListJobsParams): Promise<JobsListResponse> {
  const p = new URLSearchParams()
  p.set('search_job_id', params.search_job_id)
  if (params.page != null) p.set('page', String(params.page))
  if (params.page_size != null) p.set('page_size', String(params.page_size))
  if (params.min_score != null) p.set('min_score', String(params.min_score))
  params.source?.forEach((s) => p.append('source', s))
  params.company?.forEach((c) => p.append('company', c))
  const response = await api.get<JobsListResponse>(`/jobs?${p.toString()}`)
  return response.data
}

export async function getJobFilters(search_job_id: string): Promise<JobFiltersResponse> {
  const response = await api.get<JobFiltersResponse>('/jobs/filters', {
    params: { search_job_id },
  })
  return response.data
}

export async function getJob(id: string): Promise<JobPosting> {
  const response = await api.get<JobPosting>(`/jobs/${id}`)
  return response.data
}

export async function prepareApplication(jobId: string): Promise<PrepareApplicationResponse> {
  const response = await api.post<PrepareApplicationResponse>(`/jobs/${jobId}/prepare`)
  return response.data
}
