import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { JobDetailSlideOver } from './JobDetailSlideOver'
import type { JobPosting } from '../../types'

vi.mock('../../api/jobs')

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const job: JobPosting = {
  id: 'job-1',
  source: 'greenhouse',
  title: 'Senior React Engineer',
  company: 'Acme Corp',
  location: 'Remote',
  remote_status: 'remote',
  url: 'https://example.com/jobs/1',
  description: 'Build great UIs.',
  compensation: null,
  posted_date: null,
  match_score: 80,
  relevance_score: null,
}

beforeEach(() => {
  useJobSearchStore.setState({ selectedJob: null })
})

describe('JobDetailSlideOver', () => {
  it('renders nothing when no job is selected', () => {
    const { container } = render(<JobDetailSlideOver />, { wrapper })
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the selected job and closes on Escape', async () => {
    useJobSearchStore.setState({ selectedJob: job })
    render(<JobDetailSlideOver />, { wrapper })

    expect(screen.getByRole('heading', { name: /senior react engineer/i })).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(useJobSearchStore.getState().selectedJob).toBeNull())
  })

  it('closes when the close button is clicked', async () => {
    useJobSearchStore.setState({ selectedJob: job })
    render(<JobDetailSlideOver />, { wrapper })

    await userEvent.click(screen.getByRole('button', { name: /close job detail/i }))
    await waitFor(() => expect(useJobSearchStore.getState().selectedJob).toBeNull())
  })
})
