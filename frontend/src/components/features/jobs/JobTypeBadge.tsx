interface JobTypeBadgeProps {
  jobType: 'SCHEDULED' | 'ON_DEMAND';
  className?: string;
}

export function JobTypeBadge({ jobType, className = '' }: JobTypeBadgeProps) {
  if (jobType === 'SCHEDULED') {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 ${className}`}>
        <span className="mr-1">🕒</span>
        Scheduled
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 ${className}`}>
      <span className="mr-1">👤</span>
      Manual
    </span>
  );
}
