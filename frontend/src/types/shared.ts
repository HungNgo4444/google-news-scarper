// Shared TypeScript interfaces matching backend models

export interface Category {
  id: string;
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  is_active: boolean;
  language: string;
  country: string;
  schedule_enabled?: boolean;
  schedule_interval_minutes?: number | null;
  last_scheduled_run_at?: string | null;
  next_scheduled_run_at?: string | null;
  crawl_period?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateCategoryRequest {
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  is_active: boolean;
  language: string;
  country: string;
  crawl_period?: string | null;
}

export interface UpdateCategoryRequest {
  name?: string;
  keywords?: string[];
  exclude_keywords?: string[];
  is_active?: boolean;
  language?: string;
  country?: string;
  crawl_period?: string | null;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

// Job-related interfaces from story specification
export interface CrawlJob {
  id: string;
  category_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
  articles_found: number;
  error_message: string | null;
}

export interface JobResponse {
  id: string;
  category_id: string;
  category_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  celery_task_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  articles_found: number;
  articles_saved: number;
  error_message: string | null;
  retry_count: number;
  priority: number;
  correlation_id: string | null;
  job_type?: 'SCHEDULED' | 'ON_DEMAND';
  created_at: string;
  updated_at: string;
  duration_seconds: number | null;
  success_rate: number;
}

export interface CreateJobRequest {
  category_id: string;
  priority?: number;
  metadata?: object;
  start_date?: string;
  end_date?: string;
  max_results?: number;
}

export interface JobListResponse {
  jobs: JobResponse[];
  total: number;
  pending_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
}

// Schedule configuration interfaces
export interface UpdateScheduleConfigRequest {
  enabled: boolean;
  interval_minutes?: number | null;
}

export interface ScheduleConfigResponse {
  category_id: string;
  category_name: string;
  schedule_enabled: boolean;
  schedule_interval_minutes: number | null;
  schedule_display: string;
  last_scheduled_run_at: string | null;
  next_scheduled_run_at: string | null;
  next_run_display: string | null;
}

export interface ScheduleCapacityResponse {
  total_scheduled_categories: number;
  estimated_jobs_per_hour: number;
  capacity_status: 'normal' | 'warning' | 'critical';
  warnings: string[];
  recommendations: string[];
}