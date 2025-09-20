// Shared TypeScript interfaces matching backend models

export interface Category {
  id: string;
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  is_active: boolean;
  language: string;
  country: string;
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
}

export interface UpdateCategoryRequest {
  name?: string;
  keywords?: string[];
  exclude_keywords?: string[];
  is_active?: boolean;
  language?: string;
  country?: string;
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
  created_at: string;
  updated_at: string;
  duration_seconds: number | null;
  success_rate: number;
}

export interface CreateJobRequest {
  category_id: string;
  priority?: number;
  metadata?: object;
}

export interface JobListResponse {
  jobs: JobResponse[];
  total: number;
  pending_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
}