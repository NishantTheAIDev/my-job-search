import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadResume } from '../../api/resume'
import { useJobSearchStore } from '../../store/useJobSearchStore'

interface ResumeUploadProps {
  variant: 'card' | 'inline'
}

function CheckBadge() {
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white" aria-hidden="true">
      <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
      </svg>
    </span>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className ?? ''}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
    </svg>
  )
}

export function ResumeUpload({ variant }: ResumeUploadProps) {
  const resumeUploaded = useJobSearchStore((s) => s.resumeUploaded)
  const setResumeUploaded = useJobSearchStore((s) => s.setResumeUploaded)
  const queryClient = useQueryClient()

  const [uploadError, setUploadError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const uploadMutation = useMutation({
    mutationFn: uploadResume,
    onSuccess: () => {
      setResumeUploaded(true)
      setUploadError(null)
      setSelectedFile(null)
      queryClient.invalidateQueries({ queryKey: ['resume'] })
    },
    onError: () => setUploadError('Upload failed. Please check the file and try again.'),
  })
  const isUploading = uploadMutation.isPending

  function handleUpload(file: File | null) {
    if (!file) { setUploadError('Please select a file first.'); return }
    setUploadError(null)
    uploadMutation.mutate(file)
  }

  // ---- inline: compact status / replace control for the results top bar ----
  if (variant === 'inline') {
    if (resumeUploaded) {
      return (
        <span className="hidden items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[12px] font-semibold text-emerald-700 ring-1 ring-emerald-200 md:inline-flex">
          <CheckBadge />
          Resume ready
        </span>
      )
    }
    return (
      <label className="hidden cursor-pointer items-center gap-1.5 rounded-lg border border-dashed border-slate-300 px-2.5 py-1.5 text-[12px] font-medium text-slate-500 transition hover:border-indigo-300 hover:text-indigo-600 md:inline-flex">
        {isUploading ? <Spinner className="h-3.5 w-3.5" /> : (
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
          </svg>
        )}
        {isUploading ? 'Uploading…' : 'Upload resume'}
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(e) => handleUpload(e.target.files?.[0] ?? null)}
          disabled={isUploading}
          aria-label="Resume file input"
        />
      </label>
    )
  }

  // ---- card: full upload card for the landing hero ----
  if (resumeUploaded) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 ring-1 ring-emerald-200">
        <CheckBadge />
        <span className="text-[13px] font-semibold text-emerald-700">Resume uploaded — match scores are on</span>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-4 backdrop-blur">
      <div className="mb-3 text-center">
        <p className="text-[13px] font-semibold text-slate-700">Add your resume for AI match scores</p>
        <p className="text-[11px] text-slate-400">Optional · PDF, DOCX, or TXT · Max 5 MB</p>
      </div>

      <label
        className={`mb-3 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed p-4 transition ${
          selectedFile
            ? 'border-indigo-300 bg-indigo-50'
            : 'border-slate-200 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/50'
        }`}
        aria-label="Choose resume file"
      >
        <svg className={`h-6 w-6 ${selectedFile ? 'text-indigo-400' : 'text-slate-300'}`} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
        </svg>
        <span className={`text-[12px] font-medium ${selectedFile ? 'text-indigo-600' : 'text-slate-500'}`}>
          {selectedFile ? selectedFile.name : 'Click to choose file'}
        </span>
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(e) => { setSelectedFile(e.target.files?.[0] ?? null); setUploadError(null) }}
          disabled={isUploading}
          aria-label="Resume file input"
        />
      </label>

      <button
        onClick={() => handleUpload(selectedFile)}
        disabled={isUploading || !selectedFile}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2 text-[12px] font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isUploading ? (<><Spinner className="h-3.5 w-3.5" />Uploading…</>) : 'Upload Resume'}
      </button>
      {uploadError && <p role="alert" className="mt-2 text-center text-[11px] text-red-500">{uploadError}</p>}
    </div>
  )
}
