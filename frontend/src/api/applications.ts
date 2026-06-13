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

export type ReviseTarget = 'resume' | 'cover_letter'

export async function reviseApplication(
  id: string,
  target: ReviseTarget,
  instructions: string
): Promise<ApplicationResponse> {
  const response = await api.post<ApplicationResponse>(`/applications/${id}/revise`, {
    target,
    instructions,
  })
  return response.data
}

export async function editApplicationContent(
  id: string,
  target: ReviseTarget,
  text: string
): Promise<ApplicationResponse> {
  const response = await api.put<ApplicationResponse>(`/applications/${id}/content`, {
    target,
    text,
  })
  return response.data
}

export type DownloadFormat = 'pdf' | 'docx'

// RenderCV themes available for the tailored-resume PDF. Kept in sync with
// RENDERCV_THEMES in backend/services/rendercv_service.py — the backend rejects
// any value not in its allowlist.
export const RENDERCV_THEMES: { value: string; label: string }[] = [
  { value: 'engineeringresumes', label: 'Engineering Resumes' },
  { value: 'engineeringclassic', label: 'Engineering Classic' },
  { value: 'classic', label: 'Classic' },
  { value: 'harvard', label: 'Harvard' },
  { value: 'sb2nov', label: 'sb2nov' },
  { value: 'moderncv', label: 'ModernCV' },
  { value: 'ember', label: 'Ember' },
  { value: 'ink', label: 'Ink' },
  { value: 'opal', label: 'Opal' },
]

export const DEFAULT_RENDERCV_THEME = 'engineeringresumes'

// Theme only affects the rendercv PDF; the .docx export is plain text.
export function getResumeDownloadUrl(
  id: string,
  format: DownloadFormat,
  theme?: string
): string {
  const url = `/api/applications/${id}/resume.${format}`
  return format === 'pdf' && theme ? `${url}?theme=${encodeURIComponent(theme)}` : url
}

export function getCoverLetterDownloadUrl(id: string, format: DownloadFormat): string {
  return `/api/applications/${id}/cover-letter.${format}`
}
