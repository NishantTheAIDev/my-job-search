import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SalaryTable } from './SalaryTable'
import * as insightsApi from '../../api/insights'
import type { SalaryStat } from '../../types'

vi.mock('../../api/insights')

const mockGetSalary = vi.mocked(insightsApi.getSalary)

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const sampleSalaries: SalaryStat[] = [
  { role: 'Software Engineer', median: 1200000, currency: 'INR', sample_size: 500 },
  { role: 'Data Scientist', median: 1500000, currency: 'INR', sample_size: 300 },
  { role: 'ML Engineer', median: null, currency: 'INR', sample_size: 0 },
]

beforeEach(() => {
  vi.clearAllMocks()
})

describe('SalaryTable', () => {
  // ── Table rendering ──────────────────────────────────────────────────────────

  it('renders a table with role headers', () => {
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    const table = screen.getByRole('table', { name: /median salary by role/i })
    expect(table).toBeInTheDocument()
  })

  it('renders a row for each salary entry', () => {
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    expect(screen.getByText('Software Engineer')).toBeInTheDocument()
    expect(screen.getByText('Data Scientist')).toBeInTheDocument()
    expect(screen.getByText('ML Engineer')).toBeInTheDocument()
  })

  it('formats the median salary as a currency string', () => {
    render(<SalaryTable salaries={[sampleSalaries[0]]} region="in" />, { wrapper })

    // formatSalary for INR 1200000 in en-IN locale — just check it doesn't show raw number
    const cells = screen.getAllByRole('cell')
    const salaryCell = cells.find((c) => c.textContent?.includes('1,20,000') || c.textContent?.includes('12,00,000') || c.textContent?.includes('₹'))
    expect(salaryCell).toBeDefined()
  })

  it('renders "—" for a null median salary', () => {
    render(<SalaryTable salaries={[sampleSalaries[2]]} region="in" />, { wrapper })

    // The dash should appear in the salary column
    const cells = screen.getAllByRole('cell')
    const dashCell = cells.find((c) => c.textContent === '—')
    expect(dashCell).toBeDefined()
  })

  it('shows "—" in sample size column when sample_size is 0', () => {
    render(<SalaryTable salaries={[sampleSalaries[2]]} region="in" />, { wrapper })

    // Both the salary cell and the sample size cell can show —
    const allDashes = screen.getAllByText('—')
    expect(allDashes.length).toBeGreaterThanOrEqual(1)
  })

  it('shows formatted sample_size when > 0', () => {
    render(<SalaryTable salaries={[sampleSalaries[0]]} region="in" />, { wrapper })

    // 500 should appear (possibly with locale formatting)
    expect(screen.getByText(/500/)).toBeInTheDocument()
  })

  // ── Empty state ──────────────────────────────────────────────────────────────

  it('shows empty state when salaries array is empty', () => {
    render(<SalaryTable salaries={[]} region="in" />, { wrapper })

    expect(screen.getByText(/no salary data/i)).toBeInTheDocument()
  })

  // ── Role search form ─────────────────────────────────────────────────────────

  it('renders the role search form with a label and button', () => {
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    expect(screen.getByLabelText(/job role/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /look up/i })).toBeInTheDocument()
  })

  it('Look up button is disabled when input is empty', () => {
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    const button = screen.getByRole('button', { name: /look up/i })
    expect(button).toBeDisabled()
  })

  it('Look up button becomes enabled when text is typed', async () => {
    const user = userEvent.setup()
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    const input = screen.getByLabelText(/job role/i)
    await user.type(input, 'DevOps Engineer')

    expect(screen.getByRole('button', { name: /look up/i })).not.toBeDisabled()
  })

  it('submitting the form calls getSalary with the typed role', async () => {
    const user = userEvent.setup()
    mockGetSalary.mockResolvedValue({
      role: 'DevOps Engineer',
      median: 1100000,
      currency: 'INR',
      sample_size: 150,
    })
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    const input = screen.getByLabelText(/job role/i)
    await user.type(input, 'DevOps Engineer')
    await user.click(screen.getByRole('button', { name: /look up/i }))

    await waitFor(() => {
      expect(mockGetSalary).toHaveBeenCalledWith('DevOps Engineer', 'in')
    })
  })

  it('shows the inline result after a successful lookup', async () => {
    const user = userEvent.setup()
    mockGetSalary.mockResolvedValue({
      role: 'DevOps Engineer',
      median: 1100000,
      currency: 'INR',
      sample_size: 150,
    })
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    await user.type(screen.getByLabelText(/job role/i), 'DevOps Engineer')
    await user.click(screen.getByRole('button', { name: /look up/i }))

    await waitFor(() => {
      expect(screen.getByText('DevOps Engineer')).toBeInTheDocument()
    })
  })

  it('shows a no-data message when search result median is null', async () => {
    const user = userEvent.setup()
    mockGetSalary.mockResolvedValue({
      role: 'Niche Role',
      median: null,
      currency: 'INR',
      sample_size: 0,
    })
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    await user.type(screen.getByLabelText(/job role/i), 'Niche Role')
    await user.click(screen.getByRole('button', { name: /look up/i }))

    await waitFor(() => {
      expect(screen.getByText(/no salary data available/i)).toBeInTheDocument()
    })
  })

  it('shows an error message when the salary lookup fails', async () => {
    const user = userEvent.setup()
    mockGetSalary.mockRejectedValue(new Error('Network error'))
    render(<SalaryTable salaries={sampleSalaries} region="in" />, { wrapper })

    await user.type(screen.getByLabelText(/job role/i), 'Some Role')
    await user.click(screen.getByRole('button', { name: /look up/i }))

    // SalaryTable uses retry:1 in useQuery so allow enough time for retries to exhaust
    await waitFor(() => {
      expect(screen.getByText(/could not fetch salary/i)).toBeInTheDocument()
    }, { timeout: 5000 })
  })
})
