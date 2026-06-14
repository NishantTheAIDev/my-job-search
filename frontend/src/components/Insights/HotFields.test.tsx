import { render, screen } from '@testing-library/react'
import { HotFields } from './HotFields'
import type { HotField } from '../../types'

const sampleFields: HotField[] = [
  { label: 'IT Jobs', tag: 'it-jobs', openings: 12500, mean_salary: 900000, currency: 'INR' },
  { label: 'Engineering Jobs', tag: 'engineering-jobs', openings: 8000, mean_salary: 800000, currency: 'INR' },
  { label: 'Finance Jobs', tag: 'finance-jobs', openings: 3000, mean_salary: 700000, currency: 'INR' },
]

describe('HotFields', () => {
  it('renders without crashing with populated data', () => {
    render(<HotFields fields={sampleFields} region="in" />)

    expect(screen.getByText('IT Jobs')).toBeInTheDocument()
  })

  it('renders a ranked list with correct accessible label', () => {
    render(<HotFields fields={sampleFields} region="in" />)

    const list = screen.getByRole('list', { name: /hottest job fields ranked by openings/i })
    expect(list).toBeInTheDocument()
  })

  it('renders a list item for each field', () => {
    render(<HotFields fields={sampleFields} region="in" />)

    const items = screen.getAllByRole('listitem')
    expect(items.length).toBe(3)
  })

  it('shows field label for every entry', () => {
    render(<HotFields fields={sampleFields} region="in" />)

    expect(screen.getByText('IT Jobs')).toBeInTheDocument()
    expect(screen.getByText('Engineering Jobs')).toBeInTheDocument()
    expect(screen.getByText('Finance Jobs')).toBeInTheDocument()
  })

  it('shows openings count for each field', () => {
    render(<HotFields fields={sampleFields} region="in" />)

    expect(screen.getByText(/12,500 openings/i)).toBeInTheDocument()
  })

  it('renders a progress bar with an accessible aria-label', () => {
    render(<HotFields fields={sampleFields} region="in" />)

    const bars = screen.getAllByRole('img')
    expect(bars.length).toBeGreaterThanOrEqual(sampleFields.length)
  })

  // ── Empty state ──────────────────────────────────────────────────────────────

  it('shows empty state when fields array is empty', () => {
    render(<HotFields fields={[]} region="in" />)

    expect(screen.getByText(/no field data/i)).toBeInTheDocument()
  })
})
