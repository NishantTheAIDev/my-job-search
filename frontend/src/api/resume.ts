import { api } from './client'
import type { ResumeResponse } from '../types'

export async function uploadResume(file: File): Promise<ResumeResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<ResumeResponse>('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function getResume(): Promise<ResumeResponse> {
  const response = await api.get<ResumeResponse>('/resume')
  return response.data
}
