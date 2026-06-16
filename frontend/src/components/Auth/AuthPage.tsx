import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { login, register } from '../../api/auth'
import { useAuthStore } from '../../store/useAuthStore'
import { Logo } from '../shared/Logo'

type Mode = 'login' | 'register'

/**
 * Unauthenticated entry screen. On success it stores the JWT in the auth store,
 * which flips App from the gate to the main application.
 */
export function AuthPage() {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const setToken = useAuthStore((s) => s.setToken)

  const mutation = useMutation({
    mutationFn: async () => {
      const fn = mode === 'login' ? login : register
      return fn(email.trim().toLowerCase(), password)
    },
    onSuccess: (data) => setToken(data.access_token),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    mutation.mutate()
  }

  const errorMessage = (() => {
    if (!mutation.isError) return null
    const err = mutation.error
    if (err instanceof AxiosError) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') return detail
      if (err.response?.status === 422) return 'Please enter a valid email and password.'
    }
    return 'Something went wrong. Please try again.'
  })()

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-slate-50 font-sans">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <Logo />
          <h1 className="text-lg font-semibold text-slate-800">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-[13px] font-medium text-slate-600">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-[13px] font-medium text-slate-600">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {errorMessage && (
            <p role="alert" className="text-[13px] text-red-600">
              {errorMessage}
            </p>
          )}

          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60"
          >
            {mutation.isPending
              ? 'Please wait…'
              : mode === 'login'
                ? 'Log in'
                : 'Sign up'}
          </button>
        </form>

        <p className="mt-5 text-center text-[13px] text-slate-500">
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode((m) => (m === 'login' ? 'register' : 'login'))
              mutation.reset()
            }}
            className="font-medium text-indigo-600 hover:text-indigo-700"
          >
            {mode === 'login' ? 'Sign up' : 'Log in'}
          </button>
        </p>
      </div>
    </div>
  )
}
