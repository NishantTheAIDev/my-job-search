import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ResultsList } from './ResultsList'
import * as searchApi from '../../api/search'
import * as jobsApi from '../../api/jobs'
import type { JobPosting } from '../../types'

// Mock API modules
vi.mock('../../api/search')
vi.mock('../../api/jobs')

const mockGetSearchStatus = vi.mocked(searchApi.getSearchStatus)
const mockListJobs = vi.mocked(jobsApi.listJobs)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const sampleJob: JobPosting = {
  id: 'job-1',
  source: 'greenhouse',
  title: 'Senior React Engineer',
  company: 'Acme Corp',
  location: 'San Francisco, CA',
  remote_status: 'remote',
  url: 'https://example.com/jobs/1',
  compensation: '$150k–$180k',
  posted_date: '2026-05-20',
  match_score: 85,
}

beforeEach(() => {
  vi.clearAllMocks()
  // Reset store
  useJobSearchStore.setState({ activeSearchJobId: null })
})

describe('ResultsList', () => {
  it('renders nothing when no active search', () => {
    const { container } = render(<ResultsList />, { wrapper })
    expect(container.firstChild).toBeNull()
  })

  it('shows loading spinner when status is running', async () => {
    mockGetSearchStatus.mockResolvedValue({
      job_id: 'search-1',
      status: 'running',
      total_results: null,
      error: null,
    })

    useJobSearchStore.setState({ activeSearchJobId: 'search-1' })
    render(<ResultsList />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('status', { name: /searching job boards/i })).toBeInTheDocument()
    })
  })

  it('shows loading spinner when status is queued', async () => {
    mockGetSearchStatus.mockResolvedValue({
      job_id: 'search-1',
      status: 'queued',
      total_results: null,
      error: null,
    })

    useJobSearchStore.setState({ activeSearchJobId: 'search-1' })
    render(<ResultsList />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument()
    })
  })

  it('shows empty state when search completes with 0 results', async () => {
    mockGetSearchStatus.mockResolvedValue({
      job_id: 'search-1',
      status: 'complete',
      total_results: 0,
      error: null,
    })
    mockListJobs.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })

    useJobSearchStore.setState({ activeSearchJobId: 'search-1' })
    render(<ResultsList />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText(/no jobs found/i)).toBeInTheDocument()
    })
  })

  it('shows job cards when results are present', async () => {
    mockGetSearchStatus.mockResolvedValue({
      job_id: 'search-1',
      status: 'complete',
      total_results: 1,
      error: null,
    })
    mockListJobs.mockResolvedValue({ items: [sampleJob], total: 1, page: 1, page_size: 20 })

    useJobSearchStore.setState({ activeSearchJobId: 'search-1' })
    render(<ResultsList />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Senior React Engineer')).toBeInTheDocument()
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })
  })

  it('shows error banner on search status failure', async () => {
    mockGetSearchStatus.mockRejectedValue(new Error('Network error'))

    useJobSearchStore.setState({ activeSearchJobId: 'search-1' })
    render(<ResultsList />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })
})
