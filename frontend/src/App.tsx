import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from './store/useJobSearchStore'
import { LandingPage } from './components/Landing/LandingPage'
import { ResultsView } from './components/Results/ResultsView'
import { JobDetailSlideOver } from './components/Results/JobDetailSlideOver'
import { ResumeEditor } from './components/ResumeEditor/ResumeEditor'
import { ApprovalScreen } from './components/ApprovalScreen/ApprovalScreen'
import { InsightsPage } from './components/Insights/InsightsPage'

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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppLayout />
    </QueryClientProvider>
  )
}

export default App
