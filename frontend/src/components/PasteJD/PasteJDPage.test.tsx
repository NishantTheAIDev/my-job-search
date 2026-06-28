import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { PasteJDPage } from './PasteJDPage'
import * as jobsApi from '../../api/jobs'

vi.mock('../../api/jobs')

const mockCreateManual = vi.mocked(jobsApi.createManualApplication)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobSearchStore.setState({
    showPasteJd: true,
    activeApplicationId: null,
    resumeUploaded: true,
    activeSearchJobId: null,
  })
})

describe('PasteJDPage', () => {
  it('gates behind an active resume — shows upload prompt when none uploaded', () => {
    useJobSearchStore.setState({ resumeUploaded: false })
    render(<PasteJDPage />, { wrapper })

    expect(screen.getByText(/upload your resume first/i)).toBeInTheDocument()
    // The JD textarea must not be shown until a resume exists
    expect(screen.queryByLabelText(/job description/i)).not.toBeInTheDocument()
  })

  it('shows the JD form once a resume is uploaded', () => {
    render(<PasteJDPage />, { wrapper })
    expect(screen.getByLabelText(/job description/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/company/i)).toBeInTheDocument()
  })

  it('keeps submit disabled until the JD textarea has content', async () => {
    const user = userEvent.setup()
    render(<PasteJDPage />, { wrapper })

    const submit = screen.getByRole('button', { name: /tailor & review/i })
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/job description/i), 'Senior Python Engineer JD')
    expect(submit).toBeEnabled()
  })

  it('submitting calls createManualApplication and opens the workspace', async () => {
    const user = userEvent.setup()
    mockCreateManual.mockResolvedValue({ status: 'preparing', job_id: 'job-123' })
    render(<PasteJDPage />, { wrapper })

    await user.type(screen.getByLabelText(/job description/i), '  Backend role  ')
    await user.type(screen.getByLabelText(/job title/i), 'Engineer')
    await user.type(screen.getByLabelText(/company/i), 'Acme')
    await user.click(screen.getByRole('button', { name: /tailor & review/i }))

    await waitFor(() => {
      expect(mockCreateManual).toHaveBeenCalledWith({
        jd_text: 'Backend role',
        title: 'Engineer',
        company: 'Acme',
      })
    })

    await waitFor(() => {
      const state = useJobSearchStore.getState()
      expect(state.activeApplicationId).toBe('job-123')
      expect(state.showPasteJd).toBe(false)
    })
  })

  it('omits empty optional fields from the request', async () => {
    const user = userEvent.setup()
    mockCreateManual.mockResolvedValue({ status: 'preparing', job_id: 'job-9' })
    render(<PasteJDPage />, { wrapper })

    await user.type(screen.getByLabelText(/job description/i), 'Only a JD')
    await user.click(screen.getByRole('button', { name: /tailor & review/i }))

    await waitFor(() => {
      expect(mockCreateManual).toHaveBeenCalledWith({
        jd_text: 'Only a JD',
        title: undefined,
        company: undefined,
      })
    })
  })

  it('renders an error banner when the mutation fails', async () => {
    const user = userEvent.setup()
    mockCreateManual.mockRejectedValue(new Error('boom'))
    render(<PasteJDPage />, { wrapper })

    await user.type(screen.getByLabelText(/job description/i), 'A JD')
    await user.click(screen.getByRole('button', { name: /tailor & review/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    // Stays on the paste page; workspace not opened
    expect(useJobSearchStore.getState().activeApplicationId).toBeNull()
  })

  it('back button closes the paste page', async () => {
    const user = userEvent.setup()
    render(<PasteJDPage />, { wrapper })

    const backBtns = screen.getAllByRole('button', { name: /back to home/i })
    await user.click(backBtns[0])

    expect(useJobSearchStore.getState().showPasteJd).toBe(false)
  })
})
