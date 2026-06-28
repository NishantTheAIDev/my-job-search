import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { SearchBar } from './SearchBar'
import * as searchApi from '../../api/search'

vi.mock('../../api/search')
const mockCreateSearch = vi.mocked(searchApi.createSearch)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/')
  useJobSearchStore.setState({
    criteria: { query: '', remote_only: false, page: 1 },
    activeSearchJobId: null,
  })
})

describe('SearchBar', () => {
  it('disables submit until a query is entered', () => {
    render(<SearchBar variant="compact" />, { wrapper })
    expect(screen.getByRole('button', { name: /search/i })).toBeDisabled()
  })

  it('fires createSearch with the typed query and sets the active search', async () => {
    mockCreateSearch.mockResolvedValue({ job_id: 'search-9', status: 'queued', cached: false })
    render(<SearchBar variant="hero" />, { wrapper })

    await userEvent.type(screen.getByLabelText(/job title or keywords/i), 'react engineer')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => expect(mockCreateSearch).toHaveBeenCalledTimes(1))
    expect(mockCreateSearch.mock.calls[0][0]).toMatchObject({ query: 'react engineer', page: 1 })
    await waitFor(() =>
      expect(useJobSearchStore.getState().activeSearchJobId).toBe('search-9'),
    )
  })
})
