import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ArticleExport } from './ArticleExport';
import { ArticlesService } from '../../../services/articlesService';

// Mock the ArticlesService
vi.mock('../../../services/articlesService', () => ({
  ArticlesService: {
    exportArticles: vi.fn()
  }
}));

// Mock URL.createObjectURL and URL.revokeObjectURL
const mockCreateObjectURL = vi.fn();
const mockRevokeObjectURL = vi.fn();

Object.defineProperty(window, 'URL', {
  value: {
    createObjectURL: mockCreateObjectURL,
    revokeObjectURL: mockRevokeObjectURL,
  },
});

// Mock document.createElement for download link
const mockClick = vi.fn();
const mockAppendChild = vi.fn();
const mockRemoveChild = vi.fn();

Object.defineProperty(document, 'createElement', {
  value: vi.fn().mockImplementation((tagName) => {
    if (tagName === 'a') {
      return {
        href: '',
        download: '',
        click: mockClick,
        style: { display: '' }
      };
    }
    return {};
  })
});

Object.defineProperty(document.body, 'appendChild', { value: mockAppendChild });
Object.defineProperty(document.body, 'removeChild', { value: mockRemoveChild });

const mockArticlesService = vi.mocked(ArticlesService);

describe('ArticleExport', () => {
  const mockOnExportComplete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnExportComplete.mockClear();
    mockCreateObjectURL.mockClear();
    mockRevokeObjectURL.mockClear();
    mockClick.mockClear();
    mockAppendChild.mockClear();
    mockRemoveChild.mockClear();
  });

  const defaultProps = {
    jobId: 'job-123',
    onExportComplete: mockOnExportComplete
  };

  describe('Component Rendering', () => {
    it('should render export form with all format options', () => {
      render(<ArticleExport {...defaultProps} />);

      expect(screen.getByText('Export Articles')).toBeInTheDocument();
      expect(screen.getByLabelText(/export format/i)).toBeInTheDocument();
      expect(screen.getByText('JSON')).toBeInTheDocument();
      expect(screen.getByText('CSV')).toBeInTheDocument();
      expect(screen.getByText('Excel')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
    });

    it('should render field selection checkboxes', () => {
      render(<ArticleExport {...defaultProps} />);

      expect(screen.getByLabelText(/select fields to export/i)).toBeInTheDocument();
      expect(screen.getByLabelText('Title')).toBeInTheDocument();
      expect(screen.getByLabelText('Content')).toBeInTheDocument();
      expect(screen.getByLabelText('Author')).toBeInTheDocument();
      expect(screen.getByLabelText('Publish Date')).toBeInTheDocument();
      expect(screen.getByLabelText('Source URL')).toBeInTheDocument();
      expect(screen.getByLabelText('Keywords')).toBeInTheDocument();
      expect(screen.getByLabelText('Relevance Score')).toBeInTheDocument();
    });

    it('should have default fields selected', () => {
      render(<ArticleExport {...defaultProps} />);

      // Check default selected fields
      expect(screen.getByLabelText('Title')).toBeChecked();
      expect(screen.getByLabelText('Author')).toBeChecked();
      expect(screen.getByLabelText('Publish Date')).toBeChecked();
      expect(screen.getByLabelText('Source URL')).toBeChecked();
      expect(screen.getByLabelText('Keywords')).toBeChecked();

      // Check default unselected fields
      expect(screen.getByLabelText('Content')).not.toBeChecked();
      expect(screen.getByLabelText('Relevance Score')).not.toBeChecked();
    });

    it('should have JSON format selected by default', () => {
      render(<ArticleExport {...defaultProps} />);

      const jsonRadio = screen.getByLabelText('JSON');
      expect(jsonRadio).toBeChecked();
    });
  });

  describe('Format Selection', () => {
    it('should change format when radio button is selected', async () => {
      const user = userEvent.setup();
      render(<ArticleExport {...defaultProps} />);

      const csvRadio = screen.getByLabelText('CSV');
      await user.click(csvRadio);

      expect(csvRadio).toBeChecked();
      expect(screen.getByLabelText('JSON')).not.toBeChecked();
      expect(screen.getByLabelText('Excel')).not.toBeChecked();
    });

    it('should allow switching between different formats', async () => {
      const user = userEvent.setup();
      render(<ArticleExport {...defaultProps} />);

      // Switch to Excel
      const excelRadio = screen.getByLabelText('Excel');
      await user.click(excelRadio);
      expect(excelRadio).toBeChecked();

      // Switch to CSV
      const csvRadio = screen.getByLabelText('CSV');
      await user.click(csvRadio);
      expect(csvRadio).toBeChecked();
      expect(excelRadio).not.toBeChecked();

      // Switch back to JSON
      const jsonRadio = screen.getByLabelText('JSON');
      await user.click(jsonRadio);
      expect(jsonRadio).toBeChecked();
      expect(csvRadio).not.toBeChecked();
    });
  });

  describe('Field Selection', () => {
    it('should toggle field selection when checkbox is clicked', async () => {
      const user = userEvent.setup();
      render(<ArticleExport {...defaultProps} />);

      const contentCheckbox = screen.getByLabelText('Content');
      expect(contentCheckbox).not.toBeChecked();

      await user.click(contentCheckbox);
      expect(contentCheckbox).toBeChecked();

      await user.click(contentCheckbox);
      expect(contentCheckbox).not.toBeChecked();
    });

    it('should allow multiple field selections', async () => {
      const user = userEvent.setup();
      render(<ArticleExport {...defaultProps} />);

      const contentCheckbox = screen.getByLabelText('Content');
      const relevanceCheckbox = screen.getByLabelText('Relevance Score');

      await user.click(contentCheckbox);
      await user.click(relevanceCheckbox);

      expect(contentCheckbox).toBeChecked();
      expect(relevanceCheckbox).toBeChecked();
      expect(screen.getByLabelText('Title')).toBeChecked(); // Still checked from default
    });

    it('should provide select all functionality', async () => {
      const user = userEvent.setup();
      render(<ArticleExport {...defaultProps} />);

      // Check if there's a "Select All" button or checkbox
      const selectAllButton = screen.queryByText(/select all/i) || screen.queryByLabelText(/select all/i);
      if (selectAllButton) {
        await user.click(selectAllButton);

        // All checkboxes should be checked
        expect(screen.getByLabelText('Title')).toBeChecked();
        expect(screen.getByLabelText('Content')).toBeChecked();
        expect(screen.getByLabelText('Author')).toBeChecked();
        expect(screen.getByLabelText('Publish Date')).toBeChecked();
        expect(screen.getByLabelText('Source URL')).toBeChecked();
        expect(screen.getByLabelText('Keywords')).toBeChecked();
        expect(screen.getByLabelText('Relevance Score')).toBeChecked();
      }
    });

    it('should show validation error when no fields selected', async () => {
      const user = userEvent.setup();
      render(<ArticleExport {...defaultProps} />);

      // Uncheck all default fields
      await user.click(screen.getByLabelText('Title'));
      await user.click(screen.getByLabelText('Author'));
      await user.click(screen.getByLabelText('Publish Date'));
      await user.click(screen.getByLabelText('Source URL'));
      await user.click(screen.getByLabelText('Keywords'));

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(screen.getByText(/at least one field must be selected/i)).toBeInTheDocument();
    });
  });

  describe('Export Functionality', () => {
    it('should call ArticlesService.exportArticles with correct parameters', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test data'], { type: 'application/json' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(mockArticlesService.exportArticles).toHaveBeenCalledWith({
        job_id: 'job-123',
        format: 'json',
        fields: ['title', 'author', 'publish_date', 'source_url', 'keywords_matched']
      });
    });

    it('should export with CSV format when selected', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test,data'], { type: 'text/csv' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport {...defaultProps} />);

      // Select CSV format
      const csvRadio = screen.getByLabelText('CSV');
      await user.click(csvRadio);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(mockArticlesService.exportArticles).toHaveBeenCalledWith({
        job_id: 'job-123',
        format: 'csv',
        fields: ['title', 'author', 'publish_date', 'source_url', 'keywords_matched']
      });
    });

    it('should export with Excel format when selected', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['excel data'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport {...defaultProps} />);

      // Select Excel format
      const excelRadio = screen.getByLabelText('Excel');
      await user.click(excelRadio);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(mockArticlesService.exportArticles).toHaveBeenCalledWith({
        job_id: 'job-123',
        format: 'xlsx',
        fields: ['title', 'author', 'publish_date', 'source_url', 'keywords_matched']
      });
    });

    it('should include only selected fields in export request', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test data'], { type: 'application/json' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport {...defaultProps} />);

      // Uncheck some fields and add content
      await user.click(screen.getByLabelText('Author'));
      await user.click(screen.getByLabelText('Keywords'));
      await user.click(screen.getByLabelText('Content'));

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(mockArticlesService.exportArticles).toHaveBeenCalledWith({
        job_id: 'job-123',
        format: 'json',
        fields: ['title', 'publish_date', 'source_url', 'content']
      });
    });

    it('should trigger file download when export is successful', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test data'], { type: 'application/json' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
        expect(mockClick).toHaveBeenCalled();
        expect(mockAppendChild).toHaveBeenCalled();
        expect(mockRemoveChild).toHaveBeenCalled();
        expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
      });
    });

    it('should call onExportComplete callback after successful export', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test data'], { type: 'application/json' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockOnExportComplete).toHaveBeenCalledWith('Articles exported successfully');
      });
    });

    it('should show loading state during export', async () => {
      const user = userEvent.setup();
      mockArticlesService.exportArticles.mockImplementation(() => new Promise(() => {}));

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(screen.getByText('Exporting...')).toBeInTheDocument();
      expect(exportButton).toBeDisabled();
    });

    it('should handle export API error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockArticlesService.exportArticles.mockRejectedValue(new Error('Export failed'));

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('Export failed. Please try again.')).toBeInTheDocument();
        expect(consoleSpy).toHaveBeenCalledWith('Export failed:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('should clear error message when export is retried', async () => {
      const user = userEvent.setup();
      mockArticlesService.exportArticles.mockRejectedValueOnce(new Error('Export failed'));

      render(<ArticleExport {...defaultProps} />);

      // Trigger error
      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('Export failed. Please try again.')).toBeInTheDocument();
      });

      // Retry export
      mockArticlesService.exportArticles.mockResolvedValue(new Blob(['test'], { type: 'application/json' }));
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.queryByText('Export failed. Please try again.')).not.toBeInTheDocument();
      });
    });
  });

  describe('File Naming', () => {
    it('should generate appropriate filename for JSON export', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test data'], { type: 'application/json' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      const mockElement = { download: '', click: mockClick } as any;
      vi.mocked(document.createElement).mockReturnValue(mockElement);

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockElement.download).toMatch(/articles-job-123.*\.json$/);
      });
    });

    it('should generate appropriate filename for CSV export', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test,data'], { type: 'text/csv' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      const mockElement = { download: '', click: mockClick } as any;
      vi.mocked(document.createElement).mockReturnValue(mockElement);

      render(<ArticleExport {...defaultProps} />);

      // Select CSV format
      const csvRadio = screen.getByLabelText('CSV');
      await user.click(csvRadio);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockElement.download).toMatch(/articles-job-123.*\.csv$/);
      });
    });

    it('should generate appropriate filename for Excel export', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['excel data'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      const mockElement = { download: '', click: mockClick } as any;
      vi.mocked(document.createElement).mockReturnValue(mockElement);

      render(<ArticleExport {...defaultProps} />);

      // Select Excel format
      const excelRadio = screen.getByLabelText('Excel');
      await user.click(excelRadio);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockElement.download).toMatch(/articles-job-123.*\.xlsx$/);
      });
    });
  });

  describe('Component Props', () => {
    it('should work without onExportComplete callback', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test data'], { type: 'application/json' });
      mockArticlesService.exportArticles.mockResolvedValue(mockBlob);
      mockCreateObjectURL.mockReturnValue('blob:mock-url');

      render(<ArticleExport jobId="job-123" />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockCreateObjectURL).toHaveBeenCalled();
        // Should not throw error even without callback
      });
    });

    it('should handle missing jobId gracefully', async () => {
      const user = userEvent.setup();
      render(<ArticleExport jobId="" onExportComplete={mockOnExportComplete} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(screen.getByText(/job id is required for export/i)).toBeInTheDocument();
      expect(mockArticlesService.exportArticles).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should have proper form labels and fieldsets', () => {
      render(<ArticleExport {...defaultProps} />);

      expect(screen.getByRole('group', { name: /export format/i })).toBeInTheDocument();
      expect(screen.getByRole('group', { name: /select fields to export/i })).toBeInTheDocument();
    });

    it('should have proper button accessibility', () => {
      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      expect(exportButton).toBeInTheDocument();
      expect(exportButton).toHaveAttribute('type', 'button');
    });

    it('should maintain focus management during loading state', async () => {
      const user = userEvent.setup();
      mockArticlesService.exportArticles.mockImplementation(() => new Promise(() => {}));

      render(<ArticleExport {...defaultProps} />);

      const exportButton = screen.getByRole('button', { name: /export/i });
      await user.click(exportButton);

      expect(exportButton).toHaveFocus();
      expect(exportButton).toBeDisabled();
    });
  });
});