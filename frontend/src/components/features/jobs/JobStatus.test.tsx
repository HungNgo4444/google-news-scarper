import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { JobStatus } from './JobStatus';
import { JobsService } from '../../../services/jobsService';
import type { JobResponse } from '../../../types/shared';

// Mock the JobsService
vi.mock('../../../services/jobsService', () => ({
  JobsService: {
    getJobStatus: vi.fn()
  }
}));

const mockJobsService = vi.mocked(JobsService);

const createMockJob = (status: JobResponse['status'], overrides?: Partial<JobResponse>): JobResponse => ({
  id: 'job-123',
  category_id: 'cat-1',
  category_name: 'Technology',
  status,
  celery_task_id: 'task-123',
  priority: 1,
  correlation_id: 'corr-123',
  created_at: '2023-01-01T00:00:00Z',
  started_at: status === 'pending' ? null : '2023-01-01T00:01:00Z',
  completed_at: status === 'completed' ? '2023-01-01T00:02:00Z' : null,
  ...overrides
});

describe('JobStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render loading state initially', () => {
    mockJobsService.getJobStatus.mockImplementation(() => new Promise(() => {}));

    render(<JobStatus jobId="job-123" />);

    expect(screen.getByText('Loading job status...')).toBeInTheDocument();
  });

  it('should fetch and display job status on mount', async () => {
    const mockJob = createMockJob('running');
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(mockJobsService.getJobStatus).toHaveBeenCalledWith('job-123');
      expect(screen.getByText('Job Status')).toBeInTheDocument();
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('job-123')).toBeInTheDocument();
    });
  });

  it('should display pending status correctly', async () => {
    const mockJob = createMockJob('pending');
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(screen.getByText('PENDING')).toBeInTheDocument();
      expect(screen.getByText('⏳')).toBeInTheDocument();
    });
  });

  it('should display running status with auto-refresh indicator', async () => {
    const mockJob = createMockJob('running');
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
      expect(screen.getByText('🔄')).toBeInTheDocument();
      expect(screen.getByText('Auto-refreshing every 2 seconds')).toBeInTheDocument();
      expect(screen.getByText('Crawl in Progress')).toBeInTheDocument();
    });
  });

  it('should display completed status correctly', async () => {
    const mockJob = createMockJob('completed');
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);
    const onJobComplete = vi.fn();

    render(<JobStatus jobId="job-123" onJobComplete={onJobComplete} />);

    await waitFor(() => {
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
      expect(screen.getByText('✅')).toBeInTheDocument();
      expect(screen.getByText('Crawl Completed Successfully')).toBeInTheDocument();
      expect(onJobComplete).toHaveBeenCalledWith(mockJob);
    });
  });

  it('should display failed status correctly', async () => {
    const mockJob = createMockJob('failed');
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(screen.getByText('FAILED')).toBeInTheDocument();
      expect(screen.getByText('❌')).toBeInTheDocument();
      expect(screen.getByText('Crawl Job Failed')).toBeInTheDocument();
    });
  });

  it('should format timestamps correctly', async () => {
    const mockJob = createMockJob('completed', {
      created_at: '2023-01-01T12:00:00Z',
      started_at: '2023-01-01T12:01:00Z',
      completed_at: '2023-01-01T12:05:00Z'
    });
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      // Timestamps are formatted using toLocaleString, exact format depends on locale
      expect(screen.getByText(/Created:/)).toBeInTheDocument();
      expect(screen.getByText(/Started:/)).toBeInTheDocument();
      expect(screen.getByText(/Completed:/)).toBeInTheDocument();
    });
  });

  it('should show technical details when expanded', async () => {
    const mockJob = createMockJob('running');
    mockJobsService.getJobStatus.mockResolvedValue(mockJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(screen.getByText('Technical Details')).toBeInTheDocument();
      // Details are initially collapsed, but content should be in DOM
      expect(screen.getByText('task-123')).toBeInTheDocument();
      expect(screen.getByText('corr-123')).toBeInTheDocument();
    });
  });

  it('should call API for initial status fetch', async () => {
    const runningJob = createMockJob('running');
    mockJobsService.getJobStatus.mockResolvedValue(runningJob);

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(mockJobsService.getJobStatus).toHaveBeenCalledWith('job-123');
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
    });
  });

  it('should handle completed jobs', async () => {
    const completedJob = createMockJob('completed');
    const onJobComplete = vi.fn();
    mockJobsService.getJobStatus.mockResolvedValue(completedJob);

    render(<JobStatus jobId="job-123" onJobComplete={onJobComplete} />);

    await waitFor(() => {
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
      expect(onJobComplete).toHaveBeenCalledWith(completedJob);
    });
  });

  it('should handle API errors gracefully', async () => {
    mockJobsService.getJobStatus.mockRejectedValue(new Error('Network error'));

    render(<JobStatus jobId="job-123" />);

    await waitFor(() => {
      expect(screen.getByText('Failed to fetch job status')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });
  });

  it('should handle empty jobId', () => {
    render(<JobStatus jobId="" />);
    expect(mockJobsService.getJobStatus).not.toHaveBeenCalled();
  });
});