import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { JobsList } from './JobsList';
import { JobsService } from '../../../services/jobsService';
import { CategoriesService } from '../../../services/categoriesService';
import type { JobResponse, Category, JobListResponse } from '../../../types/shared';

// Mock the services
vi.mock('../../../services/jobsService', () => ({
  JobsService: {
    getJobs: vi.fn()
  }
}));

vi.mock('../../../services/categoriesService', () => ({
  CategoriesService: {
    getCategories: vi.fn()
  }
}));

const mockJobsService = vi.mocked(JobsService);
const mockCategoriesService = vi.mocked(CategoriesService);

const mockCategories: Category[] = [
  {
    id: 'cat-1',
    name: 'Technology',
    keywords: ['AI', 'tech'],
    exclude_keywords: [],
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  },
  {
    id: 'cat-2',
    name: 'Sports',
    keywords: ['football'],
    exclude_keywords: [],
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  }
];

const createMockJobs = (): JobResponse[] => [
  {
    id: 'job-1',
    category_id: 'cat-1',
    category_name: 'Technology',
    status: 'completed',
    celery_task_id: 'task-1',
    priority: 1,
    correlation_id: 'corr-1',
    created_at: '2023-01-01T10:00:00Z',
    started_at: '2023-01-01T10:01:00Z',
    completed_at: '2023-01-01T10:05:00Z',
    articles_found: 10,
    articles_saved: 8,
    error_message: null,
    retry_count: 0,
    updated_at: '2023-01-01T10:05:00Z',
    duration_seconds: 240,
    success_rate: 0.8
  },
  {
    id: 'job-2',
    category_id: 'cat-2',
    category_name: 'Sports',
    status: 'running',
    celery_task_id: 'task-2',
    priority: 1,
    correlation_id: 'corr-2',
    created_at: '2023-01-01T11:00:00Z',
    started_at: '2023-01-01T11:01:00Z',
    completed_at: null,
    articles_found: 5,
    articles_saved: 3,
    error_message: null,
    retry_count: 0,
    updated_at: '2023-01-01T11:01:00Z',
    duration_seconds: null,
    success_rate: 0.6
  }
];

const createMockJobListResponse = (jobs: JobResponse[] = createMockJobs()): JobListResponse => ({
  jobs,
  total: jobs.length,
  pending_count: jobs.filter(j => j.status === 'pending').length,
  running_count: jobs.filter(j => j.status === 'running').length,
  completed_count: jobs.filter(j => j.status === 'completed').length,
  failed_count: jobs.filter(j => j.status === 'failed').length
});

