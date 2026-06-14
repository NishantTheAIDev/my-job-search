import { render, screen } from '@testing-library/react'
import { HiringTrends } from './HiringTrends'
import type { TrendData } from '../../types'

const fullTrends: TrendData = {
  salary_history: [
    { period: '2024-01', value: 1100000 },
    { period: '2024-06', value: 1200000 },
  ],
  unemployment: [
    { year: 2021, value: 8.1 },
    { year: 2022, value: 5.4 },
    { year: 2023, value: 4.1 },
  ],
  employment: [
    { year: 2021, value: 42.0 },
    { year: 2022, value: 44.5 },
    { year: 2023, value: 45.2 },
  ],
}

const emptyTrends: TrendData = {
  salary_history: [],
  unemployment: [],
  employment: [],
}

describe('HiringTrends', () => {
  it('renders without crashing with full trend data', () => {
    render(<HiringTrends trends={fullTrends} region="in" />)

    // All three section headings should appear
    expect(screen.getByText(/average salary trend/i)).toBeInTheDocument()
    // Use exact heading text to avoid /employment rate/ matching "Unemployment Rate"
    expect(screen.getByRole('heading', { name: 'Unemployment Rate' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Employment Rate' })).toBeInTheDocument()
  })

  it('shows empty state when all arrays are empty', () => {
    render(<HiringTrends trends={emptyTrends} region="in" />)

    expect(screen.getByText(/no trend data/i)).toBeInTheDocument()
  })

  it('renders salary history chart when data is present', () => {
    render(<HiringTrends trends={fullTrends} region="in" />)

    const salaryChart = screen.getByRole('img', { name: /average salary over time/i })
    expect(salaryChart).toBeInTheDocument()
  })

  it('renders unemployment chart when data is present', () => {
    render(<HiringTrends trends={fullTrends} region="in" />)

    const charts = screen.getAllByRole('img')
    const unemployChart = charts.find((el) =>
      el.getAttribute('aria-label')?.match(/^Unemployment rate over years/i)
    )
    expect(unemployChart).toBeDefined()
  })

  it('renders employment chart when data is present', () => {
    render(<HiringTrends trends={fullTrends} region="in" />)

    // The SVG has role="img" and a specific aria-label (not matching unemployment)
    const charts = screen.getAllByRole('img')
    const employChart = charts.find((el) =>
      el.getAttribute('aria-label')?.match(/^Employment rate over years/i)
    )
    expect(employChart).toBeDefined()
  })

  it('renders only available sections — missing salary_history shows no salary chart', () => {
    const partial: TrendData = {
      salary_history: [],
      unemployment: fullTrends.unemployment,
      employment: fullTrends.employment,
    }
    render(<HiringTrends trends={partial} region="in" />)

    expect(screen.queryByText(/average salary trend/i)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Unemployment Rate' })).toBeInTheDocument()
  })

  it('renders with a single data point without crashing', () => {
    const singlePoint: TrendData = {
      salary_history: [{ period: '2024-01', value: 1000000 }],
      unemployment: [],
      employment: [],
    }
    render(<HiringTrends trends={singlePoint} region="in" />)

    expect(screen.getByText(/average salary trend/i)).toBeInTheDocument()
  })
})
