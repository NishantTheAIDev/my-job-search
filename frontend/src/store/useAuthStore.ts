import { create } from 'zustand'

const TOKEN_KEY = 'jobsearch_token'

// localStorage isn't always available (SSR, test environments). Access it
// defensively so importing this store never throws.
function readToken(): string | null {
  try {
    return globalThis.localStorage?.getItem(TOKEN_KEY) ?? null
  } catch {
    return null
  }
}

function writeToken(token: string | null): void {
  try {
    if (token === null) globalThis.localStorage?.removeItem(TOKEN_KEY)
    else globalThis.localStorage?.setItem(TOKEN_KEY, token)
  } catch {
    /* ignore — token simply won't persist across reloads */
  }
}

interface AuthState {
  token: string | null
  setToken: (token: string) => void
  clearToken: () => void
}

/**
 * Holds the JWT issued by /auth/login|register, persisted to localStorage so a
 * refresh stays logged in. The token is attached to every request by the axios
 * interceptor in api/client.ts; a 401 there clears it (logging the user out).
 */
export const useAuthStore = create<AuthState>((set) => ({
  token: readToken(),
  setToken: (token) => {
    writeToken(token)
    set({ token })
  },
  clearToken: () => {
    writeToken(null)
    set({ token: null })
  },
}))
