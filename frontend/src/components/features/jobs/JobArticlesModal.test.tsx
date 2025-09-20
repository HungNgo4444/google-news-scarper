import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { JobArticlesModal } from './JobArticlesModal';
import { ArticlesService } from '../../../services/articlesService';
import type { JobResponse } from '../../../types/shared';
import type { ArticleResponse } from '../../../services/articlesService';

// Mock the ArticlesService
vi.mock('../../../services/articlesService', () => ({
  ArticlesService: {
    getArticles: vi.fn(),
    exportArticles: vi.fn()
  }
}));

// Mock the ArticleExport component
vi.mock('../../features/articles/ArticleExport', () => ({
  ArticleExport: ({ jobId, onExportComplete }: any) => (
    <div data-testid="article-export">
      <button onClick={() => onExportComplete('Export completed')}>
        Export Articles for job {jobId}
      </button>
    </div>
  )
}));

const mockArticlesService = vi.mocked(ArticlesService);

const createMockJob = (overrides?: Partial<JobResponse>): JobResponse => ({
  id: 'job-123',
  category_id: 'cat-1',
  category_name: 'Technology',
  status: 'completed',
  celery_task_id: 'task-123',
  priority: 1,
  correlation_id: 'corr-123',
  articles_found: 15,
  articles_saved: 12,
  error_message: null,
  retry_count: 0,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
  started_at: '2023-01-01T00:01:00Z',
  completed_at: '2023-01-01T00:02:00Z',
  duration_seconds: 60,
  success_rate: 0.8,
  ...overrides
});

const createMockArticle = (id: string, overrides?: Partial<ArticleResponse>): ArticleResponse => ({
  id,
  title: `Article ${id}`,
  content: `Content for article ${id}`,
  author: `Author ${id}`,
  publish_date: '2023-01-01T00:00:00Z',
  source_url: `https://example.com/article-${id}`,
  image_url: `https://example.com/image-${id}.jpg`,
  url_hash: `hash-${id}`,
  content_hash: `content-hash-${id}`,
  last_seen: '2023-01-01T00:00:00Z',
  crawl_job_id: 'job-123',
  keywords_matched: ['python', 'ai'],
  relevance_score: 0.85,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
  ...overrides
});

