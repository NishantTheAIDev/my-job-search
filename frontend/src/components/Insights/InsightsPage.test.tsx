import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { InsightsPage } from './InsightsPage'
import * as insightsApi from '../../api/insights'
import type { Insights } from '../../types'

vi.mock('../../api/insights')

const mockGetInsights = vi.mocked(insightsApi.getInsights)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const sampleInsights: Insights = {
  region: 'in',
  currency: 'INR',
  generated_at: '2026-06-14T10:00:00Z',
  news: [
    {
      title: 'AI hiring surge in India',
      url: 'https://example.com/ai-hiring',
      domain: 'example.com',
      seendate: '20260614T100000Z',
    },
  ],
  salaries: [
    { role: 'Software Engineer', median: 1200000, currency: 'INR', sample_size: 500 },
  ],
  hottest_fields: [
    { label: 'IT Jobs', tag: 'it-jobs', openings: 12500, mean_salary: 900000, currency: 'INR' },
  ],
  trends: {
    salary_history: [{ period: '2024-01', value: 1100000 }],
    unemployment: [{ year: 2023, value: 7.1 }],
    employment: [{ year: 2023, value: 45.2 }],
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.setState({ showInsights: true, activeSearchJobId: null })
})

describe('InsightsPage', () => {
  // ── Loading state ────────────────────────────────────────────────────────────

  it('shows a loading skeleton while data is fetching', () => {
    // Never resolves during this test
    mockGetInsights.mockReturnValue(new Promise(() => {}) as any)
    render(<InsightsPage />, { wrapper })
    // Skeleton is aria-hidden but the container should be present
    const skeleton = document.querySelector('[aria-hidden="true"]')
    expect(skeleton).toBeInTheDocument()
  })

  // ── Success state ────────────────────────────────────────────────────────────

  it('renders Market News section heading after data loads', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Market News')).toBeInTheDocument()
    })
  })

  it('renders Salary Benchmarks section heading after data loads', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Salary Benchmarks')).toBeInTheDocument()
    })
  })

  it('renders Hottest Fields section heading after data loads', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Hottest Fields')).toBeInTheDocument()
    })
  })

  it('renders Hiring Trends section heading after data loads', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Hiring Trends')).toBeInTheDocument()
    })
  })

  it('shows the generated_at timestamp in the header', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    await waitFor(() => {
      // "Updated <formatted date>" should appear
      expect(screen.getByText(/updated/i)).toBeInTheDocument()
    })
  })

  // ── Error state ──────────────────────────────────────────────────────────────

  it('shows an error banner when the fetch fails', async () => {
    mockGetInsights.mockRejectedValue(new Error('Network error'))
    render(<InsightsPage />, { wrapper })

    // InsightsPage uses retry:2 in useQuery — allow enough time for all retries to exhaust
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    }, { timeout: 8000 })
  })

  it('shows a "try again" retry button on error', async () => {
    mockGetInsights.mockRejectedValue(new Error('Network error'))
    render(<InsightsPage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    }, { timeout: 8000 })
  })

  it('re-fetches when retry button is clicked', async () => {
    const user = userEvent.setup()
    // Fail all initial calls (initial + 2 retries), then succeed on the manual refetch
    mockGetInsights
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue(sampleInsights)

    render(<InsightsPage />, { wrapper })

    await waitFor(() => screen.getByRole('button', { name: /try again/i }), { timeout: 8000 })
    await user.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() => {
      expect(screen.getByText('Market News')).toBeInTheDocument()
    }, { timeout: 8000 })
    expect(mockGetInsights).toHaveBeenCalledTimes(4) // 3 failures + 1 success
  })

  // ── Region selector ──────────────────────────────────────────────────────────

  it('renders all four region buttons', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    // Region selector group
    const group = screen.getByRole('group', { name: /select region/i })
    expect(group).toBeInTheDocument()

    const buttons = screen.getAllByRole('button', { name: /india|united states|united kingdom|worldwide/i })
    expect(buttons.length).toBe(4)
  })

  it('India button is selected by default (aria-pressed=true)', async () => {
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    const indiaBtn = screen.getByRole('button', { name: /india/i })
    expect(indiaBtn).toHaveAttribute('aria-pressed', 'true')
  })

  it('switching region calls getInsights with the new region code', async () => {
    const user = userEvent.setup()
    mockGetInsights.mockResolvedValue({ ...sampleInsights, region: 'us' })
    render(<InsightsPage />, { wrapper })

    const usBtn = screen.getByRole('button', { name: /united states/i })
    await user.click(usBtn)

    await waitFor(() => {
      // getInsights should have been called with 'us'
      expect(mockGetInsights).toHaveBeenCalledWith('us')
    })
  })

  it('switching region updates aria-pressed on the new region button', async () => {
    const user = userEvent.setup()
    mockGetInsights.mockResolvedValue({ ...sampleInsights, region: 'gb' })
    render(<InsightsPage />, { wrapper })

    const gbBtn = screen.getByRole('button', { name: /united kingdom/i })
    await user.click(gbBtn)

    expect(gbBtn).toHaveAttribute('aria-pressed', 'true')
  })

  // ── Back button ──────────────────────────────────────────────────────────────

  it('back button calls setShowInsights(false) when clicked', async () => {
    const user = userEvent.setup()
    mockGetInsights.mockResolvedValue(sampleInsights)
    render(<InsightsPage />, { wrapper })

    // There are two back buttons (desktop + mobile); click the first visible one
    const backBtns = screen.getAllByRole('button', { name: /back to home/i })
    await user.click(backBtns[0])

    expect(useJobSearchStore.getState().showInsights).toBe(false)
  })
})
