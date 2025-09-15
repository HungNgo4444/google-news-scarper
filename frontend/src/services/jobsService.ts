import type { JobResponse, CreateJobRequest, JobListResponse } from '../types/shared';
import { apiClient } from './api';

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
}