describe('JobArticlesModal', () => {
  const mockOnClose = vi.fn();
  const mockJob = createMockJob();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnClose.mockClear();
  });

  const defaultProps = {
    isOpen: true,
    onClose: mockOnClose,
    job: mockJob
  };

  describe('Modal Rendering', () => {
    it('should not render when isOpen is false', () => {
      render(<JobArticlesModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByText('Articles for Job')).not.toBeInTheDocument();
    });

    it('should render modal title with job information', async () => {
      const articles = [createMockArticle('1'), createMockArticle('2')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 2,
        page: 1,
        size: 10,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      expect(screen.getByText('Articles for Job')).toBeInTheDocument();
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('job-123')).toBeInTheDocument();
    });

    it('should show loading state initially', () => {
      mockArticlesService.getArticles.mockImplementation(() => new Promise(() => {}));

      render(<JobArticlesModal {...defaultProps} />);

      expect(screen.getByText('Loading articles...')).toBeInTheDocument();
    });

    it('should render close button', () => {
      render(<JobArticlesModal {...defaultProps} />);

      expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
    });
  });

  describe('Articles Loading', () => {
    it('should fetch articles for the job on mount', async () => {
      const articles = [createMockArticle('1'), createMockArticle('2')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 2,
        page: 1,
        size: 10,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      expect(mockArticlesService.getArticles).toHaveBeenCalledWith({
        job_id: 'job-123',
        page: 1,
        size: 20
      });

      await waitFor(() => {
        expect(screen.getByText('Article 1')).toBeInTheDocument();
        expect(screen.getByText('Article 2')).toBeInTheDocument();
      });
    });

    it('should display article count in header', async () => {
      const articles = [createMockArticle('1'), createMockArticle('2')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 15,
        page: 1,
        size: 10,
        pages: 2
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('(15 articles found)')).toBeInTheDocument();
      });
    });

    it('should handle API error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockArticlesService.getArticles.mockRejectedValue(new Error('Network error'));

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load articles')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Search Functionality', () => {
    it('should render search input', async () => {
      const articles = [createMockArticle('1')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 1,
        page: 1,
        size: 10,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search articles...')).toBeInTheDocument();
      });
    });

    it('should perform search when typing in search input', async () => {
      const user = userEvent.setup();
      const articles = [createMockArticle('1', { title: 'Python Tutorial' })];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 1,
        page: 1,
        size: 10,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search articles...')).toBeInTheDocument();
      });

      // Clear the mock to track the search call
      vi.clearAllMocks();

      const searchInput = screen.getByPlaceholderText('Search articles...');
      await user.type(searchInput, 'python');

      // Wait for debounced search
      await waitFor(() => {
        expect(mockArticlesService.getArticles).toHaveBeenCalledWith({
          job_id: 'job-123',
          search: 'python',
          page: 1,
          size: 20
        });
      }, { timeout: 2000 });
    });

    it('should clear search when input is cleared', async () => {
      const user = userEvent.setup();
      const articles = [createMockArticle('1')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 1,
        page: 1,
        size: 10,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search articles...')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search articles...');
      await user.type(searchInput, 'python');
      await user.clear(searchInput);

      await waitFor(() => {
        expect(mockArticlesService.getArticles).toHaveBeenLastCalledWith({
          job_id: 'job-123',
          page: 1,
          size: 20
        });
      });
    });
  });

  describe('Pagination', () => {
    it('should show pagination when there are multiple pages', async () => {
      const articles = Array.from({ length: 20 }, (_, i) => createMockArticle((i + 1).toString()));
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 50,
        page: 1,
        size: 20,
        pages: 3
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      });
    });

    it('should disable Previous button on first page', async () => {
      const articles = [createMockArticle('1')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 50,
        page: 1,
        size: 20,
        pages: 3
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
      });
    });

    it('should load next page when Next button is clicked', async () => {
      const user = userEvent.setup();
      const articles = Array.from({ length: 20 }, (_, i) => createMockArticle((i + 1).toString()));

      // First call (initial load)
      mockArticlesService.getArticles.mockResolvedValueOnce({
        articles,
        total: 50,
        page: 1,
        size: 20,
        pages: 3
      });

      // Second call (next page)
      const nextPageArticles = Array.from({ length: 20 }, (_, i) => createMockArticle((i + 21).toString()));
      mockArticlesService.getArticles.mockResolvedValueOnce({
        articles: nextPageArticles,
        total: 50,
        page: 2,
        size: 20,
        pages: 3
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();
        expect(mockArticlesService.getArticles).toHaveBeenCalledWith({
          job_id: 'job-123',
          page: 2,
          size: 20
        });
      });
    });
  });

  describe('Article Display', () => {
    it('should display article information correctly', async () => {
      const article = createMockArticle('1', {
        title: 'Python Machine Learning Tutorial',
        author: 'John Doe',
        publish_date: '2023-01-01T12:00:00Z',
        keywords_matched: ['python', 'machine learning'],
        relevance_score: 0.92
      });

      mockArticlesService.getArticles.mockResolvedValue({
        articles: [article],
        total: 1,
        page: 1,
        size: 20,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Python Machine Learning Tutorial')).toBeInTheDocument();
        expect(screen.getByText('By John Doe')).toBeInTheDocument();
        expect(screen.getByText(/Keywords: python, machine learning/)).toBeInTheDocument();
        expect(screen.getByText(/Relevance: 92%/)).toBeInTheDocument();
      });
    });

    it('should show message when no articles found', async () => {
      mockArticlesService.getArticles.mockResolvedValue({
        articles: [],
        total: 0,
        page: 1,
        size: 20,
        pages: 0
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('No articles found for this job')).toBeInTheDocument();
      });
    });

    it('should make article titles clickable links', async () => {
      const article = createMockArticle('1', {
        title: 'Test Article',
        source_url: 'https://example.com/article-1'
      });

      mockArticlesService.getArticles.mockResolvedValue({
        articles: [article],
        total: 1,
        page: 1,
        size: 20,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        const articleLink = screen.getByRole('link', { name: 'Test Article' });
        expect(articleLink).toBeInTheDocument();
        expect(articleLink).toHaveAttribute('href', 'https://example.com/article-1');
        expect(articleLink).toHaveAttribute('target', '_blank');
      });
    });

    it('should truncate long article content', async () => {
      const longContent = 'This is a very long article content that should be truncated after a certain number of characters to prevent the modal from becoming too large and unwieldy for users to read and navigate effectively.';
      const article = createMockArticle('1', {
        title: 'Long Article',
        content: longContent
      });

      mockArticlesService.getArticles.mockResolvedValue({
        articles: [article],
        total: 1,
        page: 1,
        size: 20,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        const content = screen.getByText(/This is a very long article content/);
        expect(content.textContent?.length).toBeLessThan(longContent.length);
        expect(content.textContent).toMatch(/\.{3}$/); // Should end with ellipsis
      });
    });
  });

  describe('Export Functionality', () => {
    it('should render export component', async () => {
      const articles = [createMockArticle('1')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 1,
        page: 1,
        size: 20,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('article-export')).toBeInTheDocument();
        expect(screen.getByText('Export Articles for job job-123')).toBeInTheDocument();
      });
    });

    it('should show export success message', async () => {
      const user = userEvent.setup();
      const articles = [createMockArticle('1')];
      mockArticlesService.getArticles.mockResolvedValue({
        articles,
        total: 1,
        page: 1,
        size: 20,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('article-export')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /export articles/i });
      await user.click(exportButton);

      expect(screen.getByText('Export completed')).toBeInTheDocument();
    });
  });

  describe('Modal Interactions', () => {
    it('should call onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      render(<JobArticlesModal {...defaultProps} />);

      const closeButton = screen.getByLabelText('Close modal');
      await user.click(closeButton);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should call onClose when clicking outside modal', async () => {
      const user = userEvent.setup();
      render(<JobArticlesModal {...defaultProps} />);

      // Click on the overlay (outside the modal)
      const overlay = screen.getByRole('dialog').parentElement;
      await user.click(overlay!);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should call onClose when pressing Escape key', async () => {
      const user = userEvent.setup();
      render(<JobArticlesModal {...defaultProps} />);

      await user.keyboard('{Escape}');

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should retry loading articles when retry button is clicked', async () => {
      const user = userEvent.setup();
      mockArticlesService.getArticles
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          articles: [createMockArticle('1')],
          total: 1,
          page: 1,
          size: 20,
          pages: 1
        });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load articles')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText('Article 1')).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle job without articles_found property', async () => {
      const jobWithoutArticles = createMockJob({ articles_found: 0 });
      mockArticlesService.getArticles.mockResolvedValue({
        articles: [],
        total: 0,
        page: 1,
        size: 20,
        pages: 0
      });

      render(<JobArticlesModal {...defaultProps} job={jobWithoutArticles} />);

      await waitFor(() => {
        expect(screen.getByText('No articles found for this job')).toBeInTheDocument();
      });
    });

    it('should handle articles without some optional fields', async () => {
      const articleWithMissingFields = createMockArticle('1', {
        author: null,
        content: null,
        image_url: null,
        keywords_matched: []
      });

      mockArticlesService.getArticles.mockResolvedValue({
        articles: [articleWithMissingFields],
        total: 1,
        page: 1,
        size: 20,
        pages: 1
      });

      render(<JobArticlesModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Article 1')).toBeInTheDocument();
        expect(screen.getByText('By Unknown Author')).toBeInTheDocument();
      });
    });
  });
});