interface ScheduleStatusBadgeProps {
  enabled: boolean;
  intervalMinutes?: number | null;
  crawlPeriod?: string | null;
  className?: string;
}

const INTERVAL_LABELS: Record<number, string> = {
  1: '1 min',
  30: '30 min',
  60: '1 hour',
  1440: 'Daily'
};

export function ScheduleStatusBadge({
  enabled,
  intervalMinutes,
  crawlPeriod,
  className = ''
}: ScheduleStatusBadgeProps) {
  if (!enabled || !intervalMinutes) {
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 ${className}`}>
        <span className="mr-1">⏸️</span>
        Disabled
      </span>
    );
  }

  const label = INTERVAL_LABELS[intervalMinutes] || `${intervalMinutes}m`;
  const periodDisplay = crawlPeriod ? ` (period: ${crawlPeriod})` : '';

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 ${className}`}>
      <span className="mr-1">🕒</span>
      {label}{periodDisplay}
    </span>
  );
}
