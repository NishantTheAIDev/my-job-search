/**
 * Tests for the DownloadMenu, focused on the optional RenderCV theme selector.
 *
 * Verifies that:
 * 1. Without a `themes` prop, no theme selector renders (back-compat).
 * 2. With `themes`, a selector renders and the PDF link reflects the chosen theme.
 * 3. urlFor receives the selected theme so the export URL carries `?theme=`.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DownloadMenu } from './DownloadMenu'
import type { DownloadFormat } from '../../api/applications'

const THEMES = [
  { value: 'engineeringresumes', label: 'Engineering Resumes' },
  { value: 'moderncv', label: 'ModernCV' },
]

function urlFor(format: DownloadFormat, theme?: string): string {
  const url = `/api/applications/1/resume.${format}`
  return format === 'pdf' && theme ? `${url}?theme=${theme}` : url
}

it('renders no theme selector when themes prop is absent', async () => {
  render(<DownloadMenu label="Resume" urlFor={urlFor} />)
  await userEvent.click(screen.getByRole('button', { name: /resume/i }))
  expect(screen.queryByLabelText('PDF theme')).toBeNull()
})

it('renders a theme selector and applies the default theme to the PDF link', async () => {
  render(
    <DownloadMenu
      label="Resume"
      urlFor={urlFor}
      themes={THEMES}
      defaultTheme="engineeringresumes"
    />
  )
  await userEvent.click(screen.getByRole('button', { name: /resume/i }))
  expect(screen.getByLabelText('PDF theme')).toBeInTheDocument()
  const pdfLink = screen.getByRole('menuitem', { name: /pdf/i })
  expect(pdfLink).toHaveAttribute('href', '/api/applications/1/resume.pdf?theme=engineeringresumes')
})

it('updates the PDF link when a different theme is selected', async () => {
  render(<DownloadMenu label="Resume" urlFor={urlFor} themes={THEMES} />)
  await userEvent.click(screen.getByRole('button', { name: /resume/i }))
  await userEvent.selectOptions(screen.getByLabelText('PDF theme'), 'moderncv')
  const pdfLink = screen.getByRole('menuitem', { name: /pdf/i })
  expect(pdfLink).toHaveAttribute('href', '/api/applications/1/resume.pdf?theme=moderncv')
})

it('leaves the docx link untouched by the theme', async () => {
  render(<DownloadMenu label="Resume" urlFor={urlFor} themes={THEMES} />)
  await userEvent.click(screen.getByRole('button', { name: /resume/i }))
  const docxLink = screen.getByRole('menuitem', { name: /word/i })
  expect(docxLink).toHaveAttribute('href', '/api/applications/1/resume.docx')
})
