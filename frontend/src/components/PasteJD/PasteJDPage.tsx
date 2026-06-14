import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useJobSearchStore } from '../../store/useJobSearchStore'
import { createManualApplication } from '../../api/jobs'
import { Logo } from '../shared/Logo'
import { ResumeUpload } from '../shared/ResumeUpload'
import { ErrorBanner } from '../shared/ErrorBanner'

export function PasteJDPage() {
  const setShowPasteJd = useJobSearchStore((s) => s.setShowPasteJd)
  const setShowApproval = useJobSearchStore((s) => s.setShowApproval)
  const setActiveApplication = useJobSearchStore((s) => s.setActiveApplication)
  const resumeUploaded = useJobSearchStore((s) => s.resumeUploaded)
  const activeSearchJobId = useJobSearchStore((s) => s.activeSearchJobId)

  const [jdText, setJdText] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [company, setCompany] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      createManualApplication({
        jd_text: jdText.trim(),
        title: jobTitle.trim() || undefined,
        company: company.trim() || undefined,
      }),
    onSuccess: (data) => {
      setActiveApplication(data.job_id)
      setShowPasteJd(false)
      setShowApproval(true)
    },
  })

  function handleBack() {
    setShowPasteJd(false)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!jdText.trim() || mutation.isPending) return
    mutation.mutate()
  }

  const isDisabled = !jdText.trim() || mutation.isPending

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Top nav — mirrors InsightsPage header */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.06)] sm:px-5">
        <div className="hidden shrink-0 md:block">
          <Logo />
        </div>

        <div className="flex min-w-0 flex-1 items-center">
          <span className="text-[15px] font-semibold leading-tight text-slate-900">Tailor from JD</span>
        </div>

        {/* Back button — desktop */}
        <button
          onClick={handleBack}
          aria-label={activeSearchJobId ? 'Back to results' : 'Back to home'}
          className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[12px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:inline-flex"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {activeSearchJobId ? 'Back to results' : 'Back to home'}
        </button>

        {/* Back button — mobile icon only */}
        <button
          onClick={handleBack}
          aria-label={activeSearchJobId ? 'Back to results' : 'Back to home'}
          className="flex shrink-0 items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:hidden"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
        </button>
      </header>

      {/* Page body */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">

          {!resumeUploaded ? (
            /* Resume gate — mirrors how SearchForm handles it */
            <div className="flex flex-col items-center gap-6 py-10">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-500">
                <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                </svg>
              </div>
              <div className="text-center">
                <h2 className="text-[16px] font-semibold text-slate-900">Upload your resume first</h2>
                <p className="mt-1.5 max-w-xs text-[13px] leading-relaxed text-slate-500">
                  A resume is required to tailor your application. Upload a PDF, DOCX, or TXT file below.
                </p>
              </div>
              <div className="w-full max-w-md">
                <ResumeUpload variant="card" />
              </div>
            </div>
          ) : (
            /* JD form */
            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
              <div>
                <h2 className="text-[18px] font-bold text-slate-900">Paste a job description</h2>
                <p className="mt-1 text-[13px] text-slate-500">
                  Claude will score, tailor your resume, and draft a cover letter. You review before anything is saved.
                </p>
              </div>

              {mutation.isError && (
                <ErrorBanner
                  message="Failed to start tailoring. Please check your connection and try again."
                  onRetry={() => mutation.reset()}
                />
              )}

              {/* JD textarea */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="jd-textarea"
                  className="text-[13px] font-semibold text-slate-700"
                >
                  Job description <span className="text-red-500" aria-hidden="true">*</span>
                </label>
                <textarea
                  id="jd-textarea"
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  required
                  rows={14}
                  placeholder="Paste the full job description here…"
                  aria-required="true"
                  aria-describedby="jd-hint"
                  className="w-full resize-y rounded-xl border border-slate-200 bg-white px-4 py-3 font-mono text-[13px] leading-relaxed text-slate-800 placeholder-slate-300 shadow-sm transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30"
                />
                <p id="jd-hint" className="text-[11px] text-slate-400">
                  The full JD gives the best match scores and tailoring quality.
                </p>
              </div>

              {/* Optional metadata row */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="jd-title" className="text-[13px] font-semibold text-slate-700">
                    Job title <span className="text-[11px] font-normal text-slate-400">(optional)</span>
                  </label>
                  <input
                    id="jd-title"
                    type="text"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    placeholder="e.g. Senior Software Engineer"
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-[13px] text-slate-800 placeholder-slate-300 shadow-sm transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="jd-company" className="text-[13px] font-semibold text-slate-700">
                    Company <span className="text-[11px] font-normal text-slate-400">(optional)</span>
                  </label>
                  <input
                    id="jd-company"
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="e.g. Acme Corp"
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-[13px] text-slate-800 placeholder-slate-300 shadow-sm transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 pt-1">
                <button
                  type="submit"
                  disabled={isDisabled}
                  aria-busy={mutation.isPending}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-[14px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {mutation.isPending ? (
                    <>
                      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                      </svg>
                      Starting…
                    </>
                  ) : (
                    <>
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
                      </svg>
                      Tailor &amp; Review
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={handleBack}
                  className="rounded-xl border border-slate-200 px-6 py-3 text-[14px] font-medium text-slate-600 transition hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </main>
    </div>
  )
}
