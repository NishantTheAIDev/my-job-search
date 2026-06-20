import { render, screen } from '@testing-library/react'
import { MarketNews } from './MarketNews'
import type { NewsItem } from '../../types'

const sampleNews: NewsItem[] = [
  {
    title: 'AI hiring surge in India',
    url: 'https://example.com/ai-hiring',
    domain: 'example.com',
    seendate: '20260614T100000Z',
  },
  {
    title: 'Tech layoffs hit record high',
    url: 'https://techcrunch.com/layoffs',
    domain: 'techcrunch.com',
    seendate: '20260113T090000Z',
  },
]

describe('MarketNews', () => {
  // ── Empty state ──────────────────────────────────────────────────────────────

  it('shows empty state when news array is empty', () => {
    render(<MarketNews news={[]} />)

    expect(screen.getByText(/no news available/i)).toBeInTheDocument()
  })

  // ── Article list ─────────────────────────────────────────────────────────────

  it('renders a list item for each news article', () => {
    render(<MarketNews news={sampleNews} />)

    expect(screen.getByText('AI hiring surge in India')).toBeInTheDocument()
    expect(screen.getByText('Tech layoffs hit record high')).toBeInTheDocument()
  })

  it('renders the article list with an accessible label', () => {
    render(<MarketNews news={sampleNews} />)

    expect(screen.getByRole('list', { name: /market news articles/i })).toBeInTheDocument()
  })

  // ── External link security ───────────────────────────────────────────────────

  it('every article link has rel="noopener noreferrer"', () => {
    render(<MarketNews news={sampleNews} />)

    const links = screen.getAllByRole('link')
    for (const link of links) {
      const rel = link.getAttribute('rel') ?? ''
      expect(rel).toContain('noopener')
      expect(rel).toContain('noreferrer')
    }
  })

  it('every article link opens in a new tab (target="_blank")', () => {
    render(<MarketNews news={sampleNews} />)

    const links = screen.getAllByRole('link')
    for (const link of links) {
      expect(link).toHaveAttribute('target', '_blank')
    }
  })

  it('every article link href points to the correct URL', () => {
    render(<MarketNews news={sampleNews} />)

    const link = screen.getByRole('link', { name: /ai hiring surge in india/i })
    expect(link).toHaveAttribute('href', 'https://example.com/ai-hiring')
  })

  it('link has an accessible aria-label mentioning "opens in new tab"', () => {
    render(<MarketNews news={[sampleNews[0]]} />)

    const link = screen.getByRole('link', { name: /opens in new tab/i })
    expect(link).toBeInTheDocument()
  })

  // ── Domain badge ─────────────────────────────────────────────────────────────

  it('renders the domain badge for each article', () => {
    render(<MarketNews news={sampleNews} />)

    expect(screen.getByText('example.com')).toBeInTheDocument()
    expect(screen.getByText('techcrunch.com')).toBeInTheDocument()
  })

  // ── GDELT seendate parsing ───────────────────────────────────────────────────

  it('parses and renders the GDELT seendate into a human-readable date', () => {
    render(<MarketNews news={[sampleNews[0]]} />)

    // "20260614T100000Z" → should render as "14 Jun 2026" in en-GB format
    // We just assert some date-like text is present; locale output varies
    const dateSpan = document.querySelector('[aria-label^="Published"]')
    expect(dateSpan).toBeInTheDocument()
    expect(dateSpan?.textContent).toMatch(/2026/)
  })

  it('renders an empty string seendate without crashing', () => {
    const noDate: NewsItem[] = [
      { title: 'No date article', url: 'https://x.com', domain: 'x.com', seendate: '' },
    ]
    render(<MarketNews news={noDate} />)

    expect(screen.getByText('No date article')).toBeInTheDocument()
  })
})
