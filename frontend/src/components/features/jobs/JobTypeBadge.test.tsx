import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { JobTypeBadge } from './JobTypeBadge';

describe('JobTypeBadge', () => {
  it('should display "Scheduled" badge for SCHEDULED job type', () => {
    render(<JobTypeBadge jobType="SCHEDULED" />);

    const badge = screen.getByText('Scheduled');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('bg-blue-100', 'text-blue-800');
    expect(screen.getByText('🕒')).toBeInTheDocument();
  });

  it('should display "Manual" badge for ON_DEMAND job type', () => {
    render(<JobTypeBadge jobType="ON_DEMAND" />);

    const badge = screen.getByText('Manual');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('bg-purple-100', 'text-purple-800');
    expect(screen.getByText('👤')).toBeInTheDocument();
  });

  it('should apply custom className when provided', () => {
    const { container } = render(
      <JobTypeBadge jobType="SCHEDULED" className="custom-class" />
    );

    const badge = container.querySelector('.custom-class');
    expect(badge).toBeInTheDocument();
  });

  it('should render badge with proper structure for accessibility', () => {
    render(<JobTypeBadge jobType="SCHEDULED" />);

    const badge = screen.getByText('Scheduled');
    expect(badge.tagName).toBe('SPAN');
    expect(badge).toHaveClass('inline-flex', 'items-center');
  });

  it('should distinguish SCHEDULED vs ON_DEMAND visually', () => {
    const { rerender } = render(<JobTypeBadge jobType="SCHEDULED" />);

    // SCHEDULED should be blue
    expect(screen.getByText('Scheduled')).toHaveClass('bg-blue-100');

    // ON_DEMAND should be purple
    rerender(<JobTypeBadge jobType="ON_DEMAND" />);
    expect(screen.getByText('Manual')).toHaveClass('bg-purple-100');
  });
});
