import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  /** Rendered when a descendant throws. Receives a reset callback to retry. */
  fallback?: (reset: () => void) => ReactNode
  /** When any value in this array changes, the boundary auto-resets. Useful for
   * clearing the error when the user navigates or changes filters. */
  resetKeys?: unknown[]
  /** Optional label included in the logged error for easier debugging. */
  label?: string
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Catches render errors in its subtree so a single failing component can't blank
 * the entire app (React unmounts the whole tree on an uncaught render throw).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface the real error in the console for debugging instead of swallowing it.
    console.error(`[ErrorBoundary${this.props.label ? `: ${this.props.label}` : ''}]`, error, info.componentStack)
  }

  componentDidUpdate(prev: ErrorBoundaryProps) {
    if (!this.state.error) return
    const a = prev.resetKeys
    const b = this.props.resetKeys
    if (a && b && (a.length !== b.length || a.some((v, i) => !Object.is(v, b[i])))) {
      this.reset()
    }
  }

  reset = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback(this.reset)
      return (
        <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-3 p-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-50 text-rose-500">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0 3.75h.008M10.34 3.94 1.74 18.06A1.5 1.5 0 0 0 3.05 20.3h17.9a1.5 1.5 0 0 0 1.3-2.24L13.66 3.94a1.5 1.5 0 0 0-2.62 0Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-700">Something went wrong</h3>
            <p className="mt-1 max-w-sm text-sm leading-relaxed text-slate-500">
              This section failed to render. The rest of the app is still usable.
            </p>
          </div>
          <button
            onClick={this.reset}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
