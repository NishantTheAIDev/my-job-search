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

export async function approveApplication(id: string): Promise<ApplicationResponse> {
  const response = await api.post<ApplicationResponse>(`/applications/${id}/approve`)
  return response.data
}

export async function rejectApplication(id: string): Promise<ApplicationResponse> {
  const response = await api.post<ApplicationResponse>(`/applications/${id}/reject`)
  return response.data
}

export function getResumeDownloadUrl(id: string): string {
  return `/api/applications/${id}/resume.docx`
}
