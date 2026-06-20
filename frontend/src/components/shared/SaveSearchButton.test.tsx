import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { SaveSearchButton } from './SaveSearchButton'
import * as savedSearchesApi from '../../api/savedSearches'

vi.mock('../../api/savedSearches', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/savedSearches')>()
  return { ...actual, createSavedSearch: vi.fn() }
})

const mockCreate = vi.mocked(savedSearchesApi.createSavedSearch)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.getState().resetToLanding()
  useJobSearchStore.getState().setCriteria({ query: 'ml engineer', remote_only: true })
})

it('expands to a name input prefilled with the current query', async () => {
  render(<SaveSearchButton />, { wrapper })
  await userEvent.click(screen.getByLabelText('Save this search'))
  const input = screen.getByLabelText('Saved search name') as HTMLInputElement
  expect(input.value).toBe('ml engineer')
})

it('creates a saved search with the entered name and current criteria', async () => {
  mockCreate.mockResolvedValue({
    id: 'ss-1',
    name: 'My ML search',
    criteria: { query: 'ml engineer', remote_only: true, page: 1 },
    created_at: '2026-06-14T10:00:00Z',
    last_run_at: null,
    last_search_job_id: null,
  })
  render(<SaveSearchButton />, { wrapper })

  await userEvent.click(screen.getByLabelText('Save this search'))
  const input = screen.getByLabelText('Saved search name')
  await userEvent.clear(input)
  await userEvent.type(input, 'My ML search')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() =>
    expect(mockCreate).toHaveBeenCalledWith(
      'My ML search',
      expect.objectContaining({ query: 'ml engineer', remote_only: true }),
    ),
  )
})
