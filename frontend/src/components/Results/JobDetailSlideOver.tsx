import { useEffect, useState } from 'react'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { JobDetailPanel } from '../ResultsList/JobDetailPanel'

/**
 * Right-anchored slide-over hosting the job detail. Driven by `selectedJob` in the
 * store. Renders the backdrop + panel only while a job is selected; uses a brief
 * mount delay so the slide-in transition runs, and closes on Escape or backdrop click.
 */
export function JobDetailSlideOver() {
  const selectedJob = useJobSearchStore((s) => s.selectedJob)
  const setSelectedJob = useJobSearchStore((s) => s.setSelectedJob)
  const [entered, setEntered] = useState(false)

  useEffect(() => {
    if (!selectedJob) return
    const id = requestAnimationFrame(() => setEntered(true))
    return () => {
      cancelAnimationFrame(id)
      setEntered(false)
    }
  }, [selectedJob])

  useEffect(() => {
    if (!selectedJob) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setSelectedJob(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedJob, setSelectedJob])

  if (!selectedJob) return null

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Job detail">
      {/* Backdrop */}
      <div
        onClick={() => setSelectedJob(null)}
        className={`absolute inset-0 bg-slate-900/30 backdrop-blur-[1px] transition-opacity duration-200 ${entered ? 'opacity-100' : 'opacity-0'}`}
        aria-hidden="true"
      />
      {/* Panel */}
      <div
        className={`absolute right-0 top-0 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-slate-50 shadow-2xl transition-transform duration-300 ease-out ${entered ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <JobDetailPanel job={selectedJob} onClose={() => setSelectedJob(null)} />
      </div>
    </div>
  )
}
