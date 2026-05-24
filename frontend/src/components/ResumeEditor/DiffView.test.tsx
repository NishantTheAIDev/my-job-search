import { render, screen } from '@testing-library/react'
import { DiffView } from './DiffView'
import type { DiffHunk } from '../../types'

describe('DiffView', () => {
  it('renders empty message when no hunks', () => {
    render(<DiffView hunks={[]} />)
    expect(screen.getByText(/no changes detected/i)).toBeInTheDocument()
  })

  it('renders "added" hunks with green background class', () => {
    const hunks: DiffHunk[] = [
      { type: 'added', text: 'New line of content', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    const addedRow = container.querySelector('.bg-green-50')
    expect(addedRow).toBeInTheDocument()
  })

  it('renders "added" hunks with "+" marker', () => {
    const hunks: DiffHunk[] = [
      { type: 'added', text: 'New line', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    // The glyph span with "+" should exist
    const glyphs = container.querySelectorAll('[aria-hidden="true"]')
    const plusGlyph = Array.from(glyphs).find((el) => el.textContent === '+')
    expect(plusGlyph).toBeTruthy()
  })

  it('renders "removed" hunks with red background class', () => {
    const hunks: DiffHunk[] = [
      { type: 'removed', text: 'Old line content', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    const removedRow = container.querySelector('.bg-red-50')
    expect(removedRow).toBeInTheDocument()
  })

  it('renders "removed" hunks with "-" marker', () => {
    const hunks: DiffHunk[] = [
      { type: 'removed', text: 'Old line', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    const glyphs = container.querySelectorAll('[aria-hidden="true"]')
    const minusGlyph = Array.from(glyphs).find((el) => el.textContent === '-')
    expect(minusGlyph).toBeTruthy()
  })

  it('applies line-through to removed text', () => {
    const hunks: DiffHunk[] = [
      { type: 'removed', text: 'Removed text', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    // Select all elements with line-through; the one inside the diff row contains the actual text
    const strikethroughEls = container.querySelectorAll('.line-through')
    const textEl = Array.from(strikethroughEls).find((el) =>
      el.textContent?.includes('Removed text')
    )
    expect(textEl).toBeTruthy()
  })

  it('applies underline to added text', () => {
    const hunks: DiffHunk[] = [
      { type: 'added', text: 'Added text', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    // Select all underlined elements; the one inside the diff row contains the actual text
    const underlinedEls = container.querySelectorAll('.underline')
    const textEl = Array.from(underlinedEls).find((el) =>
      el.textContent?.includes('Added text')
    )
    expect(textEl).toBeTruthy()
  })

  it('renders unchanged hunks without special styling', () => {
    const hunks: DiffHunk[] = [
      { type: 'unchanged', text: 'Normal text', line: 1 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    expect(container.querySelector('.bg-green-50')).not.toBeInTheDocument()
    expect(container.querySelector('.bg-red-50')).not.toBeInTheDocument()
  })

  it('shows legend when there are changes', () => {
    const hunks: DiffHunk[] = [
      { type: 'added', text: 'New', line: 1 },
      { type: 'removed', text: 'Old', line: 2 },
    ]
    render(<DiffView hunks={hunks} />)
    expect(screen.getByText('Added')).toBeInTheDocument()
    expect(screen.getByText('Removed')).toBeInTheDocument()
  })

  it('renders multiple hunk types correctly', () => {
    const hunks: DiffHunk[] = [
      { type: 'unchanged', text: 'Line 1', line: 1 },
      { type: 'removed', text: 'Removed', line: 2 },
      { type: 'added', text: 'Added', line: 3 },
    ]
    const { container } = render(<DiffView hunks={hunks} />)
    expect(container.querySelector('.bg-red-50')).toBeInTheDocument()
    expect(container.querySelector('.bg-green-50')).toBeInTheDocument()
  })
})
