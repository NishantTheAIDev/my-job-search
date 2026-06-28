import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { SavedApplicationsPage } from './SavedApplicationsPage'
import * as applicationsApi from '../../api/applications'
import type { SavedApplicationSummary, ApplicationResponse } from '../../types'

vi.mock('../../api/applications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/applications')>()
  return {
    ...actual,
    listSavedApplications: vi.fn(),
    getApplication: vi.fn(),
  }
})

const mockList = vi.mocked(applicationsApi.listSavedApplications)
const mockGetApplication = vi.mocked(applicationsApi.getApplication)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const sampleList: SavedApplicationSummary[] = [
  {
    id: 'app-1',
    job_title: 'Senior Python Engineer',
    company: 'Acme Corp',
    location: 'Remote',
    match_score: 82,
    saved_at: '2026-06-14T10:00:00Z',
  },
]

const sampleDetail: ApplicationResponse = {
  id: 'app-1',
  job_posting_id: 'job-1',
  status: 'saved',
  prep_stage: '',
  prep_error: '',
  match_score: 82,
  match_rationale: 'Strong Python and FastAPI overlap.',
  tailored_resume_text: 'TAILORED RESUME BODY',
  ai_tailored_resume_text: 'TAILORED RESUME BODY',
  resume_diff_json: '[]',
  cover_letter_text: 'COVER LETTER BODY',
  ai_cover_letter_text: 'COVER LETTER BODY',
  tailoring_failed: false,
  resume_data_yaml: '',
  cover_letter_data_yaml: '',
  match_gaps: ['Kubernetes experience'],
  created_at: '2026-06-14T09:00:00Z',
  approved_at: null,
  submitted_at: null,
  saved_at: '2026-06-14T10:00:00Z',
  rejected_at: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.setState({ showSavedApplications: true, activeSearchJobId: null })
})

describe('SavedApplicationsPage', () => {
  it('shows a loading state while fetching', () => {
    mockList.mockReturnValue(new Promise(() => {}) as never)
    render(<SavedApplicationsPage />, { wrapper })
    expect(screen.getByText(/loading saved applications/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no saved applications', async () => {
    mockList.mockResolvedValue([])
    render(<SavedApplicationsPage />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText(/no saved applications yet/i)).toBeInTheDocument()
    })
  })

  it('shows an error banner with retry when the fetch fails', async () => {
    mockList.mockRejectedValue(new Error('Network error'))
    render(<SavedApplicationsPage />, { wrapper })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('renders saved application rows', async () => {
    mockList.mockResolvedValue(sampleList)
    render(<SavedApplicationsPage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument()
    })
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /view saved application: Senior Python Engineer at Acme Corp/i,
      })
    ).toBeInTheDocument()
  })

  it('clicking a row opens the read-only detail with downloads and no edit controls', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(sampleList)
    mockGetApplication.mockResolvedValue(sampleDetail)
    render(<SavedApplicationsPage />, { wrapper })

    await waitFor(() => screen.getByText('Senior Python Engineer'))
    await user.click(
      screen.getByRole('button', {
        name: /view saved application: Senior Python Engineer at Acme Corp/i,
      })
    )

    await waitFor(() => {
      expect(mockGetApplication).toHaveBeenCalledWith('app-1')
    })

    // Read-only content renders
    await waitFor(() => {
      expect(screen.getByText('TAILORED RESUME BODY')).toBeInTheDocument()
    })
    expect(screen.getByText('COVER LETTER BODY')).toBeInTheDocument()
    expect(screen.getByText(/strong python and fastapi overlap/i)).toBeInTheDocument()
    // Gaps render
    expect(screen.getByLabelText('Match gaps list')).toBeInTheDocument()
    expect(screen.getByText('Kubernetes experience')).toBeInTheDocument()

    // No mutating controls in the saved (read-only) view
    expect(screen.queryByRole('button', { name: /approve & save/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /revise|edit/i })).not.toBeInTheDocument()
  })

  it('back button closes the saved applications view', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue([])
    render(<SavedApplicationsPage />, { wrapper })

    await waitFor(() => screen.getByText(/no saved applications yet/i))
    const backBtns = screen.getAllByRole('button', { name: /back to home/i })
    await user.click(backBtns[0])

    expect(useJobSearchStore.getState().showSavedApplications).toBe(false)
  })
})
