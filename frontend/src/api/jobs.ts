import { api } from './client'
import type { JobPosting, JobsListResponse, PrepareApplicationResponse } from '../types'

export interface ListJobsParams {
  search_job_id: string
  page?: number
  page_size?: number
  min_score?: number
}

export async function listJobs(params: ListJobsParams): Promise<JobsListResponse> {
  const response = await api.get<JobsListResponse>('/jobs', { params })
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
