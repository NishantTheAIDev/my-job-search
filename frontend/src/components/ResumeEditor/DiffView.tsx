import { useState } from 'react'
import type { DiffHunk } from '../../types'

interface DiffViewProps {
  hunks: DiffHunk[]
}

const CONTEXT_LINES = 3

function groupHunksWithContext(hunks: DiffHunk[]): Array<{ hunk: DiffHunk; showByDefault: boolean }> {
  // Find indices of changed hunks
  const changedIndices = new Set<number>()
  hunks.forEach((h, i) => {
    if (h.type !== 'unchanged') changedIndices.add(i)
  })

  // Expand context around changed lines
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

  const bgClass = isAdded
    ? 'bg-green-50'
    : isRemoved
      ? 'bg-red-50'
      : 'bg-white'

  const textClass = isAdded
    ? 'text-green-900 underline'
    : isRemoved
      ? 'text-red-900 line-through'
      : 'text-gray-800'

  const glyph = isAdded ? '+' : isRemoved ? '-' : ' '
  const glyphColor = isAdded
    ? 'text-green-600 font-bold'
    : isRemoved
      ? 'text-red-600 font-bold'
      : 'text-gray-300'

  return (
    <div
      className={`flex font-mono text-sm leading-relaxed ${bgClass}`}
      role="row"
      aria-label={`${hunk.type} line ${hunk.line}`}
    >
      {/* Line number */}
      <span
        className="w-10 shrink-0 select-none border-r border-gray-200 pr-2 text-right text-xs text-gray-400"
        aria-hidden="true"
      >
        {hunk.line}
      </span>
      {/* Glyph */}
      <span
        className={`w-6 shrink-0 select-none text-center ${glyphColor}`}
        aria-hidden="true"
      >
        {glyph}
      </span>
      {/* Text */}
      <span className={`flex-1 whitespace-pre-wrap break-all px-2 ${textClass}`}>
        {hunk.text || ' '}
      </span>
    </div>
  )
}

export function DiffView({ hunks }: DiffViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set())

  if (hunks.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-gray-500">No changes detected in this resume.</p>
    )
  }

  const annotated = groupHunksWithContext(hunks)

  // Build render groups: consecutive hidden unchanged lines become a collapsible block
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
      // Start of a hidden block — gather consecutive hidden items
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
      className="overflow-hidden rounded-lg border border-gray-200 bg-white"
      role="table"
      aria-label="Resume diff"
    >
      {/* Legend */}
      {hasChanges && (
        <div className="flex gap-4 border-b border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-600">
          <span className="flex items-center gap-1">
            <span className="font-bold text-green-600">+</span>
            <span className="underline">Added</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="font-bold text-red-600">-</span>
            <span className="line-through">Removed</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="text-gray-300">&nbsp;</span>
            Unchanged
          </span>
        </div>
      )}

      <div className="divide-y divide-gray-100" role="rowgroup">
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
              className="flex w-full items-center gap-2 bg-gray-50 px-4 py-1.5 text-left text-xs text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
              aria-label={`Expand ${count} hidden unchanged lines`}
            >
              <span aria-hidden="true">&#x2026;</span>
              {count} unchanged {count === 1 ? 'line' : 'lines'} hidden — click to expand
            </button>
          )
        })}
      </div>
    </div>
  )
}
