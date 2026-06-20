import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ApprovalScreen } from './ApprovalScreen'
import * as applicationsApi from '../../api/applications'
import * as jobsApi from '../../api/jobs'
import type { ApplicationResponse, JobPosting } from '../../types'

vi.mock('../../api/applications')
vi.mock('../../api/jobs')

const mockGetApplicationByJob = vi.mocked(applicationsApi.getApplicationByJob)
const mockSaveApplication = vi.mocked(applicationsApi.saveApplication)
const mockGetJob = vi.mocked(jobsApi.getJob)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const sampleApplication: ApplicationResponse = {
  id: 'app-1',
  job_posting_id: 'job-1',
  status: 'pending',
  prep_stage: '',
  prep_error: '',
  match_score: 82,
  match_rationale: 'Strong React and TypeScript skills',
  tailored_resume_text: 'Tailored resume content here...',
  resume_diff_json: '[]',
  cover_letter_text: 'Dear Hiring Manager...',
  tailoring_failed: false,
  resume_data_yaml: '',
  cover_letter_data_yaml: '',
  created_at: '2026-05-20T10:00:00Z',
  approved_at: null,
  submitted_at: null,
  rejected_at: null,
  match_gaps: [],
  saved_at: null,
}

const sampleJob: JobPosting = {
  id: 'job-1',
  source: 'greenhouse',
  title: 'Senior React Engineer',
  company: 'Acme Corp',
  location: 'San Francisco, CA',
  remote_status: 'remote',
  url: 'https://example.com',
  description: 'We are looking for a Senior React Engineer.',
  compensation: null,
  posted_date: null,
  match_score: 82,
  relevance_score: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.setState({ activeApplicationId: 'job-1', showApproval: true })
  mockGetApplicationByJob.mockResolvedValue(sampleApplication)
  mockGetJob.mockResolvedValue(sampleJob)
})

describe('ApprovalScreen', () => {
  it('renders job title and company after loading', async () => {
    render(<ApprovalScreen />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Senior React Engineer')).toBeInTheDocument()
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })
  })

  it('renders Approve & Save button', async () => {
    render(<ApprovalScreen />, { wrapper })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
    })
  })

  it('opens confirmation modal on Approve & Save click', async () => {
    const user = userEvent.setup()
    render(<ApprovalScreen />, { wrapper })
    await waitFor(() => screen.getByRole('button', { name: /approve & save/i }))
    await user.click(screen.getByRole('button', { name: /approve & save/i }))
    expect(screen.getByRole('dialog', { name: /save this application/i })).toBeInTheDocument()
  })

  it('Confirm button is disabled while request is in flight', async () => {
    const user = userEvent.setup()
    // Save takes a while
    mockSaveApplication.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ ...sampleApplication, status: 'saved' as const }), 5000))
    )

    render(<ApprovalScreen />, { wrapper })
    await waitFor(() => screen.getByRole('button', { name: /approve & save/i }))
    await user.click(screen.getByRole('button', { name: /approve & save/i }))

    // The modal's confirm button text is "Approve & Save"
    const modalConfirmBtn = screen.getAllByRole('button', { name: /approve & save/i })[1]
    await user.click(modalConfirmBtn)

    // After click, button should be disabled (in-flight)
    expect(modalConfirmBtn).toBeDisabled()
  })

  it('shows success message after save', async () => {
    const user = userEvent.setup()
    mockSaveApplication.mockResolvedValue({ ...sampleApplication, status: 'saved' as const })

    render(<ApprovalScreen />, { wrapper })
    await waitFor(() => screen.getByRole('button', { name: /approve & save/i }))
    await user.click(screen.getByRole('button', { name: /approve & save/i }))
    // Click the modal confirm button (second one with that name)
    const confirmBtns = screen.getAllByRole('button', { name: /approve & save/i })
    await user.click(confirmBtns[confirmBtns.length - 1])

    await waitFor(() => {
      expect(screen.getByText(/application saved for acme corp/i)).toBeInTheDocument()
    })
  })

  it('shows 409 error message when already saved', async () => {
    const user = userEvent.setup()
    const error = Object.assign(new Error('Conflict'), {
      response: { status: 409, data: { detail: 'Application already submitted.' } },
    })
    mockSaveApplication.mockRejectedValue(error)

    render(<ApprovalScreen />, { wrapper })
    await waitFor(() => screen.getByRole('button', { name: /approve & save/i }))
    await user.click(screen.getByRole('button', { name: /approve & save/i }))
    const confirmBtns = screen.getAllByRole('button', { name: /approve & save/i })
    await user.click(confirmBtns[confirmBtns.length - 1])

    await waitFor(() => {
      expect(screen.getByText(/application already submitted/i)).toBeInTheDocument()
    })
  })
})
