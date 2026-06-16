import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { SavedSearchesPage } from './SavedSearchesPage'
import * as savedSearchesApi from '../../api/savedSearches'
import type { SavedSearch } from '../../types'

vi.mock('../../api/savedSearches', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/savedSearches')>()
  return {
    ...actual,
    listSavedSearches: vi.fn(),
    runSavedSearch: vi.fn(),
    deleteSavedSearch: vi.fn(),
  }
})

const mockList = vi.mocked(savedSearchesApi.listSavedSearches)
const mockRun = vi.mocked(savedSearchesApi.runSavedSearch)
const mockDelete = vi.mocked(savedSearchesApi.deleteSavedSearch)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const sample: SavedSearch[] = [
  {
    id: 'ss-1',
    name: 'Remote AI roles',
    criteria: { query: 'ai engineer', remote_only: true, page: 1 },
    created_at: '2026-06-14T10:00:00Z',
    last_run_at: null,
    last_search_job_id: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.getState().resetToLanding()
})

it('renders the saved searches list', async () => {
  mockList.mockResolvedValue(sample)
  render(<SavedSearchesPage />, { wrapper })

  expect(await screen.findByText('Remote AI roles')).toBeInTheDocument()
  expect(screen.getByText(/"ai engineer"/)).toBeInTheDocument()
  expect(screen.getByText(/Not run yet/)).toBeInTheDocument()
})

it('shows the empty state when there are no saved searches', async () => {
  mockList.mockResolvedValue([])
  render(<SavedSearchesPage />, { wrapper })
  expect(await screen.findByText('No saved searches yet')).toBeInTheDocument()
})

it('runs a saved search and navigates to results', async () => {
  mockList.mockResolvedValue(sample)
  mockRun.mockResolvedValue({
    saved_search_id: 'ss-1',
    search_job_id: 'job-99',
    status: 'queued',
  })
  render(<SavedSearchesPage />, { wrapper })

  await screen.findByText('Remote AI roles')
  await userEvent.click(screen.getByLabelText('Run saved search: Remote AI roles'))

  await waitFor(() => expect(mockRun).toHaveBeenCalledWith('ss-1'))
  const state = useJobSearchStore.getState()
  expect(state.activeSearchJobId).toBe('job-99')
  expect(state.activeSavedSearchId).toBe('ss-1')
  expect(state.showSavedSearches).toBe(false)
})

it('deletes a saved search after confirmation', async () => {
  mockList.mockResolvedValue(sample)
  mockDelete.mockResolvedValue()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  render(<SavedSearchesPage />, { wrapper })

  await screen.findByText('Remote AI roles')
  await userEvent.click(screen.getByLabelText('Delete saved search: Remote AI roles'))

  await waitFor(() => expect(mockDelete).toHaveBeenCalledWith('ss-1'))
})
