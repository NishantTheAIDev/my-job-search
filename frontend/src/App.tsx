import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from './store/useJobSearchStore'
import { ResumeUploadBanner } from './components/ResumeUploadBanner/ResumeUploadBanner'
import { SearchForm } from './components/SearchForm/SearchForm'
import { ResultsList } from './components/ResultsList/ResultsList'
import { ResumeEditor } from './components/ResumeEditor/ResumeEditor'
import { ApprovalScreen } from './components/ApprovalScreen/ApprovalScreen'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
    },
  },
})

function AppLayout() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const showApproval = useJobSearchStore((s) => s.showApproval)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white shadow-sm">
        <div className="mx-auto max-w-3xl px-4 py-4">
          <h1 className="text-xl font-bold text-gray-900">Job Search Assistant</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            AI-powered job search and application assistant
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6">
        <ResumeUploadBanner />
        <SearchForm />
        <ResultsList />
      </main>

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
