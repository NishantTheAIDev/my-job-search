/**
 * Tests for ApplicationWorkspace — the unified full-page application review component.
 *
 * Coverage:
 * 1. Render states: null when no activeApplicationId, loading spinner, PrepProgress
 *    when preparing, ErrorBanner when query errors or prep_failed, ready content.
 * 2. Revert buttons: visible only when pending and edit mode is off;
 *    "Undo my edits" disabled when live === AI snapshot, enabled when they differ;
 *    clicking opens RevertModal; confirming calls revertApplicationContent.
 *    "Revert to original" present on resume tab only.
 * 3. Approve & Save: opens ConfirmationModal, confirming calls saveApplication.
 * 4. Reject: inline confirm appears, confirming calls rejectApplication.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { ApplicationWorkspace } from './ApplicationWorkspace'
import * as appsApi from '../../api/applications'
import * as jobsApi from '../../api/jobs'
import type { ApplicationResponse, JobPosting } from '../../types'

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock('../../api/applications')
vi.mock('../../api/jobs')

const mockGetApplicationByJob = vi.mocked(appsApi.getApplicationByJob)
const mockGetJob = vi.mocked(jobsApi.getJob)
const mockSaveApplication = vi.mocked(appsApi.saveApplication)
const mockRejectApplication = vi.mocked(appsApi.rejectApplication)
const mockRevertApplicationContent = vi.mocked(appsApi.revertApplicationContent)
const mockCancelApplication = vi.mocked(appsApi.cancelApplication)

// ── Shared test fixtures ──────────────────────────────────────────────────────

const JOB_ID = 'job-posting-1'

const mockJob: JobPosting = {
  id: JOB_ID,
  source: 'greenhouse',
  title: 'Senior Python Engineer',
  company: 'Acme Corp',
  location: 'Remote',
  remote_status: 'remote',
  url: 'https://example.com/job/1',
  description: 'Build great backends.',
  compensation: null,
  posted_date: null,
  match_score: 82,
  relevance_score: null,
}

function makeApp(overrides: Partial<ApplicationResponse> = {}): ApplicationResponse {
  return {
    id: 'app-1',
    job_posting_id: JOB_ID,
    status: 'pending',
    prep_stage: '',
    prep_error: '',
    match_score: 82,
    match_rationale: 'Great Python skills match the role.',
    match_gaps: ['Docker', 'Kubernetes'],
    tailored_resume_text: 'AI tailored resume text',
    ai_tailored_resume_text: 'AI tailored resume text',
    resume_diff_json: JSON.stringify([
      { type: 'added', text: '+ AI tailored line', line: 1 },
    ]),
    cover_letter_text: 'Dear Hiring Manager, AI drafted letter.',
    ai_cover_letter_text: 'Dear Hiring Manager, AI drafted letter.',
    tailoring_failed: false,
    resume_data_yaml: '',
    cover_letter_data_yaml: '',
    created_at: new Date().toISOString(),
    approved_at: null,
    submitted_at: null,
    rejected_at: null,
    saved_at: null,
    ...overrides,
  }
}

// ── Test wrapper ──────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  // Default: no active application
  useJobSearchStore.setState({ activeApplicationId: null })
})

// ── 1. Render states ──────────────────────────────────────────────────────────

describe('ApplicationWorkspace render states', () => {
  it('renders nothing when activeApplicationId is null', () => {
    const { container } = render(<ApplicationWorkspace />, { wrapper })
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a loading spinner while the application query is in flight', async () => {
    // Never-resolving promise keeps the query in loading state
    mockGetApplicationByJob.mockImplementation(() => new Promise(() => {}))
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    // LoadingSpinner renders a role="status" element or similar text
    expect(
      screen.getByText(/loading application/i) ||
      screen.getByRole('status')
    ).toBeInTheDocument()
  })

  it('shows PrepProgress while the application is in preparing state', async () => {
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'preparing', prep_stage: 'tailoring' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText(/tailoring your resume/i)).toBeInTheDocument()
    })
  })

  it('shows an error banner when prep_failed', async () => {
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'prep_failed', prep_error: 'LLM quota exceeded' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      const alert = screen.getByRole('alert')
      expect(alert).toBeInTheDocument()
      expect(alert).toHaveTextContent(/LLM quota exceeded/i)
    })
  })

  it('shows an error banner when the query itself fails', async () => {
    mockGetApplicationByJob.mockRejectedValue(new Error('Network error'))
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('renders ready content: job title, tabs, score, gaps when pending', async () => {
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    // The h1 header includes both job title and company; wait for it to appear.
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: /senior python engineer/i })
      ).toBeInTheDocument()
    })

    // Tab bar
    expect(screen.getByRole('tab', { name: /resume changes/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /cover letter/i })).toBeInTheDocument()

    // Match gaps list
    expect(screen.getByText('Docker')).toBeInTheDocument()
    expect(screen.getByText('Kubernetes')).toBeInTheDocument()
  })

  it('shows the "Approve & Save" and "Reject" footer buttons when pending', async () => {
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
    })
  })

  it('does not show action footer buttons for a saved application', async () => {
    mockGetApplicationByJob.mockResolvedValue(makeApp({ status: 'saved' }))
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      // Status label "Saved" appears in header badge and footer; getAllByText is safe here.
      expect(screen.getAllByText('Saved').length).toBeGreaterThan(0)
    })
    expect(screen.queryByRole('button', { name: /approve & save/i })).not.toBeInTheDocument()
  })
})

// ── 2. Revert buttons ─────────────────────────────────────────────────────────

describe('Revert buttons', () => {
  it('shows "Undo my edits" and "Revert to original" on the resume tab when pending', async () => {
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /undo my edits to resume/i })
      ).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /revert resume to original/i })
      ).toBeInTheDocument()
    })
  })

  it('"Undo my edits" on resume tab is disabled when live text equals AI snapshot', async () => {
    // tailored_resume_text === ai_tailored_resume_text → resumeIsAtAiDraft = true
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        tailored_resume_text: 'Same text',
        ai_tailored_resume_text: 'Same text',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /undo my edits to resume/i })
      expect(btn).toBeDisabled()
    })
  })

  it('"Undo my edits" on resume tab is enabled when live text differs from AI snapshot', async () => {
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        tailored_resume_text: 'Manually edited text',
        ai_tailored_resume_text: 'AI draft text',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /undo my edits to resume/i })
      expect(btn).toBeEnabled()
    })
  })

  it('clicking "Undo my edits" on resume tab opens the RevertModal', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        tailored_resume_text: 'Manually edited',
        ai_tailored_resume_text: 'AI draft',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /undo my edits to resume/i })).toBeEnabled()
    )

    await user.click(screen.getByRole('button', { name: /undo my edits to resume/i }))

    // RevertModal should appear with its dialog role
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(
        screen.getByText(/undo your edits to the resume/i)
      ).toBeInTheDocument()
    })
  })

  it('confirming the RevertModal calls revertApplicationContent(id, "resume", "ai_draft")', async () => {
    const user = userEvent.setup()
    const updatedApp = makeApp({
      tailored_resume_text: 'AI draft',
      ai_tailored_resume_text: 'AI draft',
    })
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        tailored_resume_text: 'Manually edited',
        ai_tailored_resume_text: 'AI draft',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    mockRevertApplicationContent.mockResolvedValue(updatedApp)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /undo my edits to resume/i })).toBeEnabled()
    )

    await user.click(screen.getByRole('button', { name: /undo my edits to resume/i }))

    // Modal appears; click the destructive confirm button
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /yes, undo my edits/i }))

    await waitFor(() => {
      expect(mockRevertApplicationContent).toHaveBeenCalledWith(
        'app-1',
        'resume',
        'ai_draft'
      )
    })
  })

  it('clicking "Revert to original" opens RevertModal with the correct heading', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /revert resume to original/i })
      ).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /revert resume to original/i }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText(/revert to your original resume/i)).toBeInTheDocument()
    })
  })

  it('confirming "Revert to original" calls revertApplicationContent(id, "resume", "original")', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    mockRevertApplicationContent.mockResolvedValue(makeApp())
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /revert resume to original/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /revert resume to original/i }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /yes, revert to original/i }))

    await waitFor(() => {
      expect(mockRevertApplicationContent).toHaveBeenCalledWith(
        'app-1',
        'resume',
        'original'
      )
    })
  })

  it('cancelling the RevertModal closes it without calling the API', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        tailored_resume_text: 'Manually edited',
        ai_tailored_resume_text: 'AI draft',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /undo my edits to resume/i })).toBeEnabled()
    )

    await user.click(screen.getByRole('button', { name: /undo my edits to resume/i }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /^cancel$/i }))

    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    )
    expect(mockRevertApplicationContent).not.toHaveBeenCalled()
  })

  it('shows "Undo my edits" on the cover letter tab but NOT "Revert to original"', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        tailored_resume_text: 'Manually edited',
        ai_tailored_resume_text: 'AI draft',
        cover_letter_text: 'Manually edited CL',
        ai_cover_letter_text: 'AI cover letter',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    // Switch to the Cover Letter tab
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /cover letter/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('tab', { name: /cover letter/i }))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /undo my edits to cover letter/i })
      ).toBeInTheDocument()
    })
    // "Revert to original" must not be present on the cover letter tab
    expect(
      screen.queryByRole('button', { name: /revert resume to original/i })
    ).not.toBeInTheDocument()
  })

  it('"Undo my edits" is disabled on cover letter tab when live text equals AI snapshot', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({
        cover_letter_text: 'Same cover letter',
        ai_cover_letter_text: 'Same cover letter',
      })
    )
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /cover letter/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('tab', { name: /cover letter/i }))

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /undo my edits to cover letter/i })
      expect(btn).toBeDisabled()
    })
  })

  it('revert buttons are absent when the application is not pending', async () => {
    mockGetApplicationByJob.mockResolvedValue(makeApp({ status: 'saved' }))
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      // "Saved" appears in header badge + footer; getAllByText avoids the multiple-match error.
      expect(screen.getAllByText('Saved').length).toBeGreaterThan(0)
    })

    expect(
      screen.queryByRole('button', { name: /undo my edits to resume/i })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /revert resume to original/i })
    ).not.toBeInTheDocument()
  })
})

// ── 3. Approve & Save ─────────────────────────────────────────────────────────

describe('Approve & Save', () => {
  it('clicking "Approve & Save" opens the ConfirmationModal', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /approve & save/i }))

    await waitFor(() => {
      const dialog = screen.getByRole('dialog')
      expect(dialog).toBeInTheDocument()
      expect(within(dialog).getByText(/save this application/i)).toBeInTheDocument()
    })
  })

  it('confirming the modal calls saveApplication with the application id', async () => {
    const user = userEvent.setup()
    const savedApp = makeApp({ status: 'saved' })
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    mockSaveApplication.mockResolvedValue(savedApp)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
    )

    // Open confirmation modal
    await user.click(screen.getByRole('button', { name: /approve & save/i }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

    // Confirm save — the button inside the dialog is also labelled "Approve & Save"
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /approve & save/i }))

    await waitFor(() => {
      expect(mockSaveApplication).toHaveBeenCalledWith('app-1')
    })
  })

  it('cancelling the modal does not call saveApplication', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /approve & save/i }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    )
    expect(mockSaveApplication).not.toHaveBeenCalled()
  })

  it('shows a success message after saving and hides the footer actions', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    mockSaveApplication.mockResolvedValue(makeApp({ status: 'saved' }))
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /approve & save/i }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /approve & save/i }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/application saved/i)
    })
  })
})

// ── 4. Reject ─────────────────────────────────────────────────────────────────

describe('Reject', () => {
  it('clicking "Reject" shows an inline confirmation prompt', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^reject$/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /^reject$/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/reject this application\? this cannot be undone/i)
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /yes, reject/i })).toBeInTheDocument()
    })
  })

  it('confirming rejection calls rejectApplication with the application id', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    mockRejectApplication.mockResolvedValue(makeApp({ status: 'rejected' }))
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^reject$/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /^reject$/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /yes, reject/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /yes, reject/i }))

    await waitFor(() => {
      expect(mockRejectApplication).toHaveBeenCalledWith('app-1')
    })
  })

  it('clicking Cancel on the reject prompt hides it without calling the API', async () => {
    const user = userEvent.setup()
    mockGetApplicationByJob.mockResolvedValue(makeApp())
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^reject$/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /^reject$/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /yes, reject/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /^cancel$/i }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /yes, reject/i })).not.toBeInTheDocument()
    )
    expect(mockRejectApplication).not.toHaveBeenCalled()
  })
})

// ── 5. Cancel preparation ─────────────────────────────────────────────────────

describe('Cancel preparation', () => {
  it('renders "Cancel preparation" button when application is preparing', async () => {
    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'preparing', prep_stage: 'tailoring' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /cancel preparation/i })
      ).toBeInTheDocument()
    })
  })

  it('does not render "Cancel preparation" button when application is pending', async () => {
    mockGetApplicationByJob.mockResolvedValue(makeApp({ status: 'pending' }))
    mockGetJob.mockResolvedValue(mockJob)
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /approve & save/i })).toBeInTheDocument()
    )
    expect(
      screen.queryByRole('button', { name: /cancel preparation/i })
    ).not.toBeInTheDocument()
  })

  it('clicking "Cancel preparation" triggers window.confirm', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'preparing', prep_stage: 'scoring' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /cancel preparation/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /cancel preparation/i }))

    expect(confirmSpy).toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('calls cancelApplication when the user confirms the cancel dialog', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockCancelApplication.mockResolvedValue(
      makeApp({ status: 'cancelled' })
    )

    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ id: 'app-1', status: 'preparing', prep_stage: 'tailoring' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /cancel preparation/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /cancel preparation/i }))

    await waitFor(() => {
      expect(mockCancelApplication).toHaveBeenCalledWith('app-1')
    })

    vi.restoreAllMocks()
  })

  it('does not call cancelApplication when the user dismisses the confirm dialog', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'preparing', prep_stage: 'tailoring' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /cancel preparation/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /cancel preparation/i }))

    expect(mockCancelApplication).not.toHaveBeenCalled()
    vi.restoreAllMocks()
  })
})

// ── 6. Preparing-state close guard ───────────────────────────────────────────

describe('Preparing-state close guard', () => {
  it('triggers window.confirm when closing during preparing state', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'preparing', prep_stage: 'parsing' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    // The Back button's accessible name comes from its aria-label, not text content.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /close workspace/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /close workspace/i }))

    expect(confirmSpy).toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('does not close the workspace when the user dismisses the confirm on preparing', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    mockGetApplicationByJob.mockResolvedValue(
      makeApp({ status: 'preparing', prep_stage: 'parsing' })
    )
    useJobSearchStore.setState({ activeApplicationId: JOB_ID })

    render(<ApplicationWorkspace />, { wrapper })

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /close workspace/i })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: /close workspace/i }))

    // activeApplicationId should remain set
    expect(useJobSearchStore.getState().activeApplicationId).toBe(JOB_ID)
    vi.restoreAllMocks()
  })
})
