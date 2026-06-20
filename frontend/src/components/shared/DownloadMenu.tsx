import { useEffect, useId, useRef, useState } from 'react'
import type { DownloadFormat } from '../../api/applications'
import { downloadFile } from '../../api/client'

const FORMATS: { format: DownloadFormat; label: string }[] = [
  { format: 'pdf', label: 'PDF (.pdf)' },
  { format: 'docx', label: 'Word (.docx)' },
]

interface DownloadMenuProps {
  /** Button text, e.g. "Download resume". */
  label: string
  /** Returns the download URL for a given file format and (optional) theme. */
  urlFor: (format: DownloadFormat, theme?: string) => string
  /**
   * Optional RenderCV themes. When provided, a theme selector is shown and the
   * chosen value is passed to `urlFor`. The theme only affects the PDF export;
   * the .docx is plain text and ignores it.
   */
  themes?: { value: string; label: string }[]
  /** Initially selected theme value (defaults to the first theme). */
  defaultTheme?: string
}

/**
 * Single download control with a PDF / Word format menu. Each item is a plain
 * download link to an export endpoint, which streams the file with a
 * Content-Disposition attachment header.
 */
export function DownloadMenu({ label, urlFor, themes, defaultTheme }: DownloadMenuProps) {
  const [open, setOpen] = useState(false)
  const [theme, setTheme] = useState(defaultTheme ?? themes?.[0]?.value)
  const [downloadError, setDownloadError] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const themeSelectId = useId()

  async function handleDownload(format: DownloadFormat) {
    setDownloadError(false)
    try {
      // Authenticated download: fetch as a blob (bearer token attached) rather
      // than a plain link, which can't send the Authorization header.
      await downloadFile(urlFor(format, theme))
      setOpen(false)
    } catch {
      setDownloadError(true)
    }
  }

  useEffect(() => {
    if (!open) return
    function handlePointer(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[13px] font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
      >
        <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path d="M8 1a.75.75 0 0 1 .75.75v6.69l1.72-1.72a.75.75 0 1 1 1.06 1.06l-3 3a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 0 1 1.06-1.06l1.72 1.72V1.75A.75.75 0 0 1 8 1Z" />
          <path d="M2.75 11a.75.75 0 0 1 .75.75v1.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 12.25 15h-8.5A1.75 1.75 0 0 1 2 13.25v-1.5a.75.75 0 0 1 .75-.75Z" />
        </svg>
        {label}
        <svg className="h-3.5 w-3.5 text-slate-400" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          aria-label={`${label} — choose format`}
          className="absolute right-0 z-50 mt-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {themes && themes.length > 0 && (
            <div className="border-b border-slate-100 px-3 py-2">
              <label
                htmlFor={themeSelectId}
                className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400"
              >
                PDF theme
              </label>
              <select
                id={themeSelectId}
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[13px] text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {themes.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          {FORMATS.map(({ format, label: formatLabel }) => (
            <button
              key={format}
              type="button"
              role="menuitem"
              onClick={() => handleDownload(format)}
              className="block w-full px-3 py-2 text-left text-[13px] text-slate-700 transition hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
            >
              {formatLabel}
            </button>
          ))}
          {downloadError && (
            <p role="alert" className="px-3 py-2 text-[12px] text-red-600">
              Download failed. Please try again.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
