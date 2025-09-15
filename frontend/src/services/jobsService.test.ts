import { describe, it, expect, vi, beforeEach } from 'vitest';
import { JobsService } from './jobsService';
import { apiClient } from './api';
import type { JobResponse, CreateJobRequest, JobListResponse } from '../types/shared';

// Mock the api client
vi.mock('./api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  }
}));

const mockApiClient = vi.mocked(apiClient);

describe('JobsService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createJob', () => {
    it('should call POST API with correct data', async () => {
      const createData: CreateJobRequest = {
        category_id: 'cat-123',
        priority: 1,
        metadata: { source: 'manual' }
      };

      const mockResponse: JobResponse = {
        id: 'job-123',
        category_id: 'cat-123',
        category_name: 'Technology',
        status: 'pending',
        celery_task_id: 'task-123',
        priority: 1,
        correlation_id: 'corr-123',
        created_at: '2023-01-01T00:00:00Z',
        started_at: null,
        completed_at: null
      };

      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await JobsService.createJob(createData);

      expect(mockApiClient.post).toHaveBeenCalledWith('/api/v1/jobs', createData);
      expect(result).toEqual(mockResponse);
    });

    it('should handle minimal job creation request', async () => {
      const createData: CreateJobRequest = {
        category_id: 'cat-123'
      };

      const mockResponse: JobResponse = {
        id: 'job-123',
        category_id: 'cat-123',
        category_name: 'Technology',
        status: 'pending',
        celery_task_id: 'task-123',
        priority: 0,
        correlation_id: 'corr-123',
        created_at: '2023-01-01T00:00:00Z',
        started_at: null,
        completed_at: null
      };

      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await JobsService.createJob(createData);

      expect(mockApiClient.post).toHaveBeenCalledWith('/api/v1/jobs', createData);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getJobs', () => {
    it('should call API with correct URL for all jobs', async () => {
      const mockResponse: JobListResponse = {
        jobs: [],
        total: 0,
        pending_count: 0,
        running_count: 0,
        completed_count: 0,
        failed_count: 0
      };

      mockApiClient.get.mockResolvedValue(mockResponse);

      const result = await JobsService.getJobs();

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v1/jobs');
      expect(result).toEqual(mockResponse);
    });

    it('should call API with query parameters when provided', async () => {
      const params = {
        status: 'running',
        category_id: 'cat-123',
        limit: 10
      };

      const mockResponse: JobListResponse = {
        jobs: [],
        total: 0,
        pending_count: 0,
        running_count: 0,
        completed_count: 0,
        failed_count: 0
      };

      mockApiClient.get.mockResolvedValue(mockResponse);

      await JobsService.getJobs(params);

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v1/jobs?status=running&category_id=cat-123&limit=10&offset=20');
    });

    it('should handle partial parameters', async () => {
      const params = {
        status: 'completed',
        limit: 5
      };

      mockApiClient.get.mockResolvedValue({ jobs: [], total: 0, pending_count: 0, running_count: 0, completed_count: 0, failed_count: 0 });

      await JobsService.getJobs(params);

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v1/jobs?status=completed&limit=5');
    });
  });

  describe('getJobStatus', () => {
    it('should call GET API with correct job ID', async () => {
      const jobId = 'job-123';
      const mockResponse: JobResponse = {
        id: jobId,
        category_id: 'cat-123',
        category_name: 'Technology',
        status: 'running',
        celery_task_id: 'task-123',
        priority: 1,
        correlation_id: 'corr-123',
        created_at: '2023-01-01T00:00:00Z',
        started_at: '2023-01-01T00:01:00Z',
        completed_at: null
      };

      mockApiClient.get.mockResolvedValue(mockResponse);

      const result = await JobsService.getJobStatus(jobId);

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v1/jobs/job-123/status');
      expect(result).toEqual(mockResponse);
    });
  });
});