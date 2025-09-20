import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { JobEditModal } from './JobEditModal';
import { JobsService } from '../../../services/jobsService';
import type { JobResponse } from '../../../types/shared';

// Mock the JobsService
vi.mock('../../../services/jobsService', () => ({
  JobsService: {
    updateJob: vi.fn()
  }
}));

const mockJobsService = vi.mocked(JobsService);

const createMockJob = (status: JobResponse['status'], overrides?: Partial<JobResponse>): JobResponse => ({
  id: 'job-123',
  category_id: 'cat-1',
  category_name: 'Technology',
  status,
  celery_task_id: 'task-123',
  priority: 5,
  correlation_id: 'corr-123',
  articles_found: 10,
  articles_saved: 8,
  error_message: null,
  retry_count: 2,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
  started_at: status === 'pending' ? null : '2023-01-01T00:01:00Z',
  completed_at: status === 'completed' ? '2023-01-01T00:02:00Z' : null,
  duration_seconds: status === 'completed' ? 60 : null,
  success_rate: status === 'completed' ? 0.8 : 0,
  ...overrides
});

describe('JobEditModal', () => {
  const mockOnClose = vi.fn();
  const mockOnJobUpdated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnClose.mockClear();
    mockOnJobUpdated.mockClear();
  });

  const defaultProps = {
    isOpen: true,
    onClose: mockOnClose,
    job: createMockJob('pending'),
    onJobUpdated: mockOnJobUpdated
  };

  describe('Modal Rendering', () => {
    it('should not render when isOpen is false', () => {
      render(<JobEditModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByText('Edit Job Configuration')).not.toBeInTheDocument();
    });

    it('should render modal with job information', () => {
      render(<JobEditModal {...defaultProps} />);

      expect(screen.getByText('Edit Job Configuration')).toBeInTheDocument();
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('job-123')).toBeInTheDocument();
    });

    it('should show current job values in form fields', () => {
      const job = createMockJob('pending', { priority: 7, retry_count: 3 });
      render(<JobEditModal {...defaultProps} job={job} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      const retryInput = screen.getByLabelText(/retry count/i);

      expect(priorityInput).toHaveValue(7);
      expect(retryInput).toHaveValue(3);
    });

    it('should render form action buttons', () => {
      render(<JobEditModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
    });
  });

  describe('Form Interactions', () => {
    it('should update priority value when input changes', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '8');

      expect(priorityInput).toHaveValue(8);
    });

    it('should update retry count when input changes', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const retryInput = screen.getByLabelText(/retry count/i);
      await user.clear(retryInput);
      await user.type(retryInput, '5');

      expect(retryInput).toHaveValue(5);
    });

    it('should handle job metadata input', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const metadataTextarea = screen.getByLabelText(/job metadata/i);
      await user.type(metadataTextarea, '{"source": "manual", "priority": "high"}');

      expect(metadataTextarea).toHaveValue('{"source": "manual", "priority": "high"}');
    });

    it('should show job metadata as formatted JSON when provided', () => {
      const job = createMockJob('pending', {
        job_metadata: { source: 'test', environment: 'dev' }
      });
      render(<JobEditModal {...defaultProps} job={job} />);

      const metadataTextarea = screen.getByLabelText(/job metadata/i);
      expect(metadataTextarea).toHaveValue('{\n  "source": "test",\n  "environment": "dev"\n}');
    });
  });

  describe('Form Validation', () => {
    it('should show error for invalid priority value', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '-1');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      expect(screen.getByText('Priority must be between 0 and 10')).toBeInTheDocument();
    });

    it('should show error for priority value above maximum', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '15');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      expect(screen.getByText('Priority must be between 0 and 10')).toBeInTheDocument();
    });

    it('should show error for invalid retry count', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const retryInput = screen.getByLabelText(/retry count/i);
      await user.clear(retryInput);
      await user.type(retryInput, '-5');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      expect(screen.getByText('Retry count must be 0 or greater')).toBeInTheDocument();
    });

    it('should show error for invalid JSON in metadata', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const metadataTextarea = screen.getByLabelText(/job metadata/i);
      await user.type(metadataTextarea, '{invalid json}');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      expect(screen.getByText(/Invalid JSON format in metadata/)).toBeInTheDocument();
    });

    it('should not allow saving when there are validation errors', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '15');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      expect(mockJobsService.updateJob).not.toHaveBeenCalled();
    });
  });

  describe('Save Functionality', () => {
    it('should call updateJob API when form is submitted with valid data', async () => {
      const user = userEvent.setup();
      const updatedJob = createMockJob('pending', { priority: 8, retry_count: 4 });
      mockJobsService.updateJob.mockResolvedValue(updatedJob);

      render(<JobEditModal {...defaultProps} />);

      // Update priority
      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '8');

      // Update retry count
      const retryInput = screen.getByLabelText(/retry count/i);
      await user.clear(retryInput);
      await user.type(retryInput, '4');

      // Submit form
      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockJobsService.updateJob).toHaveBeenCalledWith('job-123', {
          priority: 8,
          retry_count: 4,
          job_metadata: undefined
        });
        expect(mockOnJobUpdated).toHaveBeenCalledWith(updatedJob);
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it('should include metadata in update request when provided', async () => {
      const user = userEvent.setup();
      const updatedJob = createMockJob('pending');
      mockJobsService.updateJob.mockResolvedValue(updatedJob);

      render(<JobEditModal {...defaultProps} />);

      const metadataTextarea = screen.getByLabelText(/job metadata/i);
      await user.type(metadataTextarea, '{"environment": "production"}');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockJobsService.updateJob).toHaveBeenCalledWith('job-123', {
          priority: 5,
          retry_count: 2,
          job_metadata: { environment: 'production' }
        });
      });
    });

    it('should only send changed fields in update request', async () => {
      const user = userEvent.setup();
      const updatedJob = createMockJob('pending', { priority: 7 });
      mockJobsService.updateJob.mockResolvedValue(updatedJob);

      render(<JobEditModal {...defaultProps} />);

      // Only change priority
      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '7');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockJobsService.updateJob).toHaveBeenCalledWith('job-123', {
          priority: 7,
          retry_count: 2,
          job_metadata: undefined
        });
      });
    });

    it('should show loading state during save', async () => {
      const user = userEvent.setup();
      mockJobsService.updateJob.mockImplementation(() => new Promise(() => {}));

      render(<JobEditModal {...defaultProps} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '7');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      expect(screen.getByText('Saving...')).toBeInTheDocument();
      expect(saveButton).toBeDisabled();
    });

    it('should handle save API error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockJobsService.updateJob.mockRejectedValue(new Error('Network error'));

      render(<JobEditModal {...defaultProps} />);

      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '7');

      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to update job. Please try again.')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it('should clear error message when form is modified after error', async () => {
      const user = userEvent.setup();
      mockJobsService.updateJob.mockRejectedValue(new Error('Network error'));

      render(<JobEditModal {...defaultProps} />);

      // Trigger error
      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to update job. Please try again.')).toBeInTheDocument();
      });

      // Modify form
      const priorityInput = screen.getByLabelText(/priority/i);
      await user.type(priorityInput, '7');

      expect(screen.queryByText('Failed to update job. Please try again.')).not.toBeInTheDocument();
    });
  });

  describe('Cancel Functionality', () => {
    it('should call onClose when Cancel button is clicked', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should call onClose when clicking outside modal', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      // Click on the overlay (outside the modal)
      const overlay = screen.getByRole('dialog').parentElement;
      await user.click(overlay!);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should call onClose when pressing Escape key', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      await user.keyboard('{Escape}');

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should reset form to original values when cancelled after changes', async () => {
      const user = userEvent.setup();
      render(<JobEditModal {...defaultProps} />);

      // Make changes
      const priorityInput = screen.getByLabelText(/priority/i);
      await user.clear(priorityInput);
      await user.type(priorityInput, '9');

      // Cancel
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      // Reopen modal (this would happen in parent component)
      const { rerender } = render(<JobEditModal {...defaultProps} />);
      rerender(<JobEditModal {...defaultProps} isOpen={true} />);

      expect(screen.getByLabelText(/priority/i)).toHaveValue(5); // Original value
    });
  });

  describe('Running Job Restrictions', () => {
    it('should disable form fields for running job', () => {
      const runningJob = createMockJob('running');
      render(<JobEditModal {...defaultProps} job={runningJob} />);

      expect(screen.getByLabelText(/priority/i)).toBeDisabled();
      expect(screen.getByLabelText(/retry count/i)).toBeDisabled();
      expect(screen.getByLabelText(/job metadata/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /save changes/i })).toBeDisabled();
    });

    it('should show message for running job', () => {
      const runningJob = createMockJob('running');
      render(<JobEditModal {...defaultProps} job={runningJob} />);

      expect(screen.getByText(/cannot edit configuration of a running job/i)).toBeInTheDocument();
    });

    it('should allow editing for pending jobs', () => {
      const pendingJob = createMockJob('pending');
      render(<JobEditModal {...defaultProps} job={pendingJob} />);

      expect(screen.getByLabelText(/priority/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/retry count/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/job metadata/i)).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /save changes/i })).not.toBeDisabled();
    });

    it('should allow editing for failed jobs', () => {
      const failedJob = createMockJob('failed');
      render(<JobEditModal {...defaultProps} job={failedJob} />);

      expect(screen.getByLabelText(/priority/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/retry count/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/job metadata/i)).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /save changes/i })).not.toBeDisabled();
    });

    it('should allow editing for completed jobs', () => {
      const completedJob = createMockJob('completed');
      render(<JobEditModal {...defaultProps} job={completedJob} />);

      expect(screen.getByLabelText(/priority/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/retry count/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/job metadata/i)).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /save changes/i })).not.toBeDisabled();
    });
  });

  describe('Form Help Text', () => {
    it('should show help text for priority field', () => {
      render(<JobEditModal {...defaultProps} />);

      expect(screen.getByText(/higher values \(5-10\) get priority execution/i)).toBeInTheDocument();
    });

    it('should show help text for retry count field', () => {
      render(<JobEditModal {...defaultProps} />);

      expect(screen.getByText(/number of times to retry if job fails/i)).toBeInTheDocument();
    });

    it('should show help text for metadata field', () => {
      render(<JobEditModal {...defaultProps} />);

      expect(screen.getByText(/additional job configuration as json/i)).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle job without metadata', () => {
      const jobWithoutMetadata = createMockJob('pending');
      delete (jobWithoutMetadata as any).job_metadata;

      render(<JobEditModal {...defaultProps} job={jobWithoutMetadata} />);

      const metadataTextarea = screen.getByLabelText(/job metadata/i);
      expect(metadataTextarea).toHaveValue('');
    });

    it('should handle empty metadata object', () => {
      const jobWithEmptyMetadata = createMockJob('pending', { job_metadata: {} });
      render(<JobEditModal {...defaultProps} job={jobWithEmptyMetadata} />);

      const metadataTextarea = screen.getByLabelText(/job metadata/i);
      expect(metadataTextarea).toHaveValue('{}');
    });

    it('should handle null values in form fields', () => {
      const jobWithNulls = createMockJob('pending', {
        priority: 0,
        retry_count: 0
      });
      render(<JobEditModal {...defaultProps} job={jobWithNulls} />);

      expect(screen.getByLabelText(/priority/i)).toHaveValue(0);
      expect(screen.getByLabelText(/retry count/i)).toHaveValue(0);
    });
  });
});