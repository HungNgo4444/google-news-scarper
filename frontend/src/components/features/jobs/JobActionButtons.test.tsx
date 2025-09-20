import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { JobActionButtons } from './JobActionButtons';
import { JobsService } from '../../../services/jobsService';
import type { JobResponse } from '../../../types/shared';

// Mock the JobsService
vi.mock('../../../services/jobsService', () => ({
  JobsService: {
    updateJobPriority: vi.fn(),
    deleteJob: vi.fn()
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
  articles_found: 0,
  articles_saved: 0,
  error_message: null,
  retry_count: 0,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
  started_at: status === 'pending' ? null : '2023-01-01T00:01:00Z',
  completed_at: status === 'completed' ? '2023-01-01T00:02:00Z' : null,
  duration_seconds: status === 'completed' ? 60 : null,
  success_rate: status === 'completed' ? 0.8 : 0,
  ...overrides
});

describe('JobActionButtons', () => {
  const mockOnJobUpdated = vi.fn();
  const mockOnJobDeleted = vi.fn();
  const mockOnViewArticles = vi.fn();
  const mockOnEditJob = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnJobUpdated.mockClear();
    mockOnJobDeleted.mockClear();
    mockOnViewArticles.mockClear();
    mockOnEditJob.mockClear();
  });

  const defaultProps = {
    job: createMockJob('pending'),
    onJobUpdated: mockOnJobUpdated,
    onJobDeleted: mockOnJobDeleted,
    onViewArticles: mockOnViewArticles,
    onEditJob: mockOnEditJob
  };

  describe('Button Rendering', () => {
    it('should render all action buttons for pending job', () => {
      render(<JobActionButtons {...defaultProps} />);

      expect(screen.getByRole('button', { name: /run now/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /view articles/i })).toBeInTheDocument();
    });

    it('should disable Run Now button for running job', () => {
      const runningJob = createMockJob('running');
      render(<JobActionButtons {...defaultProps} job={runningJob} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      expect(runNowButton).toBeDisabled();
      expect(runNowButton).toHaveAttribute('title', 'Job is already running');
    });

    it('should disable Run Now button for completed job', () => {
      const completedJob = createMockJob('completed');
      render(<JobActionButtons {...defaultProps} job={completedJob} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      expect(runNowButton).toBeDisabled();
      expect(runNowButton).toHaveAttribute('title', 'Job is already completed');
    });

    it('should disable Edit button for running job', () => {
      const runningJob = createMockJob('running');
      render(<JobActionButtons {...defaultProps} job={runningJob} />);

      const editButton = screen.getByRole('button', { name: /edit/i });
      expect(editButton).toBeDisabled();
      expect(editButton).toHaveAttribute('title', 'Cannot edit running job');
    });

    it('should show different tooltip for failed job Run Now button', () => {
      const failedJob = createMockJob('failed');
      render(<JobActionButtons {...defaultProps} job={failedJob} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      expect(runNowButton).not.toBeDisabled();
      expect(runNowButton).toHaveAttribute('title', 'Retry failed job with high priority');
    });
  });

  describe('Run Now Functionality', () => {
    it('should call updateJobPriority when Run Now is clicked', async () => {
      const user = userEvent.setup();
      const updatedJob = createMockJob('pending', { priority: 8 });
      mockJobsService.updateJobPriority.mockResolvedValue(updatedJob);

      render(<JobActionButtons {...defaultProps} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      await user.click(runNowButton);

      expect(mockJobsService.updateJobPriority).toHaveBeenCalledWith('job-123', { priority: 8 });
      await waitFor(() => {
        expect(mockOnJobUpdated).toHaveBeenCalledWith(updatedJob);
      });
    });

    it('should show loading state when Run Now is processing', async () => {
      const user = userEvent.setup();
      mockJobsService.updateJobPriority.mockImplementation(() => new Promise(() => {}));

      render(<JobActionButtons {...defaultProps} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      await user.click(runNowButton);

      expect(runNowButton).toBeDisabled();
      expect(screen.getByText('⏳')).toBeInTheDocument();
    });

    it('should handle Run Now API error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockJobsService.updateJobPriority.mockRejectedValue(new Error('Network error'));

      render(<JobActionButtons {...defaultProps} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      await user.click(runNowButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to update job priority:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('should use priority 10 for failed jobs', async () => {
      const user = userEvent.setup();
      const failedJob = createMockJob('failed');
      const updatedJob = createMockJob('failed', { priority: 10 });
      mockJobsService.updateJobPriority.mockResolvedValue(updatedJob);

      render(<JobActionButtons {...defaultProps} job={failedJob} />);

      const runNowButton = screen.getByRole('button', { name: /run now/i });
      await user.click(runNowButton);

      expect(mockJobsService.updateJobPriority).toHaveBeenCalledWith('job-123', { priority: 10 });
    });
  });

  describe('Edit Job Functionality', () => {
    it('should call onEditJob when Edit button is clicked', async () => {
      const user = userEvent.setup();
      render(<JobActionButtons {...defaultProps} />);

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      expect(mockOnEditJob).toHaveBeenCalledWith(defaultProps.job);
    });
  });

  describe('View Articles Functionality', () => {
    it('should call onViewArticles when View Articles button is clicked', async () => {
      const user = userEvent.setup();
      render(<JobActionButtons {...defaultProps} />);

      const viewButton = screen.getByRole('button', { name: /view articles/i });
      await user.click(viewButton);

      expect(mockOnViewArticles).toHaveBeenCalledWith(defaultProps.job);
    });

    it('should show article count in View Articles button when available', () => {
      const jobWithArticles = createMockJob('completed', { articles_found: 15 });
      render(<JobActionButtons {...defaultProps} job={jobWithArticles} />);

      expect(screen.getByText('View Articles (15)')).toBeInTheDocument();
    });

    it('should show "View Articles" without count when no articles', () => {
      render(<JobActionButtons {...defaultProps} />);

      expect(screen.getByText('View Articles')).toBeInTheDocument();
    });
  });

  describe('Delete Job Functionality', () => {
    it('should show confirmation dialog when Delete is clicked', async () => {
      const user = userEvent.setup();
      render(<JobActionButtons {...defaultProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      expect(screen.getByText('Confirm Job Deletion')).toBeInTheDocument();
      expect(screen.getByText(/are you sure you want to delete this job/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete job/i })).toBeInTheDocument();
    });

    it('should close dialog when Cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<JobActionButtons {...defaultProps} />);

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(screen.queryByText('Confirm Job Deletion')).not.toBeInTheDocument();
    });

    it('should call deleteJob API when deletion is confirmed', async () => {
      const user = userEvent.setup();
      const deletionResponse = {
        job_id: 'job-123',
        impact: { articles_affected: 5, articles_deleted: 0, was_running: false },
        message: 'Job deleted successfully',
        deleted_at: '2023-01-01T00:00:00Z'
      };
      mockJobsService.deleteJob.mockResolvedValue(deletionResponse);

      render(<JobActionButtons {...defaultProps} />);

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen.getByRole('button', { name: /delete job/i });
      await user.click(confirmButton);

      expect(mockJobsService.deleteJob).toHaveBeenCalledWith('job-123', {
        force: false,
        delete_articles: false
      });

      await waitFor(() => {
        expect(mockOnJobDeleted).toHaveBeenCalledWith('job-123', deletionResponse);
      });
    });

    it('should show force deletion option for running job', async () => {
      const user = userEvent.setup();
      const runningJob = createMockJob('running');
      render(<JobActionButtons {...defaultProps} job={runningJob} />);

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      expect(screen.getByText(/this job is currently running/i)).toBeInTheDocument();
      expect(screen.getByRole('checkbox', { name: /force deletion/i })).toBeInTheDocument();
    });

    it('should show delete articles option for jobs with articles', async () => {
      const user = userEvent.setup();
      const jobWithArticles = createMockJob('completed', { articles_found: 10 });
      render(<JobActionButtons {...defaultProps} job={jobWithArticles} />);

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      expect(screen.getByText(/this job has 10 associated articles/i)).toBeInTheDocument();
      expect(screen.getByRole('checkbox', { name: /delete articles/i })).toBeInTheDocument();
    });

    it('should send correct flags when checkboxes are selected', async () => {
      const user = userEvent.setup();
      const runningJobWithArticles = createMockJob('running', { articles_found: 5 });
      const deletionResponse = {
        job_id: 'job-123',
        impact: { articles_affected: 5, articles_deleted: 5, was_running: true },
        message: 'Job deleted successfully',
        deleted_at: '2023-01-01T00:00:00Z'
      };
      mockJobsService.deleteJob.mockResolvedValue(deletionResponse);

      render(<JobActionButtons {...defaultProps} job={runningJobWithArticles} />);

      // Open dialog
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      // Select both checkboxes
      const forceCheckbox = screen.getByRole('checkbox', { name: /force deletion/i });
      const deleteArticlesCheckbox = screen.getByRole('checkbox', { name: /delete articles/i });

      await user.click(forceCheckbox);
      await user.click(deleteArticlesCheckbox);

      // Confirm deletion
      const confirmButton = screen.getByRole('button', { name: /delete job/i });
      await user.click(confirmButton);

      expect(mockJobsService.deleteJob).toHaveBeenCalledWith('job-123', {
        force: true,
        delete_articles: true
      });
    });

    it('should show loading state during deletion', async () => {
      const user = userEvent.setup();
      mockJobsService.deleteJob.mockImplementation(() => new Promise(() => {}));

      render(<JobActionButtons {...defaultProps} />);

      // Open dialog and confirm
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      const confirmButton = screen.getByRole('button', { name: /delete job/i });
      await user.click(confirmButton);

      expect(screen.getByText('Deleting...')).toBeInTheDocument();
      expect(confirmButton).toBeDisabled();
    });

    it('should handle deletion API error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockJobsService.deleteJob.mockRejectedValue(new Error('Network error'));

      render(<JobActionButtons {...defaultProps} />);

      // Open dialog and confirm
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      const confirmButton = screen.getByRole('button', { name: /delete job/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to delete job:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Button States', () => {
    it('should show correct button states for pending job', () => {
      render(<JobActionButtons {...defaultProps} />);

      expect(screen.getByRole('button', { name: /run now/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /edit/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /delete/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /view articles/i })).not.toBeDisabled();
    });

    it('should show correct button states for running job', () => {
      const runningJob = createMockJob('running');
      render(<JobActionButtons {...defaultProps} job={runningJob} />);

      expect(screen.getByRole('button', { name: /run now/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /edit/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /delete/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /view articles/i })).not.toBeDisabled();
    });

    it('should show correct button states for completed job', () => {
      const completedJob = createMockJob('completed');
      render(<JobActionButtons {...defaultProps} job={completedJob} />);

      expect(screen.getByRole('button', { name: /run now/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /edit/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /delete/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /view articles/i })).not.toBeDisabled();
    });

    it('should show correct button states for failed job', () => {
      const failedJob = createMockJob('failed');
      render(<JobActionButtons {...defaultProps} job={failedJob} />);

      expect(screen.getByRole('button', { name: /run now/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /edit/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /delete/i })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /view articles/i })).not.toBeDisabled();
    });
  });
});