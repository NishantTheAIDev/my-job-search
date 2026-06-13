import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from './store/useJobSearchStore'
import { LeftSidebar } from './components/LeftSidebar/LeftSidebar'
import { ResultsList } from './components/ResultsList/ResultsList'
import { JobDetailPanel } from './components/ResultsList/JobDetailPanel'
import { ResumeEditor } from './components/ResumeEditor/ResumeEditor'
import { ApprovalScreen } from './components/ApprovalScreen/ApprovalScreen'
import type { JobFiltersResponse } from './types'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
    },
  },
})

function BriefcaseIcon() {
  return (
    <svg
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"
      />
    </svg>
  )
}


function AppLayout() {
  const activeApplicationId = useJobSearchStore((s) => s.activeApplicationId)
  const showApproval = useJobSearchStore((s) => s.showApproval)
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)
  const selectedJob = useJobSearchStore((s) => s.selectedJob)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)

  const [filtersData, setFiltersData] = useState<JobFiltersResponse | null>(null)

  useEffect(() => {
    setFiltersData(null)
  }, [activeSearchJobId])

  return (
    <div className="fixed inset-0 flex flex-col bg-slate-50 font-sans">
      {/* Top navigation bar */}
      <nav className="sticky top-0 z-50 flex h-14 items-center border-b border-slate-200 bg-white px-5 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
            <BriefcaseIcon />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-slate-900">
            Job Search Assistant
          </span>
          <span className="ml-1 inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-600">
            AI
          </span>
        </div>
      </nav>

      {/* Three-column layout */}
      <div className="flex min-h-0 flex-1 overflow-hidden">

        {/* Left sidebar */}
        <aside className="w-72 flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-white">
          <LeftSidebar filtersData={filtersData} />
        </aside>

        {/* Middle: results list — stable fixed width to prevent layout shift on filter interactions */}
        <div id="results-col" className="w-[420px] flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-white">
          <ResultsList onFiltersLoaded={setFiltersData} />
        </div>

        {/* Right: job detail — only rendered when a job is selected */}
        {selectedJob && (
          <div className="flex-1 overflow-y-auto bg-slate-50">
            <JobDetailPanel job={selectedJob} onClose={() => setSelectedJob(null)} />
          </div>
        )}
      </div>

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
