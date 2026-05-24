// Resume
export interface ResumeResponse {
  id: string
  filename: string
  uploaded_at: string
  text_preview: string
}

// Search
export interface SearchCriteria {
  query: string
  location?: string
  remote_only?: boolean
  employment_type?: string
  seniority?: string
  posted_within_days?: number
  page?: number
}

export interface SearchStatusResponse {
  job_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  total_results: number | null
  error: string | null
}

// Jobs
export type RemoteStatus = 'remote' | 'hybrid' | 'onsite' | 'unspecified'

export interface JobPosting {
  id: string
  source: string
  title: string
  company: string | null
  location: string | null
  remote_status: RemoteStatus
  url: string
  compensation: string | null
  posted_date: string | null
  match_score: number | null
}

export interface JobsListResponse {
  items: JobPosting[]
  total: number
  page: number
  page_size: number
}

export interface JobFiltersResponse {
  sources: string[]
  companies: string[]
}

// Applications
export type ApplicationStatus = 'pending' | 'approved' | 'rejected' | 'submitted' | 'failed'

export interface ApplicationResponse {
  id: string
  job_posting_id: string
  status: ApplicationStatus
  match_score: number
  match_rationale: string
  tailored_resume_text: string
  resume_diff_json: string // JSON string: DiffHunk[]
  cover_letter_text: string
  tailoring_failed: boolean
  created_at: string
  approved_at: string | null
  submitted_at: string | null
  rejected_at: string | null
}

export type DiffHunkType = 'unchanged' | 'added' | 'removed'

export interface DiffHunk {
  type: DiffHunkType
  text: string
  line: number
}

// Prepare response
export interface PrepareApplicationResponse {
  status: string
  job_id: string
}
