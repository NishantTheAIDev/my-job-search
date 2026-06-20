import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createSavedSearch } from '../../api/savedSearches'
import { useJobSearchStore } from '../../store/useJobSearchStore'

function BookmarkIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
    </svg>
  )
}

/**
 * Compact "Save this search" control. Collapsed it's a single button; expanded it
 * reveals an inline name input + Save. Persists the current store `criteria`.
 */
export function SaveSearchButton() {
  const criteria = useJobSearchStore((s) => s.criteria)
  const queryClient = useQueryClient()

  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')

  const mutation = useMutation({
    mutationFn: () => createSavedSearch(name.trim(), criteria),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedSearches'] })
      setOpen(false)
      setName('')
    },
  })

  if (!open) {
    return (
      <button
        onClick={() => {
          setName(criteria.query ?? '')
          setOpen(true)
        }}
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        aria-label="Save this search"
      >
        <BookmarkIcon />
        Save search
      </button>
    )
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (name.trim()) mutation.mutate()
      }}
      className="flex items-center gap-1.5"
      aria-label="Save this search"
    >
      <input
        type="text"
        value={name}
        autoFocus
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false)
            setName('')
          }
        }}
        placeholder="Name this search…"
        aria-label="Saved search name"
        maxLength={120}
        className="w-40 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-800 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
      />
      <button
        type="submit"
        disabled={!name.trim() || mutation.isPending}
        className="inline-flex items-center rounded-lg bg-indigo-600 px-2.5 py-1 text-[11px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {mutation.isPending ? 'Saving…' : 'Save'}
      </button>
      <button
        type="button"
        onClick={() => {
          setOpen(false)
          setName('')
        }}
        className="inline-flex items-center rounded-lg border border-slate-200 px-2 py-1 text-[11px] font-medium text-slate-500 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        aria-label="Cancel saving search"
      >
        Cancel
      </button>
      {mutation.isError && (
        <span role="alert" className="text-[11px] text-red-500">
          Failed
        </span>
      )}
    </form>
  )
}