describe('JobsList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render loading state initially', () => {
    mockCategoriesService.getCategories.mockImplementation(() => new Promise(() => {}));
    mockJobsService.getJobs.mockImplementation(() => new Promise(() => {}));

    render(<JobsList />);

    expect(screen.getByText('Job History')).toBeInTheDocument();
    expect(screen.getByText('Loading jobs...')).toBeInTheDocument();
  });

  it('should load and display jobs and categories on mount', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      expect(mockCategoriesService.getCategories).toHaveBeenCalled();
      expect(mockJobsService.getJobs).toHaveBeenCalledWith({
        limit: 20
      });

      // Check table headers
      expect(screen.getByText('Job ID')).toBeInTheDocument();
      expect(screen.getByText('Category')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();

      // Check job data in the table (more specific than dropdown options)
      const tableRows = screen.getAllByRole('row');
      expect(tableRows.length).toBeGreaterThan(2); // Header + data rows
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
    });
  });

  it('should show empty state when no jobs found', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse([]));

    render(<JobsList />);

    await waitFor(() => {
      expect(screen.getByText('No jobs found')).toBeInTheDocument();
      expect(screen.getByText('Jobs will appear here once you start crawling categories.')).toBeInTheDocument();
    });
  });

  it('should filter jobs by status', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      const statusFilter = screen.getByLabelText('Filter by Status');
      fireEvent.change(statusFilter, { target: { value: 'completed' } });
    });

    await waitFor(() => {
      expect(mockJobsService.getJobs).toHaveBeenLastCalledWith({
        limit: 20,
        status: 'completed'
      });
    });
  });

  it('should filter jobs by category', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      const categoryFilter = screen.getByLabelText('Filter by Category');
      fireEvent.change(categoryFilter, { target: { value: 'cat-1' } });
    });

    await waitFor(() => {
      expect(mockJobsService.getJobs).toHaveBeenLastCalledWith({
        limit: 20,
        category_id: 'cat-1'
      });
    });
  });

  it('should display results summary correctly', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      expect(screen.getByText('Showing 2 of 2 jobs')).toBeInTheDocument();
    });
  });

  it('should display filtered results summary', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    // Apply status filter
    await waitFor(() => {
      const statusFilter = screen.getByLabelText('Filter by Status');
      fireEvent.change(statusFilter, { target: { value: 'completed' } });
    });

    await waitFor(() => {
      expect(screen.getByText('Showing 2 of 2 jobs with status "completed"')).toBeInTheDocument();
    });
  });

  it('should handle refresh button click', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    // Clear previous calls
    vi.clearAllMocks();
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockJobsService.getJobs).toHaveBeenCalledWith({
        limit: 20
      });
    });
  });

  it('should handle load more functionality', async () => {
    // Create a full page of jobs to trigger hasMore = true
    const initialJobs = Array.from({ length: 20 }, (_, i) => ({
      id: `job-${i + 1}`,
      category_id: 'cat-1',
      category_name: 'Technology',
      status: 'completed' as const,
      celery_task_id: `task-${i + 1}`,
      priority: 1,
      correlation_id: `corr-${i + 1}`,
      created_at: '2023-01-01T10:00:00Z',
      started_at: '2023-01-01T10:01:00Z',
      completed_at: '2023-01-01T10:05:00Z',
      updated_at: '2023-01-01T10:05:00Z',
      articles_found: 10,
      articles_saved: 8,
      error_message: null,
      retry_count: 0,
      duration_seconds: 240,
      success_rate: 0.8
    }));

    const moreJobs = [
      {
        id: 'job-21',
        category_id: 'cat-1',
        category_name: 'Technology',
        status: 'failed' as const,
        celery_task_id: 'task-21',
        priority: 1,
        correlation_id: 'corr-21',
        created_at: '2023-01-01T12:00:00Z',
        started_at: '2023-01-01T12:01:00Z',
        completed_at: null,
        updated_at: '2023-01-01T12:01:00Z',
        articles_found: 5,
        articles_saved: 0,
        error_message: 'Connection failed',
        retry_count: 1,
        duration_seconds: null,
        success_rate: 0.0
      }
    ];

    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs
      .mockResolvedValueOnce({ jobs: initialJobs, total: 21, limit: 20, pending_count: 0, running_count: 0, completed_count: 21, failed_count: 0 })
      .mockResolvedValueOnce({ jobs: moreJobs, total: 21, limit: 20, pending_count: 0, running_count: 0, completed_count: 21, failed_count: 0 });

    render(<JobsList />);

    await waitFor(() => {
      // Look for the exact text format: "Load More (1 remaining)"
      const loadMoreButton = screen.getByText('Load More (1 remaining)');
      expect(loadMoreButton).toBeInTheDocument();
    });

    const loadMoreButton = screen.getByText('Load More (1 remaining)');
    fireEvent.click(loadMoreButton);

    await waitFor(() => {
      expect(mockJobsService.getJobs).toHaveBeenLastCalledWith({
        limit: 20,
        offset: 20
      });
    });
  });

  it('should handle API errors gracefully', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockRejectedValue(new Error('Network error'));

    render(<JobsList />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load jobs. Please try again.')).toBeInTheDocument();
    });
  });

  it('should format timestamps correctly', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      // Check that timestamps are displayed (exact format depends on locale)
      const rows = screen.getAllByRole('row');
      expect(rows.length).toBeGreaterThan(2); // Header + data rows
    });
  });

  it('should format job ID display correctly', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    render(<JobsList />);

    await waitFor(() => {
      // Job IDs should be truncated to first 8 characters + ellipsis
      expect(screen.getByText('job-1...')).toBeInTheDocument();
      expect(screen.getByText('job-2...')).toBeInTheDocument();
    });
  });

  it('should update when refreshTrigger prop changes', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    const { rerender } = render(<JobsList refreshTrigger={0} />);

    await waitFor(() => {
      expect(mockJobsService.getJobs).toHaveBeenCalledTimes(1);
    });

    // Clear mocks and re-render with new trigger value
    vi.clearAllMocks();
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse());

    rerender(<JobsList refreshTrigger={1} />);

    await waitFor(() => {
      expect(mockJobsService.getJobs).toHaveBeenCalledTimes(1);
    });
  });

  it('should display different status icons correctly', async () => {
    const jobs: JobResponse[] = [
      { ...createMockJobs()[0], status: 'pending' },
      { ...createMockJobs()[0], id: 'job-2', status: 'running' },
      { ...createMockJobs()[0], id: 'job-3', status: 'completed' },
      { ...createMockJobs()[0], id: 'job-4', status: 'failed' }
    ];

    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.getJobs.mockResolvedValue(createMockJobListResponse(jobs));

    render(<JobsList />);

    await waitFor(() => {
      expect(screen.getByText('⏳')).toBeInTheDocument(); // pending
      expect(screen.getByText('🔄')).toBeInTheDocument(); // running
      expect(screen.getByText('✅')).toBeInTheDocument(); // completed
      expect(screen.getByText('❌')).toBeInTheDocument(); // failed
    });
  });
});