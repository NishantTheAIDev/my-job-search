import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SavedApplicationDetail } from './SavedApplicationDetail'
import * as applicationsApi from '../../api/applications'
import type { ApplicationResponse } from '../../types'

vi.mock('../../api/applications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/applications')>()
  return { ...actual, getApplication: vi.fn() }
})

const mockGetApplication = vi.mocked(applicationsApi.getApplication)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const baseDetail: ApplicationResponse = {
  id: 'app-1',
  job_posting_id: 'job-1',
  status: 'saved',
  prep_stage: '',
  prep_error: '',
  match_score: 70,
  match_rationale: 'Solid overlap.',
  tailored_resume_text: 'RESUME',
  resume_diff_json: '[]',
  cover_letter_text: 'COVER',
  tailoring_failed: false,
  resume_data_yaml: '',
  cover_letter_data_yaml: '',
  match_gaps: [],
  created_at: '2026-06-14T09:00:00Z',
  approved_at: null,
  submitted_at: null,
  saved_at: '2026-06-14T10:00:00Z',
  rejected_at: null,
}

beforeEach(() => vi.clearAllMocks())

describe('SavedApplicationDetail', () => {
  it('hides the gaps section when there are no gaps', async () => {
    mockGetApplication.mockResolvedValue(baseDetail)
    render(<SavedApplicationDetail applicationId="app-1" onClose={() => {}} />, { wrapper })

    await waitFor(() => screen.getByText('RESUME'))
    expect(screen.queryByLabelText('Match gaps list')).not.toBeInTheDocument()
  })

  it('shows the gaps section when gaps exist', async () => {
    mockGetApplication.mockResolvedValue({ ...baseDetail, match_gaps: ['Docker', 'AWS'] })
    render(<SavedApplicationDetail applicationId="app-1" onClose={() => {}} />, { wrapper })

    await waitFor(() => screen.getByLabelText('Match gaps list'))
    expect(screen.getByText('Docker')).toBeInTheDocument()
    expect(screen.getByText('AWS')).toBeInTheDocument()
  })

  it('shows an error banner when the fetch fails', async () => {
    mockGetApplication.mockRejectedValue(new Error('boom'))
    render(<SavedApplicationDetail applicationId="app-1" onClose={() => {}} />, { wrapper })
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
