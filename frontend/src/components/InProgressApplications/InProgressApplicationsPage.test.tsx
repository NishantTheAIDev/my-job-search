/**
 * Tests for InProgressApplicationsPage.
 *
 * Coverage:
 * 1. Loading state while the query is in flight.
 * 2. Empty state when no in-progress applications exist.
 * 3. Error state with a retry button.
 * 4. List render: job title, company, status badge per status.
 * 5. Row click: calls setActiveApplication(job_posting_id),
 *    setWorkspaceOrigin('home'), and setShowInProgressApplications(false).
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { InProgressApplicationsPage } from './InProgressApplicationsPage'
import * as applicationsApi from '../../api/applications'
import type { InProgressApplicationItem } from '../../api/applications'

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock('../../api/applications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/applications')>()
  return {
    ...actual,
    listInProgressApplications: vi.fn(),
  }
})

const mockListInProgress = vi.mocked(applicationsApi.listInProgressApplications)

// ── Test wrapper ──────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeItem(overrides: Partial<InProgressApplicationItem> = {}): InProgressApplicationItem {
  return {
    id: 'app-1',
    job_posting_id: 'job-posting-1',
    job_title: 'Senior Python Engineer',
    company: 'Acme Corp',
    location: 'Remote',
    status: 'preparing',
    match_score: 82,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.setState({
    showInProgressApplications: true,
    activeSearchJobId: null,
    activeApplicationId: null,
    workspaceOrigin: null,
  })
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('InProgressApplicationsPage', () => {
  describe('loading state', () => {
    it('shows a loading spinner while the query is in flight', () => {
      mockListInProgress.mockReturnValue(new Promise(() => {}) as never)
      render(<InProgressApplicationsPage />, { wrapper })
      expect(
        screen.getByText(/loading in-progress applications/i)
      ).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('shows an empty-state message when there are no in-progress applications', async () => {
      mockListInProgress.mockResolvedValue([])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText(/nothing in progress/i)).toBeInTheDocument()
      })
    })
  })

  describe('error state', () => {
    it('shows an error banner when the fetch fails', async () => {
      mockListInProgress.mockRejectedValue(new Error('Network error'))
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument()
      })
    })

    it('shows a retry button on error', async () => {
      mockListInProgress.mockRejectedValue(new Error('Network error'))
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
      })
    })

    it('clicking retry re-fetches the list', async () => {
      const user = userEvent.setup()
      mockListInProgress
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValue([])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
      )
      await user.click(screen.getByRole('button', { name: /try again/i }))
      // After retry resolves to empty, empty state renders
      await waitFor(() =>
        expect(screen.getByText(/nothing in progress/i)).toBeInTheDocument()
      )
    })
  })

  describe('list render', () => {
    it('renders job title and company for each item', async () => {
      mockListInProgress.mockResolvedValue([makeItem()])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument()
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      })
    })

    it('shows the "Preparing" badge for a preparing item', async () => {
      mockListInProgress.mockResolvedValue([makeItem({ status: 'preparing' })])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText('Preparing')).toBeInTheDocument()
      })
    })

    it('shows the "Pending review" badge for a pending item', async () => {
      mockListInProgress.mockResolvedValue([makeItem({ status: 'pending' })])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText('Pending review')).toBeInTheDocument()
      })
    })

    it('renders multiple items in the list', async () => {
      mockListInProgress.mockResolvedValue([
        makeItem({ id: 'app-1', job_title: 'Backend Engineer', status: 'preparing' }),
        makeItem({ id: 'app-2', job_posting_id: 'job-2', job_title: 'Frontend Engineer', status: 'pending' }),
      ])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText('Backend Engineer')).toBeInTheDocument()
        expect(screen.getByText('Frontend Engineer')).toBeInTheDocument()
      })
    })

    it('renders the list with accessible aria-label', async () => {
      mockListInProgress.mockResolvedValue([makeItem()])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(
          screen.getByRole('list', { name: /in-progress applications list/i })
        ).toBeInTheDocument()
      })
    })
  })

  describe('row click navigation', () => {
    it('clicking a row calls setActiveApplication with the job_posting_id', async () => {
      const user = userEvent.setup()
      const item = makeItem({ job_posting_id: 'job-posting-42' })
      mockListInProgress.mockResolvedValue([item])
      render(<InProgressApplicationsPage />, { wrapper })

      await waitFor(() =>
        expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument()
      )

      await user.click(
        screen.getByRole('button', {
          name: /open application: Senior Python Engineer at Acme Corp/i,
        })
      )

      expect(useJobSearchStore.getState().activeApplicationId).toBe('job-posting-42')
    })

    it('clicking a row calls setWorkspaceOrigin("home")', async () => {
      const user = userEvent.setup()
      mockListInProgress.mockResolvedValue([makeItem()])
      render(<InProgressApplicationsPage />, { wrapper })

      await waitFor(() =>
        expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument()
      )

      await user.click(
        screen.getByRole('button', {
          name: /open application: Senior Python Engineer at Acme Corp/i,
        })
      )

      expect(useJobSearchStore.getState().workspaceOrigin).toBe('home')
    })

    it('clicking a row calls setShowInProgressApplications(false)', async () => {
      const user = userEvent.setup()
      mockListInProgress.mockResolvedValue([makeItem()])
      render(<InProgressApplicationsPage />, { wrapper })

      await waitFor(() =>
        expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument()
      )

      await user.click(
        screen.getByRole('button', {
          name: /open application: Senior Python Engineer at Acme Corp/i,
        })
      )

      expect(useJobSearchStore.getState().showInProgressApplications).toBe(false)
    })
  })

  describe('header count', () => {
    it('shows "1 application" for a single item', async () => {
      mockListInProgress.mockResolvedValue([makeItem()])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText(/1 application$/i)).toBeInTheDocument()
      })
    })

    it('shows "2 applications" for multiple items', async () => {
      mockListInProgress.mockResolvedValue([
        makeItem({ id: 'a1' }),
        makeItem({ id: 'a2', job_posting_id: 'jp2' }),
      ])
      render(<InProgressApplicationsPage />, { wrapper })
      await waitFor(() => {
        expect(screen.getByText(/2 applications/i)).toBeInTheDocument()
      })
    })
  })
})
