import { api } from './client'

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface MeResponse {
  id: string
  email: string
}

export async function register(email: string, password: string): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>('/auth/register', { email, password })
  return response.data
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>('/auth/login', { email, password })
  return response.data
}

export async function getMe(): Promise<MeResponse> {
  const response = await api.get<MeResponse>('/auth/me')
  return response.data
}
