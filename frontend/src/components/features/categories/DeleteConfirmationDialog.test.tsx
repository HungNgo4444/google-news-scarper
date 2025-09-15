import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeleteConfirmationDialog } from './DeleteConfirmationDialog';

const mockCategory = {
  id: '1',
  name: 'Technology',
  keywords: ['AI', 'tech', 'software', 'programming'],
  exclude_keywords: ['spam'],
  is_active: true,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z'
};

describe('DeleteConfirmationDialog', () => {
  const defaultProps = {
    isOpen: true,
    category: mockCategory,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    isDeleting: false
  };

  it('should render dialog when open with category', () => {
    render(<DeleteConfirmationDialog {...defaultProps} />);
    
    expect(screen.getByRole('heading', { name: 'Delete Category' })).toBeInTheDocument();
    expect(screen.getByText(/Are you sure you want to delete the category/)).toBeInTheDocument();
    expect(screen.getByText('Technology')).toBeInTheDocument();
    expect(screen.getByText(/Warning:/)).toBeInTheDocument();
  });

  it('should not render when closed', () => {
    render(<DeleteConfirmationDialog {...defaultProps} isOpen={false} />);
    
    expect(screen.queryByRole('heading', { name: 'Delete Category' })).not.toBeInTheDocument();
  });

  it('should not render when category is null', () => {
    render(<DeleteConfirmationDialog {...defaultProps} category={null} />);
    
    expect(screen.queryByRole('heading', { name: 'Delete Category' })).not.toBeInTheDocument();
  });

  it('should show keyword information when category has keywords', () => {
    render(<DeleteConfirmationDialog {...defaultProps} />);
    
    expect(screen.getByText(/This will also remove all associated crawling configurations/)).toBeInTheDocument();
    expect(screen.getByText(/AI, tech, software and 1 more/)).toBeInTheDocument();
  });

  it('should not show keyword warning for category with no keywords', () => {
    const categoryWithoutKeywords = {
      ...mockCategory,
      keywords: []
    };
    
    render(
      <DeleteConfirmationDialog 
        {...defaultProps} 
        category={categoryWithoutKeywords} 
      />
    );
    
    expect(screen.queryByText(/This will also remove all associated crawling configurations/)).not.toBeInTheDocument();
  });

  it('should show correct keyword count for categories with few keywords', () => {
    const categoryWithFewKeywords = {
      ...mockCategory,
      keywords: ['AI', 'tech']
    };
    
    render(
      <DeleteConfirmationDialog 
        {...defaultProps} 
        category={categoryWithFewKeywords} 
      />
    );
    
    expect(screen.getByText(/AI, tech/)).toBeInTheDocument();
    expect(screen.queryByText(/and \d+ more/)).not.toBeInTheDocument();
  });

  it('should call onConfirm when delete button clicked', async () => {
    const user = userEvent.setup();
    const mockOnConfirm = vi.fn();

    render(
      <DeleteConfirmationDialog
        {...defaultProps}
        onConfirm={mockOnConfirm}
      />
    );

    const deleteButton = screen.getByRole('button', { name: 'Delete Category' });
    await user.click(deleteButton);

    expect(mockOnConfirm).toHaveBeenCalled();
  });

  it('should call onCancel when cancel button clicked', async () => {
    const user = userEvent.setup();
    const mockOnCancel = vi.fn();
    
    render(
      <DeleteConfirmationDialog 
        {...defaultProps} 
        onCancel={mockOnCancel}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('should disable buttons when isDeleting is true', () => {
    render(<DeleteConfirmationDialog {...defaultProps} isDeleting={true} />);
    
    expect(screen.getByText('Cancel')).toBeDisabled();
    expect(screen.getByText('Deleting...')).toBeDisabled();
  });

  it('should show correct button text when not deleting', () => {
    render(<DeleteConfirmationDialog {...defaultProps} isDeleting={false} />);

    expect(screen.getByRole('button', { name: 'Delete Category' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });
});