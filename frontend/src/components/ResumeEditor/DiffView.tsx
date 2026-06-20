import { useState } from 'react'
import type { DiffHunk } from '../../types'

interface DiffViewProps {
  hunks: DiffHunk[]
}

const CONTEXT_LINES = 3

function groupHunksWithContext(hunks: DiffHunk[]): Array<{ hunk: DiffHunk; showByDefault: boolean }> {
  const changedIndices = new Set<number>()
  hunks.forEach((h, i) => {
    if (h.type !== 'unchanged') changedIndices.add(i)
  })

  const visibleIndices = new Set<number>()
  changedIndices.forEach((idx) => {
    for (let i = Math.max(0, idx - CONTEXT_LINES); i <= Math.min(hunks.length - 1, idx + CONTEXT_LINES); i++) {
      visibleIndices.add(i)
    }
  })

  return hunks.map((hunk, i) => ({
    hunk,
    showByDefault: hunk.type !== 'unchanged' || visibleIndices.has(i),
  }))
}

function DiffLine({ hunk }: { hunk: DiffHunk }) {
  const isAdded = hunk.type === 'added'
  const isRemoved = hunk.type === 'removed'

  // Background tints — color cue #1 (also used by tests to identify line types)
  const bgClass = isAdded
    ? 'bg-green-50'
    : isRemoved
      ? 'bg-red-50'
      : 'bg-white'

  // Text decoration — secondary cue for color-blind users (#2)
  const textDecoration = isAdded
    ? 'underline decoration-green-500 decoration-1 underline-offset-2'
    : isRemoved
      ? 'line-through decoration-red-400'
      : ''

  const textColor = isAdded
    ? 'text-green-900'
    : isRemoved
      ? 'text-red-900'
      : 'text-slate-700'

  const glyph = isAdded ? '+' : isRemoved ? '-' : ' '

  const glyphStyle = isAdded
    ? 'text-green-700 font-bold'
    : isRemoved
      ? 'text-red-600 font-bold'
      : 'text-slate-300'

  const borderLeft = isAdded
    ? 'border-l-2 border-green-400'
    : isRemoved
      ? 'border-l-2 border-red-400'
      : 'border-l-2 border-transparent'

  return (
    <div
      className={`flex font-mono text-[12px] leading-6 ${bgClass} ${borderLeft}`}
      role="row"
      aria-label={`${hunk.type} line ${hunk.line}`}
    >
      {/* Line number */}
      <span
        className="w-10 shrink-0 select-none border-r border-slate-100 pr-2 text-right text-[11px] text-slate-300"
        aria-hidden="true"
      >
        {hunk.line}
      </span>
      {/* Glyph */}
      <span
        className={`w-5 shrink-0 select-none text-center text-[12px] ${glyphStyle}`}
        aria-hidden="true"
      >
        {glyph}
      </span>
      {/* Text with dual cues */}
      <span className={`flex-1 whitespace-pre-wrap break-all px-2 ${textColor} ${textDecoration}`}>
        {hunk.text || ' '}
      </span>
    </div>
  )
}

export function DiffView({ hunks }: DiffViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set())

  if (hunks.length === 0) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-slate-200 bg-slate-50 py-8 text-center">
        <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        <p className="text-[13px] text-slate-500">No changes detected in this resume.</p>
      </div>
    )
  }

  const annotated = groupHunksWithContext(hunks)

  type VisibleItem = { type: 'line'; index: number; hunk: DiffHunk }
  type CollapsedItem = { type: 'collapsed'; startIndex: number; endIndex: number; groupId: number }
  type RenderItem = VisibleItem | CollapsedItem

  const renderItems: RenderItem[] = []
  let groupId = 0
  let i = 0

  while (i < annotated.length) {
    const item = annotated[i]
    if (item.showByDefault || expandedSections.has(groupId)) {
      renderItems.push({ type: 'line', index: i, hunk: item.hunk })
      i++
    } else {
      const start = i
      while (i < annotated.length && !annotated[i].showByDefault) {
        i++
      }
      const end = i - 1
      const thisGroupId = groupId++
      if (expandedSections.has(thisGroupId)) {
        for (let j = start; j <= end; j++) {
          renderItems.push({ type: 'line', index: j, hunk: annotated[j].hunk })
        }
      } else {
        renderItems.push({ type: 'collapsed', startIndex: start, endIndex: end, groupId: thisGroupId })
      }
    }
  }

  function expandGroup(gid: number) {
    setExpandedSections((prev) => new Set([...prev, gid]))
  }

  const hasChanges = hunks.some((h) => h.type !== 'unchanged')

  return (
    <div
      className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
      role="table"
      aria-label="Resume diff"
    >
      {/* Legend */}
      {hasChanges && (
        <div className="flex gap-5 border-b border-slate-100 bg-slate-50 px-4 py-2.5 text-[11px]">
          <span className="flex items-center gap-1.5 text-slate-500">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-green-400" aria-hidden="true" />
            <span className="font-bold text-green-700">+</span>
            <span className="underline decoration-green-500 underline-offset-2">Added</span>
          </span>
          <span className="flex items-center gap-1.5 text-slate-500">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-400" aria-hidden="true" />
            <span className="font-bold text-red-600">-</span>
            <span className="line-through decoration-red-400">Removed</span>
          </span>
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="text-slate-300">&nbsp;&nbsp;</span>
            Unchanged
          </span>
        </div>
      )}

      <div className="divide-y divide-slate-50" role="rowgroup">
        {renderItems.map((item, idx) => {
          if (item.type === 'line') {
            return <DiffLine key={`line-${item.index}`} hunk={item.hunk} />
          }
          const count = item.endIndex - item.startIndex + 1
          return (
            <button
              key={`collapsed-${idx}`}
              type="button"
              onClick={() => expandGroup(item.groupId)}
              className="flex w-full items-center gap-1.5 bg-slate-50 px-4 py-1.5 text-left text-[11px] font-medium text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
              aria-label={`Expand ${count} hidden unchanged lines`}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9h16.5m-16.5 6.75h16.5" />
              </svg>
              {count} unchanged {count === 1 ? 'line' : 'lines'} — click to expand
            </button>
          )
        })}
      </div>
    </div>
  )
}
