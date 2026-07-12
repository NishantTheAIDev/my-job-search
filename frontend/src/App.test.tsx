/**
 * Focused tests for App-level routing logic.
 *
 * The "smart back" invariant: when workspaceOrigin === 'home' AND
 * activeSearchJobId is set AND no active application is open, LandingPage
 * renders rather than ResultsView.  This prevents a user who opened the
 * workspace from the "Paste JD" or "In Progress" surfaces from landing in
 * unrelated search results when they close the workspace.
 */

import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from './store/useJobSearchStore'
import { useAuthStore } from './store/useAuthStore'
import App from './App'

// ── Stub child components so we don't need to mock all API routes ──────────

vi.mock('./components/Landing/LandingPage', () => ({
  LandingPage: () => <div data-testid="landing-page">Landing</div>,
}))

vi.mock('./components/Results/ResultsView', () => ({
  ResultsView: () => <div data-testid="results-view">Results</div>,
}))

vi.mock('./components/Results/JobDetailSlideOver', () => ({
  JobDetailSlideOver: () => null,
}))

vi.mock('./components/ApplicationWorkspace/ApplicationWorkspace', () => ({
  ApplicationWorkspace: () => <div data-testid="workspace">Workspace</div>,
}))

vi.mock('./components/Insights/InsightsPage', () => ({
  InsightsPage: () => <div data-testid="insights">Insights</div>,
}))

vi.mock('./components/PasteJD/PasteJDPage', () => ({
  PasteJDPage: () => <div data-testid="paste-jd">PasteJD</div>,
}))

vi.mock('./components/SavedApplications/SavedApplicationsPage', () => ({
  SavedApplicationsPage: () => <div data-testid="saved-apps">Saved</div>,
}))

vi.mock('./components/SavedSearches/SavedSearchesPage', () => ({
  SavedSearchesPage: () => <div data-testid="saved-searches">Saved Searches</div>,
}))

vi.mock('./components/InProgressApplications/InProgressApplicationsPage', () => ({
  InProgressApplicationsPage: () => <div data-testid="in-progress">In Progress</div>,
}))

vi.mock('./components/Auth/AuthPage', () => ({
  AuthPage: () => <div data-testid="auth-page">Auth</div>,
}))

// ── Test wrapper ──────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

// ── Setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  // Set a fake token so the auth gate passes and AppLayout renders.
  useAuthStore.setState({ token: 'fake-token' })
  useJobSearchStore.setState({
    activeSearchJobId: null,
    activeApplicationId: null,
    workspaceOrigin: null,
    showInsights: false,
    showPasteJd: false,
    showSavedApplications: false,
    showSavedSearches: false,
    showInProgressApplications: false,
  })
})

afterEach(() => {
  // Clear token to avoid leak into other test files.
  useAuthStore.setState({ token: null })
})

// ── Smart-back tests ──────────────────────────────────────────────────────────

describe('App smart-back (showResults logic)', () => {
  it('shows LandingPage when there is no active search', () => {
    useJobSearchStore.setState({ activeSearchJobId: null, workspaceOrigin: null })
    render(<App />, { wrapper })
    expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    expect(screen.queryByTestId('results-view')).not.toBeInTheDocument()
  })

  it('shows ResultsView when activeSearchJobId is set and workspaceOrigin is null', () => {
    useJobSearchStore.setState({ activeSearchJobId: 'search-1', workspaceOrigin: null })
    render(<App />, { wrapper })
    expect(screen.getByTestId('results-view')).toBeInTheDocument()
    expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()
  })

  it('shows ResultsView when activeSearchJobId is set and workspaceOrigin is "results"', () => {
    useJobSearchStore.setState({ activeSearchJobId: 'search-1', workspaceOrigin: 'results' })
    render(<App />, { wrapper })
    expect(screen.getByTestId('results-view')).toBeInTheDocument()
    expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()
  })

  it('shows LandingPage (not ResultsView) when workspaceOrigin is "home" even if activeSearchJobId is set', () => {
    // This is the smart-back invariant: the user came via Paste-JD / In-Progress,
    // so after closing the workspace we must return to LandingPage, not results.
    useJobSearchStore.setState({
      activeSearchJobId: 'search-1',
      workspaceOrigin: 'home',
      activeApplicationId: null,
    })
    render(<App />, { wrapper })
    expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    expect(screen.queryByTestId('results-view')).not.toBeInTheDocument()
  })

  it('shows InProgressApplicationsPage when showInProgressApplications is true', () => {
    useJobSearchStore.setState({ showInProgressApplications: true })
    render(<App />, { wrapper })
    expect(screen.getByTestId('in-progress')).toBeInTheDocument()
  })
})
