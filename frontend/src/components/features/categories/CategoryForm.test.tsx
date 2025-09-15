import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CategoryForm } from './CategoryForm';

const mockCategory = {
  id: '1',
  name: 'Technology',
  keywords: ['AI', 'tech'],
  exclude_keywords: ['spam'],
  is_active: true,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z'
};

describe('CategoryForm', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSubmit: vi.fn(),
    title: 'Test Form'
  };

  it('should render form when open', () => {
    render(<CategoryForm {...defaultProps} />);

    expect(screen.getByText('Test Form')).toBeInTheDocument();
    expect(screen.getByLabelText(/Category Name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Keywords \*/)).toBeInTheDocument(); // More specific match
    expect(screen.getByLabelText(/Exclude Keywords/)).toBeInTheDocument();
  });

  it('should not render when closed', () => {
    render(<CategoryForm {...defaultProps} isOpen={false} />);
    
    expect(screen.queryByText('Test Form')).not.toBeInTheDocument();
  });

  it('should populate form with initial data', () => {
    render(
      <CategoryForm 
        {...defaultProps} 
        initialData={mockCategory}
      />
    );

    expect(screen.getByDisplayValue('Technology')).toBeInTheDocument();
    expect(screen.getByDisplayValue('AI, tech')).toBeInTheDocument();
    expect(screen.getByDisplayValue('spam')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { checked: true })).toBeInTheDocument();
  });

  it('should validate required fields', async () => {
    const user = userEvent.setup();
    render(<CategoryForm {...defaultProps} />);

    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Category name is required')).toBeInTheDocument();
      expect(screen.getByText('At least one keyword is required')).toBeInTheDocument();
    });
  });

  it('should validate name length', async () => {
    const user = userEvent.setup();
    render(<CategoryForm {...defaultProps} />);

    const nameInput = screen.getByLabelText(/Category Name/);
    await user.type(nameInput, 'A');
    
    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Category name must be at least 2 characters')).toBeInTheDocument();
    });
  });

  it('should parse keywords correctly', async () => {
    const user = userEvent.setup();
    const mockOnSubmit = vi.fn().mockResolvedValue(undefined);
    
    render(
      <CategoryForm 
        {...defaultProps} 
        onSubmit={mockOnSubmit}
      />
    );

    await user.type(screen.getByLabelText(/Category Name/), 'Test Category');
    await user.type(screen.getByLabelText(/Keywords \*/), 'AI, machine learning,  technology ');
    
    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: 'Test Category',
        keywords: ['AI', 'machine learning', 'technology'],
        exclude_keywords: [],
        is_active: true
      });
    });
  });

  it('should remove duplicate keywords', async () => {
    const user = userEvent.setup();
    const mockOnSubmit = vi.fn().mockResolvedValue(undefined);
    
    render(
      <CategoryForm 
        {...defaultProps} 
        onSubmit={mockOnSubmit}
      />
    );

    await user.type(screen.getByLabelText(/Category Name/), 'Test');
    await user.type(screen.getByLabelText(/Keywords \*/), 'AI, tech, AI, technology, tech');
    
    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: 'Test',
        keywords: ['AI', 'tech', 'technology'],
        exclude_keywords: [],
        is_active: true
      });
    });
  });

  it('should handle form submission errors', async () => {
    const user = userEvent.setup();
    const mockOnSubmit = vi.fn().mockRejectedValue(new Error('409: Category already exists'));
    
    render(
      <CategoryForm 
        {...defaultProps} 
        onSubmit={mockOnSubmit}
      />
    );

    await user.type(screen.getByLabelText(/Category Name/), 'Existing Category');
    await user.type(screen.getByLabelText(/Keywords \*/), 'test');
    
    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('A category with this name already exists')).toBeInTheDocument();
    });
  });

  it('should call onClose when cancel button clicked', async () => {
    const user = userEvent.setup();
    const mockOnClose = vi.fn();
    
    render(
      <CategoryForm 
        {...defaultProps} 
        onClose={mockOnClose}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });
});