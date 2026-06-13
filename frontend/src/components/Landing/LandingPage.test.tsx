import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { LandingPage } from './LandingPage'

vi.mock('../../api/search')
vi.mock('../../api/resume')

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

beforeEach(() => {
  window.history.replaceState(null, '', '/')
  useJobSearchStore.setState({
    criteria: { query: '', remote_only: false, page: 1 },
    resumeUploaded: false,
  })
})

describe('LandingPage', () => {
  it('renders the hero, search, and how-it-works content', () => {
    render(<LandingPage />, { wrapper })
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByLabelText(/job title or keywords/i)).toBeInTheDocument()
    expect(screen.getByText(/how it works/i)).toBeInTheDocument()
    // Supported boards strip
    expect(screen.getByText('LinkedIn')).toBeInTheDocument()
  })
})
