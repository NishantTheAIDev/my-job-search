import { render, screen, fireEvent } from '@testing-library/react'
import { useState } from 'react'
import { ErrorBoundary } from './ErrorBoundary'

function Boom({ explode }: { explode: boolean }): React.ReactElement {
  if (explode) throw new Error('kaboom')
  return <div>safe content</div>
}

describe('ErrorBoundary', () => {
  beforeEach(() => vi.spyOn(console, 'error').mockImplementation(() => {}))
  afterEach(() => vi.restoreAllMocks())

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>hello</div>
      </ErrorBoundary>,
    )
    expect(screen.getByText('hello')).toBeInTheDocument()
  })

  it('shows fallback instead of blanking when a child throws', () => {
    render(
      <ErrorBoundary>
        <Boom explode />
      </ErrorBoundary>,
    )
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  it('auto-resets when resetKeys change', () => {
    function Harness() {
      const [explode, setExplode] = useState(true)
      const [key, setKey] = useState(0)
      return (
        <>
          <button onClick={() => { setExplode(false); setKey((k) => k + 1) }}>fix</button>
          <ErrorBoundary resetKeys={[key]}>
            <Boom explode={explode} />
          </ErrorBoundary>
        </>
      )
    }
    render(<Harness />)
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    fireEvent.click(screen.getByText('fix'))
    expect(screen.getByText('safe content')).toBeInTheDocument()
  })
})
