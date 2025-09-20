import type { JobResponse, CreateJobRequest, JobListResponse } from '../types/shared';
import { apiClient } from './api';

// Additional interfaces for new API endpoints
export interface PriorityUpdateRequest {
  priority: number;
}

export interface JobUpdateRequest {
  priority?: number;
  retry_count?: number;
  job_metadata?: Record<string, any>;
}

export interface JobDeletionRequest {
  force?: boolean;
  delete_articles?: boolean;
}

export interface JobDeletionResponse {
  job_id: string;
  impact: {
    articles_affected: number;
    articles_deleted: number;
    was_running: boolean;
  };
  message: string;
  deleted_at: string;
}

export class JobsService {
  private static baseUrl = '/api/v1/jobs';

  static async createJob(data: CreateJobRequest): Promise<JobResponse> {
    return apiClient.post<JobResponse>(this.baseUrl, data);
  }

  static async getJobs(params?: {
    status?: string;
    category_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<JobListResponse> {
    const queryParams = new URLSearchParams();

    if (params?.status) queryParams.append('status', params.status);
    if (params?.category_id) queryParams.append('category_id', params.category_id);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset) queryParams.append('offset', params.offset.toString());

    const url = queryParams.toString()
      ? `${this.baseUrl}?${queryParams.toString()}`
      : this.baseUrl;

    return apiClient.get<JobListResponse>(url);
  }

  static async getJobStatus(jobId: string): Promise<JobResponse> {
    return apiClient.get<JobResponse>(`${this.baseUrl}/${jobId}/status`);
  }

  static async updateJobPriority(
    jobId: string,
    data: PriorityUpdateRequest
  ): Promise<JobResponse> {
    return apiClient.patch<JobResponse>(`${this.baseUrl}/${jobId}/priority`, data);
  }

  static async updateJob(
    jobId: string,
    data: JobUpdateRequest
  ): Promise<JobResponse> {
    return apiClient.put<JobResponse>(`${this.baseUrl}/${jobId}`, data);
  }

  static async deleteJob(
    jobId: string,
    data: JobDeletionRequest = {}
  ): Promise<JobDeletionResponse> {
    return apiClient.delete<JobDeletionResponse>(`${this.baseUrl}/${jobId}`, data);
  }

  static async executeJobNow(jobId: string): Promise<JobResponse> {
    /**
     * Execute existing job immediately (Run Now functionality).
     *
     * This is the critical fix for the "Run Now" button functionality.
     * Creates a new high-priority job based on the existing job configuration
     * and triggers immediate execution.
     *
     * @param jobId - UUID of the job to execute immediately
     * @returns Promise resolving to new job data with high priority
     */
    return apiClient.post<JobResponse>(`${this.baseUrl}/${jobId}/execute`);
  }
}