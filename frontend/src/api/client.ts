import axios from 'axios'
import { useAuthStore } from '../store/useAuthStore'

export const api = axios.create({ baseURL: '/api' })

// Attach the bearer token (if any) to every request.
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A 401 means the token is missing/expired/invalid — log the user out so the
// app falls back to the auth screen instead of looping on failed requests.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearToken()
    }
    return Promise.reject(error)
  }
)

/**
 * Download a file from an authenticated endpoint. Plain <a href> links can't send
 * the Authorization header, so we fetch the bytes as a blob (token attached by the
 * request interceptor) and trigger a save via a temporary object URL.
 *
 * `path` is the full app path including the /api prefix (what the getXDownloadUrl
 * helpers return); we strip the prefix because the axios instance already adds it.
 */
export async function downloadFile(path: string): Promise<void> {
  const relative = path.replace(/^\/api/, '')
  const response = await api.get(relative, { responseType: 'blob' })

  let filename = 'download'
  const disposition = response.headers['content-disposition'] as string | undefined
  const match = disposition?.match(/filename="?([^"]+)"?/)
  if (match) filename = match[1]

  const url = URL.createObjectURL(response.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
