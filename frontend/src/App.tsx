import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from './store/useJobSearchStore'
import { useAuthStore } from './store/useAuthStore'
import { AuthPage } from './components/Auth/AuthPage'
import { LandingPage } from './components/Landing/LandingPage'
import { ResultsView } from './components/Results/ResultsView'
import { JobDetailSlideOver } from './components/Results/JobDetailSlideOver'
import { ApplicationWorkspace } from './components/ApplicationWorkspace/ApplicationWorkspace'
import { InsightsPage } from './components/Insights/InsightsPage'
import { PasteJDPage } from './components/PasteJD/PasteJDPage'
import { SavedApplicationsPage } from './components/SavedApplications/SavedApplicationsPage'
import { SavedSearchesPage } from './components/SavedSearches/SavedSearchesPage'
import { InProgressApplicationsPage } from './components/InProgressApplications/InProgressApplicationsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
    },
  },
})

function AppLayout() {
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const showInsights = useJobSearchStore((s) => s.showInsights)
  const showPasteJd = useJobSearchStore((s) => s.showPasteJd)
  const showSavedApplications = useJobSearchStore((s) => s.showSavedApplications)
  const showSavedSearches = useJobSearchStore((s) => s.showSavedSearches)
  const showInProgressApplications = useJobSearchStore((s) => s.showInProgressApplications)
  // workspaceOrigin drives "smart back": when the workspace was opened from a
  // non-results surface ('home'), closing it should show LandingPage even if
  // an activeSearchJobId is still in the store.
  const workspaceOrigin = useJobSearchStore((s) => s.workspaceOrigin)

  if (showPasteJd) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-slate-50 font-sans">
        <PasteJDPage />
      </div>
    )
  }

  if (showSavedApplications) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-slate-50 font-sans">
        <SavedApplicationsPage />
      </div>
    )
  }

  if (showSavedSearches) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-slate-50 font-sans">
        <SavedSearchesPage />
      </div>
    )
  }

  if (showInProgressApplications) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-slate-50 font-sans">
        <InProgressApplicationsPage />
      </div>
    )
  }

  if (showInsights) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-slate-50 font-sans">
        <InsightsPage />
      </div>
    )
  }

  // Show results only when there is an active search AND the workspace was not
  // opened from a non-results surface. If workspaceOrigin === 'home', the user
  // came via Paste-JD or In-Progress, so we show LandingPage after they close
  // the workspace rather than dumping them into unrelated search results.
  const showResults = !!activeSearchJobId && workspaceOrigin !== 'home'

  return (
    <div className="fixed inset-0 overflow-y-auto bg-slate-50 font-sans">
      {/* Landing (no active search, or user came from a non-results surface) vs working results layout */}
      {showResults ? <ResultsView /> : <LandingPage />}

      {/* Overlays */}
      <JobDetailSlideOver />
      {activeApplicationId && <ApplicationWorkspace />}
    </div>
  )
}

function AuthGate() {
  const token = useAuthStore((s) => s.token)
  if (!token) return <AuthPage />
  return <AppLayout />
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  )
}

export default App
