/**
 * Tests for the ResumeEditor revise/edit controls.
 *
 * Verifies that:
 * 1. "Request changes" form (revise) and "Edit content" button render when status is 'pending'.
 * 2. Those controls are absent when status is 'submitted' (non-pending).
 * 3. The reviseApplication mutation is called with the correct target + instructions on submit.
 * 4. The editApplicationContent mutation is invoked when the user saves edited text.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ResumeEditor } from './ResumeEditor'
import * as applicationsApi from '../../api/applications'
import type { ApplicationResponse } from '../../types'

vi.mock('../../api/applications')

const mockGetApplicationByJob = vi.mocked(applicationsApi.getApplicationByJob)
const mockReviseApplication = vi.mocked(applicationsApi.reviseApplication)
const mockEditApplicationContent = vi.mocked(applicationsApi.editApplicationContent)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const baseApplication: ApplicationResponse = {
  id: 'app-1',
  job_posting_id: 'job-1',
  status: 'pending',
  prep_stage: '',
  prep_error: '',
  match_score: 75,
  match_rationale: 'Good match',
  tailored_resume_text: 'Jane Smith\n\nEXPERIENCE\nEngineer at Acme',
  resume_diff_json: JSON.stringify([
    { type: 'unchanged', text: 'Jane Smith', line: 0 },
  ]),
  cover_letter_text: 'Dear Hiring Manager, I am excited to apply.',
  tailoring_failed: false,
  resume_data_yaml: '',
  cover_letter_data_yaml: '',
  created_at: '2026-05-20T10:00:00Z',
  approved_at: null,
  submitted_at: null,
  rejected_at: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.setState({ activeApplicationId: 'job-1' })
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderEditor() {
  return render(<ResumeEditor />, { wrapper })
}

// ---------------------------------------------------------------------------
// Revise controls visible for pending applications
// ---------------------------------------------------------------------------

describe('ResumeEditor — pending application', () => {
  beforeEach(() => {
    mockGetApplicationByJob.mockResolvedValue({ ...baseApplication, status: 'pending' })
  })

  it('shows the "Request changes" form for the resume tab', async () => {
    renderEditor()
    await waitFor(() => {
      expect(screen.getByRole('form', { name: /request changes to resume/i })).toBeInTheDocument()
    })
  })

  it('shows an "Edit content" button to enter direct-edit mode', async () => {
    renderEditor()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /edit content/i })).toBeInTheDocument()
    })
  })

  it('calls reviseApplication with target=resume when form is submitted', async () => {
    const user = userEvent.setup()
    mockReviseApplication.mockResolvedValue({ ...baseApplication })
    renderEditor()

    // Wait for the revise input to appear
    const input = await screen.findByPlaceholderText(/emphasise python/i)
    await user.type(input, 'Make bullets stronger')

    const submitBtn = screen.getByRole('button', { name: /request changes/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(mockReviseApplication).toHaveBeenCalledWith(
        'app-1',
        'resume',
        'Make bullets stronger',
      )
    })
  })

  it('enters edit mode when "Edit content" is clicked', async () => {
    const user = userEvent.setup()
    renderEditor()

    const editBtn = await screen.findByRole('button', { name: /edit content/i })
    await user.click(editBtn)

    // After clicking, the textarea for direct editing should appear
    await waitFor(() => {
      expect(screen.getByRole('textbox', { name: /edit tailored resume text/i })).toBeInTheDocument()
    })
  })

  it('calls editApplicationContent with target=resume when Save resume is clicked', async () => {
    const user = userEvent.setup()
    mockEditApplicationContent.mockResolvedValue({ ...baseApplication })
    renderEditor()

    const editBtn = await screen.findByRole('button', { name: /edit content/i })
    await user.click(editBtn)

    const textarea = await screen.findByRole('textbox', { name: /edit tailored resume text/i })
    // Clear pre-filled text and type new content
    await user.clear(textarea)
    await user.type(textarea, 'Updated resume content')

    const saveBtn = screen.getByRole('button', { name: /save resume/i })
    await user.click(saveBtn)

    await waitFor(() => {
      expect(mockEditApplicationContent).toHaveBeenCalledWith(
        'app-1',
        'resume',
        expect.stringContaining('Updated resume content'),
      )
    })
  })
})

// ---------------------------------------------------------------------------
// Revise controls hidden for non-pending applications
// ---------------------------------------------------------------------------

describe('ResumeEditor — submitted application', () => {
  beforeEach(() => {
    mockGetApplicationByJob.mockResolvedValue({ ...baseApplication, status: 'submitted' })
  })

  it('does not show "Request changes" form when status is submitted', async () => {
    renderEditor()
    // Wait for data to load (some other content must be visible first)
    await waitFor(() => {
      expect(screen.queryByRole('form', { name: /request changes to resume/i })).not.toBeInTheDocument()
    })
  })

  it('does not show "Edit content" button when status is submitted', async () => {
    renderEditor()
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /edit content/i })).not.toBeInTheDocument()
    })
  })
})
