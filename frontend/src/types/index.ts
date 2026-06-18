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
  posted_within_days?: number
  page?: number
}

export interface SearchStatusResponse {
  job_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  total_results: number | null
  error: string | null
  completed_adapters: number
  total_adapters: number
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
  description: string
  compensation: string | null
  posted_date: string | null
  match_score: number | null
  relevance_score: number | null
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
export type ApplicationStatus =
  | 'preparing'
  | 'prep_failed'
  | 'pending'
  | 'rejected'
  | 'submitted'
  | 'failed'
  | 'saved'

// Pipeline stage reported on prep_stage while status === 'preparing'.
export type PrepStage = '' | 'parsing' | 'scoring' | 'tailoring' | 'drafting'

export interface ApplicationResponse {
  id: string
  job_posting_id: string
  status: ApplicationStatus
  prep_stage: PrepStage
  prep_error: string
  match_score: number
  match_rationale: string
  tailored_resume_text: string
  resume_diff_json: string // JSON string: DiffHunk[]
  cover_letter_text: string
  tailoring_failed: boolean
  resume_data_yaml: string
  cover_letter_data_yaml: string
  created_at: string
  approved_at: string | null
  submitted_at: string | null
  rejected_at: string | null
  match_gaps: string[]
  saved_at: string | null
}

export interface SavedApplicationSummary {
  id: string
  job_title: string
  company: string | null
  location: string | null
  match_score: number
  saved_at: string | null
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

// ── Saved searches ──────────────────────────────────────────────────────────

export interface SavedSearch {
  id: string
  name: string
  criteria: SearchCriteria
  created_at: string
  last_run_at: string | null
  last_search_job_id: string | null
}

export interface RunSavedSearchResponse {
  saved_search_id: string
  search_job_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
}

export interface SavedSearchDiff {
  search_job_id: string
  new_count: number
  new_posting_ids: string[]
  is_first_run: boolean
}

// ── Insights ──────────────────────────────────────────────────────────────────

export type InsightsRegion = 'in' | 'us' | 'gb' | 'world'

export interface NewsItem {
  title: string
  url: string
  domain: string
  seendate: string // date format: YYYYMMDDThhmmssZ
}

export interface SalaryStat {
  role: string
  median: number | null
  currency: string
  sample_size: number
}

export interface HotField {
  label: string
  tag: string
  openings: number
  mean_salary: number | null
  currency: string
}

export interface TrendPoint {
  period?: string  // salary_history: "YYYY-MM"
  year?: number    // unemployment / employment
  value: number
}

export interface TrendData {
  salary_history: TrendPoint[]
  unemployment: TrendPoint[]
  employment: TrendPoint[]
}

export interface Insights {
  region: InsightsRegion
  currency: string
  generated_at: string // ISO 8601
  news: NewsItem[]
  salaries: SalaryStat[]
  hottest_fields: HotField[]
  trends: TrendData
}
