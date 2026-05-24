import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SearchForm } from './SearchForm'

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('SearchForm', () => {
  it('renders query input', () => {
    render(<SearchForm />, { wrapper })
    expect(screen.getByRole('textbox', { name: /job title, role, or keywords/i })).toBeInTheDocument()
  })

  it('renders remote-only checkbox', () => {
    render(<SearchForm />, { wrapper })
    expect(screen.getByRole('checkbox', { name: /remote only/i })).toBeInTheDocument()
  })

  it('remote-only checkbox has an accessible label', () => {
    render(<SearchForm />, { wrapper })
    const checkbox = screen.getByRole('checkbox', { name: /remote only/i })
    expect(checkbox).toHaveAccessibleName()
  })

  it('renders a submit button', () => {
    render(<SearchForm />, { wrapper })
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
  })

  it('submit button is disabled when query is empty', () => {
    render(<SearchForm />, { wrapper })
    const button = screen.getByRole('button', { name: /search/i })
    expect(button).toBeDisabled()
  })

  it('submit button is enabled when query has text', async () => {
    const user = userEvent.setup()
    render(<SearchForm />, { wrapper })
    const input = screen.getByRole('textbox', { name: /job title, role, or keywords/i })
    await user.type(input, 'software engineer')
    // Wait for debounce
    await new Promise((r) => setTimeout(r, 350))
    const button = screen.getByRole('button', { name: /search/i })
    expect(button).not.toBeDisabled()
  })

  it('shows/hides filter panel on toggle', async () => {
    const user = userEvent.setup()
    render(<SearchForm />, { wrapper })
    expect(screen.queryByRole('group', { hidden: true })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /show filters/i }))
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /hide filters/i }))
    expect(screen.queryByLabelText(/location/i)).not.toBeInTheDocument()
  })
})
