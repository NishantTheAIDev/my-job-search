import { useRef, useState } from 'react'
import { uploadResume } from '../../api/resume'
import { useJobSearchStore } from '../../store/useJobSearchStore'

export function ResumeUploadBanner() {
  const resumeUploaded = useJobSearchStore((s) => s.resumeUploaded)
  const setResumeUploaded = useJobSearchStore((s) => s.setResumeUploaded)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  if (resumeUploaded) return null

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    setSelectedFile(file)
    setError(null)
  }

  async function handleUpload() {
    if (!selectedFile) {
      setError('Please select a file first.')
      return
    }
    setIsUploading(true)
    setError(null)
    try {
      await uploadResume(selectedFile)
      setResumeUploaded(true)
    } catch {
      setError('Upload failed. Please check the file and try again.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div
      role="region"
      aria-label="Resume upload"
      className="mx-auto mb-6 w-full max-w-3xl rounded-xl border border-blue-200 bg-blue-50 p-5"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-blue-900">Upload your resume</h2>
          <p className="mt-0.5 text-sm text-blue-700">
            Upload your resume so we can match and tailor it to job listings.
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:items-end">
          <div className="flex gap-2">
            <label htmlFor="resume-file-input" className="sr-only">
              Choose resume file
            </label>
            <input
              id="resume-file-input"
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleFileChange}
              disabled={isUploading}
              aria-describedby={error ? 'resume-upload-error' : undefined}
              className="block w-full max-w-xs rounded-md border border-blue-300 bg-white px-3 py-1.5 text-sm text-gray-700 file:mr-2 file:rounded file:border-0 file:bg-blue-100 file:px-2 file:py-1 file:text-xs file:font-medium file:text-blue-700 disabled:opacity-50"
            />
            <button
              onClick={handleUpload}
              disabled={isUploading || !selectedFile}
              aria-busy={isUploading}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>
          {selectedFile && !error && (
            <p className="text-xs text-blue-600">{selectedFile.name}</p>
          )}
          {error && (
            <p id="resume-upload-error" role="alert" className="text-xs text-red-600">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
