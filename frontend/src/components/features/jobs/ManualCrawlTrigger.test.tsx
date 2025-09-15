import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ManualCrawlTrigger } from './ManualCrawlTrigger';
import { CategoriesService } from '../../../services/categoriesService';
import { JobsService } from '../../../services/jobsService';
import type { Category, JobResponse } from '../../../types/shared';

// Mock the services
vi.mock('../../../services/categoriesService', () => ({
  CategoriesService: {
    getCategories: vi.fn()
  }
}));

vi.mock('../../../services/jobsService', () => ({
  JobsService: {
    createJob: vi.fn()
  }
}));

const mockCategoriesService = vi.mocked(CategoriesService);
const mockJobsService = vi.mocked(JobsService);

const mockCategories: Category[] = [
  {
    id: 'cat-1',
    name: 'Technology',
    keywords: ['AI', 'tech'],
    exclude_keywords: ['spam'],
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  },
  {
    id: 'cat-2',
    name: 'Sports',
    keywords: ['football', 'basketball'],
    exclude_keywords: [],
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  }
];

const mockJobResponse: JobResponse = {
  id: 'job-123',
  category_id: 'cat-1',
  category_name: 'Technology',
  status: 'pending',
  celery_task_id: 'task-123',
  priority: 1,
  correlation_id: 'corr-123',
  created_at: '2023-01-01T00:00:00Z',
  started_at: null,
  completed_at: null
};

describe('ManualCrawlTrigger', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render and load categories on mount', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);

    render(<ManualCrawlTrigger />);

    expect(screen.getByText('Manual Crawl Job Trigger')).toBeInTheDocument();

    await waitFor(() => {
      expect(mockCategoriesService.getCategories).toHaveBeenCalledWith(true);
      expect(screen.getByDisplayValue('Choose a category to crawl...')).toBeInTheDocument();
    });
  });

  it('should display loading state initially', () => {
    mockCategoriesService.getCategories.mockImplementation(() => new Promise(() => {}));

    render(<ManualCrawlTrigger />);

    expect(screen.getByText('Loading categories...')).toBeInTheDocument();
  });

  it('should display categories in dropdown when loaded', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);

    render(<ManualCrawlTrigger />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select Category *');
      expect(select).toBeInTheDocument();

      // Check for the category options using text content matching
      expect(screen.getByText((_, element) => {
        return element?.textContent === 'Technology (2 keywords)';
      })).toBeInTheDocument();

      expect(screen.getByText((_, element) => {
        return element?.textContent === 'Sports (2 keywords)';
      })).toBeInTheDocument();
    });
  });

  it('should handle category selection and enable trigger button', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);

    render(<ManualCrawlTrigger />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select Category *');
      fireEvent.change(select, { target: { value: 'cat-1' } });
    });

    await waitFor(() => {
      const triggerButton = screen.getByText('Start Crawl Job');
      expect(triggerButton).not.toBeDisabled();
    });
  });

  it('should disable trigger button when no category selected', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);

    render(<ManualCrawlTrigger />);

    // Wait for categories to load
    await waitFor(() => {
      const triggerButton = screen.getByText('Start Crawl Job');
      expect(triggerButton).toBeDisabled();
    });
  });

  it('should show confirmation dialog when trigger clicked with category selected', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);

    render(<ManualCrawlTrigger />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select Category *');
      fireEvent.change(select, { target: { value: 'cat-1' } });
    });

    const triggerButton = screen.getByText('Start Crawl Job');
    fireEvent.click(triggerButton);

    await waitFor(() => {
      expect(screen.getByText('Confirm Crawl Job')).toBeInTheDocument();
      expect(screen.getByText(/Are you sure you want to start a crawl job for category "Technology"/)).toBeInTheDocument();
    });
  });

  it('should cancel confirmation dialog', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);

    render(<ManualCrawlTrigger />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select Category *');
      fireEvent.change(select, { target: { value: 'cat-1' } });
    });

    const triggerButton = screen.getByText('Start Crawl Job');
    fireEvent.click(triggerButton);

    await waitFor(() => {
      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);
    });

    await waitFor(() => {
      expect(screen.queryByText('Confirm Crawl Job')).not.toBeInTheDocument();
    });
  });

  it('should trigger job creation and show success message', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.createJob.mockResolvedValue(mockJobResponse);
    const onJobTriggered = vi.fn();

    render(<ManualCrawlTrigger onJobTriggered={onJobTriggered} />);

    // Select category
    await waitFor(() => {
      const select = screen.getByLabelText('Select Category *');
      fireEvent.change(select, { target: { value: 'cat-1' } });
    });

    // Click trigger button
    const triggerButton = screen.getByText('Start Crawl Job');
    fireEvent.click(triggerButton);

    // Confirm in dialog
    await waitFor(() => {
      const confirmButton = screen.getByText('Start Job');
      fireEvent.click(confirmButton);
    });

    // Verify job creation and success
    await waitFor(() => {
      expect(mockJobsService.createJob).toHaveBeenCalledWith({
        category_id: 'cat-1',
        priority: 1
      });
      expect(screen.getByText(/Crawl job started successfully for "Technology" \(Job ID: job-123\)/)).toBeInTheDocument();
      expect(onJobTriggered).toHaveBeenCalledWith(mockJobResponse);
    });
  });

  it('should handle job creation errors', async () => {
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
    mockJobsService.createJob.mockRejectedValue(new Error('HTTP 400: Bad Request'));

    render(<ManualCrawlTrigger />);

    // Select category and trigger
    await waitFor(() => {
      const select = screen.getByLabelText('Select Category *');
      fireEvent.change(select, { target: { value: 'cat-1' } });
    });

    const triggerButton = screen.getByText('Start Crawl Job');
    fireEvent.click(triggerButton);

    await waitFor(() => {
      const confirmButton = screen.getByText('Start Job');
      fireEvent.click(confirmButton);
    });

    await waitFor(() => {
      expect(screen.getByText('Invalid category or category is not active.')).toBeInTheDocument();
    });
  });

  it('should handle categories loading error', async () => {
    mockCategoriesService.getCategories.mockRejectedValue(new Error('Network error'));

    render(<ManualCrawlTrigger />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load categories. Please try again.')).toBeInTheDocument();
    });
  });

  it('should show message when no active categories available', async () => {
    mockCategoriesService.getCategories.mockResolvedValue([]);

    render(<ManualCrawlTrigger />);

    await waitFor(() => {
      expect(screen.getByText('No active categories available. Please create and activate a category first.')).toBeInTheDocument();
    });
  });
});