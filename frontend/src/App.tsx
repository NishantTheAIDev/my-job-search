import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from './store/useJobSearchStore'
import { useAuthStore } from './store/useAuthStore'
import { AuthPage } from './components/Auth/AuthPage'
import { LandingPage } from './components/Landing/LandingPage'
import { ResultsView } from './components/Results/ResultsView'
import { JobDetailSlideOver } from './components/Results/JobDetailSlideOver'
import { ResumeEditor } from './components/ResumeEditor/ResumeEditor'
import { ApprovalScreen } from './components/ApprovalScreen/ApprovalScreen'
import { InsightsPage } from './components/Insights/InsightsPage'
import { PasteJDPage } from './components/PasteJD/PasteJDPage'
import { SavedApplicationsPage } from './components/SavedApplications/SavedApplicationsPage'
import { SavedSearchesPage } from './components/SavedSearches/SavedSearchesPage'

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
  const showApproval = useJobSearchStore((s) => s.showApproval)
  const showInsights = useJobSearchStore((s) => s.showInsights)
  const showPasteJd = useJobSearchStore((s) => s.showPasteJd)
  const showSavedApplications = useJobSearchStore((s) => s.showSavedApplications)
  const showSavedSearches = useJobSearchStore((s) => s.showSavedSearches)

  // Full-page overlays — ordered by priority (showApproval must outrank showPasteJd
  // so the paste→approval transition works: PasteJDPage sets showPasteJd=false and
  // showApproval=true in a single action, and the approval screen is immediately shown).
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

  // Insights view takes over the whole page when active
  if (showInsights) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-slate-50 font-sans">
        <InsightsPage />
      </div>
    )
  }

  return (
    <div className="fixed inset-0 overflow-y-auto bg-slate-50 font-sans">
      {/* Landing (no active search) vs working results layout */}
      {activeSearchJobId ? <ResultsView /> : <LandingPage />}

      {/* Overlays */}
      <JobDetailSlideOver />
      {activeApplicationId && !showApproval && <ResumeEditor />}
      {showApproval && <ApprovalScreen />}
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
