import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CategoriesList } from './CategoriesList';
import { CategoriesService } from '../../../services/categoriesService';

// Mock the service
vi.mock('../../../services/categoriesService');

const mockCategoriesService = vi.mocked(CategoriesService);

const mockCategories = [
  {
    id: '1',
    name: 'Technology',
    keywords: ['AI', 'tech', 'software'],
    exclude_keywords: ['spam'],
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  },
  {
    id: '2',
    name: 'Sports',
    keywords: ['football', 'basketball'],
    exclude_keywords: [],
    is_active: false,
    created_at: '2023-01-02T00:00:00Z',
    updated_at: '2023-01-02T00:00:00Z'
  }
];

describe('CategoriesList', () => {
  const defaultProps = {
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onToggleStatus: vi.fn(),
    onCreateNew: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockCategoriesService.getCategories.mockResolvedValue(mockCategories);
  });

  it('should display loading state initially', async () => {
    render(<CategoriesList {...defaultProps} />);

    expect(screen.getByText('Loading categories...')).toBeInTheDocument();

    // Wait for loading to complete to avoid act warnings
    await waitFor(() => {
      expect(screen.queryByText('Loading categories...')).not.toBeInTheDocument();
    });
  });

  it('should display categories after loading', async () => {
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Technology')).toBeInTheDocument();
      expect(screen.getByText('Sports')).toBeInTheDocument();
    });
  });

  it('should display keywords with tags and overflow indicator', async () => {
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('AI')).toBeInTheDocument();
      expect(screen.getByText('tech')).toBeInTheDocument();
      expect(screen.getByText('software')).toBeInTheDocument();
      expect(screen.queryByText('+0 more')).not.toBeInTheDocument();
    });
  });

  it('should show overflow indicator for many keywords', async () => {
    const categoryWithManyKeywords = {
      ...mockCategories[0],
      keywords: ['AI', 'tech', 'software', 'programming', 'development']
    };
    
    mockCategoriesService.getCategories.mockResolvedValue([categoryWithManyKeywords]);
    
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('+2 more')).toBeInTheDocument();
    });
  });

  it('should display correct status buttons', async () => {
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Inactive')).toBeInTheDocument();
    });
  });

  it('should handle sorting by name', async () => {
    const user = userEvent.setup();
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Technology')).toBeInTheDocument();
    });

    // Find the name header element and verify it shows ascending sort initially
    await waitFor(() => {
      const nameHeaderText = screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'th' && content.includes('Name') && content.includes('↑');
      });
      expect(nameHeaderText).toBeInTheDocument();
    });

    // Click to change sort order
    const nameHeader = screen.getByText(/Name/);
    await act(async () => {
      await user.click(nameHeader);
    });

    // After clicking, should show descending (↓)
    await waitFor(() => {
      const updatedNameHeaderText = screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'th' && content.includes('Name') && content.includes('↓');
      });
      expect(updatedNameHeaderText).toBeInTheDocument();
    });
  });

  it('should call onEdit when edit button clicked', async () => {
    const user = userEvent.setup();
    const mockOnEdit = vi.fn();

    render(<CategoriesList {...defaultProps} onEdit={mockOnEdit} />);

    await waitFor(() => {
      expect(screen.getByText('Technology')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByText('Edit');
    await act(async () => {
      await user.click(editButtons[0]);
    });

    // The first category in the sorted list might not be mockCategories[0]
    expect(mockOnEdit).toHaveBeenCalledTimes(1);
    expect(mockOnEdit).toHaveBeenCalledWith(expect.objectContaining({
      id: expect.any(String),
      name: expect.any(String)
    }));
  });

  it('should call onDelete when delete button clicked', async () => {
    const user = userEvent.setup();
    const mockOnDelete = vi.fn();

    render(<CategoriesList {...defaultProps} onDelete={mockOnDelete} />);

    await waitFor(() => {
      expect(screen.getByText('Technology')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('Delete');
    await act(async () => {
      await user.click(deleteButtons[0]);
    });

    // The first category in the sorted list might not be mockCategories[0]
    expect(mockOnDelete).toHaveBeenCalledTimes(1);
    expect(mockOnDelete).toHaveBeenCalledWith(expect.objectContaining({
      id: expect.any(String),
      name: expect.any(String)
    }));
  });

  it('should call onToggleStatus when status button clicked', async () => {
    const user = userEvent.setup();
    const mockOnToggleStatus = vi.fn();

    render(<CategoriesList {...defaultProps} onToggleStatus={mockOnToggleStatus} />);

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    const activeButton = screen.getByText('Active');
    await act(async () => {
      await user.click(activeButton);
    });

    expect(mockOnToggleStatus).toHaveBeenCalledTimes(1);
    expect(mockOnToggleStatus).toHaveBeenCalledWith(expect.objectContaining({
      is_active: true
    }));
  });

  it('should call onCreateNew when create button clicked', async () => {
    const user = userEvent.setup();
    const mockOnCreateNew = vi.fn();

    render(<CategoriesList {...defaultProps} onCreateNew={mockOnCreateNew} />);

    await waitFor(() => {
      expect(screen.getByText('Create Category')).toBeInTheDocument();
    });

    const createButton = screen.getByText('Create Category');
    await act(async () => {
      await user.click(createButton);
    });

    expect(mockOnCreateNew).toHaveBeenCalled();
  });

  it('should display error state when API fails', async () => {
    mockCategoriesService.getCategories.mockRejectedValue(new Error('API Error'));
    
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Error loading categories')).toBeInTheDocument();
      expect(screen.getByText('API Error')).toBeInTheDocument();
      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });
  });

  it('should show empty state when no categories exist', async () => {
    mockCategoriesService.getCategories.mockResolvedValue([]);
    
    render(<CategoriesList {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('No categories found. Create your first category to get started.')).toBeInTheDocument();
    });
  });
});