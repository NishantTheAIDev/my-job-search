import { api } from './client'
import type { ApplicationResponse, ApplicationStatus } from '../types'

export async function listApplications(status?: ApplicationStatus): Promise<ApplicationResponse[]> {
  const params = status ? { status } : undefined
  const response = await api.get<ApplicationResponse[]>('/applications', { params })
  return response.data
}

export async function getApplication(id: string): Promise<ApplicationResponse> {
  const response = await api.get<ApplicationResponse>(`/applications/${id}`)
  return response.data
}

export async function getApplicationByJob(jobPostingId: string): Promise<ApplicationResponse> {
  const response = await api.get<ApplicationResponse>(`/applications/by-job/${jobPostingId}`)
  return response.data
}

// The prepare pipeline creates the Application row only after several LLM calls
// (resume tailoring alone can take ~45s). At 2s between polls this caps the
// "still preparing" wait at ~3 minutes before surfacing an error.
export const PREPARE_POLL_MAX_RETRIES = 90

export async function approveApplication(id: string): Promise<ApplicationResponse> {
  const response = await api.post<ApplicationResponse>(`/applications/${id}/approve`)
  return response.data
}

export async function rejectApplication(id: string): Promise<ApplicationResponse> {
  const response = await api.post<ApplicationResponse>(`/applications/${id}/reject`)
  return response.data
}

export type DownloadFormat = 'pdf' | 'docx'

export function getResumeDownloadUrl(id: string, format: DownloadFormat): string {
  return `/api/applications/${id}/resume.${format}`
}

export function getCoverLetterDownloadUrl(id: string, format: DownloadFormat): string {
  return `/api/applications/${id}/cover-letter.${format}`
}
