import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { useAuthStore } from '../../store/useAuthStore'

interface NavItem {
  label: string
  onSelect: () => void
  icon: React.ReactNode
}

/**
 * Secondary navigation collapsed into a single dropdown. Keeping the destinations
 * (Tailor from JD, Saved Searches, Saved Applications, Market Insights) behind one
 * control keeps the results top bar from overflowing on narrow viewports — the
 * search field stays the visual priority.
 */
export function NavMenu() {
  const setShowPasteJd = useJobSearchStore((s) => s.setShowPasteJd)
  const setShowSavedSearches = useJobSearchStore((s) => s.setShowSavedSearches)
  const setShowSavedApplications = useJobSearchStore((s) => s.setShowSavedApplications)
  const setShowInProgressApplications = useJobSearchStore((s) => s.setShowInProgressApplications)
  const setShowInsights = useJobSearchStore((s) => s.setShowInsights)
  const resetToLanding = useJobSearchStore((s) => s.resetToLanding)
  const clearToken = useAuthStore((s) => s.clearToken)
  const queryClient = useQueryClient()

  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  function handleLogout() {
    // Drop cached per-user server state so the next login starts clean.
    resetToLanding()
    queryClient.clear()
    clearToken()
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

  const items: NavItem[] = [
    {
      label: 'Tailor from JD',
      onSelect: () => setShowPasteJd(true),
      icon: (
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
      ),
    },
    {
      label: 'In Progress',
      onSelect: () => setShowInProgressApplications(true),
      icon: (
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      ),
    },
    {
      label: 'Saved Searches',
      onSelect: () => setShowSavedSearches(true),
      icon: (
        <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
      ),
    },
    {
      label: 'Saved Applications',
      onSelect: () => setShowSavedApplications(true),
      icon: (
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
      ),
    },
    {
      label: 'Market Insights',
      onSelect: () => setShowInsights(true),
      icon: (
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
      ),
    },
  ]

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Menu"
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[13px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5" />
        </svg>
        <span className="hidden sm:inline">Menu</span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Navigation"
          className="absolute right-0 z-50 mt-1.5 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white py-1.5 shadow-lg"
        >
          {items.map(({ label, onSelect, icon }) => (
            <button
              key={label}
              type="button"
              role="menuitem"
              onClick={() => { setOpen(false); onSelect() }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px] font-medium text-slate-700 transition hover:bg-indigo-50 hover:text-indigo-700 focus:bg-indigo-50 focus:outline-none"
            >
              <svg className="h-4 w-4 shrink-0 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
                {icon}
              </svg>
              {label}
            </button>
          ))}
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            role="menuitem"
            onClick={() => { setOpen(false); handleLogout() }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px] font-medium text-slate-700 transition hover:bg-red-50 hover:text-red-700 focus:bg-red-50 focus:outline-none"
          >
            <svg className="h-4 w-4 shrink-0 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
            </svg>
            Log out
          </button>
        </div>
      )}
    </div>
  )
}
