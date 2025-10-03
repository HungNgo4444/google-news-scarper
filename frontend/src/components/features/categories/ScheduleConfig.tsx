import { useState, useEffect } from 'react';

interface ScheduleConfigProps {
  categoryId?: string;
  isActive: boolean;
  initialEnabled?: boolean;
  initialInterval?: number | null;
  initialCrawlPeriod?: string | null;
  onChange?: (enabled: boolean, interval: number | null, crawlPeriod: string | null) => void;
}

const INTERVAL_OPTIONS = [
  { value: 1, label: '1 minute' },
  { value: 5, label: '5 minutes' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
  { value: 1440, label: '1 day' }
];

export function ScheduleConfig({
  categoryId,
  isActive,
  initialEnabled = false,
  initialInterval = null,
  initialCrawlPeriod = null,
  onChange
}: ScheduleConfigProps) {
  const [enabled, setEnabled] = useState(initialEnabled);
  const [interval, setInterval] = useState<number | null>(initialInterval);
  const [crawlPeriod, setCrawlPeriod] = useState<string>(initialCrawlPeriod || '');

  useEffect(() => {
    setEnabled(initialEnabled);
    setInterval(initialInterval);
    setCrawlPeriod(initialCrawlPeriod || '');
  }, [initialEnabled, initialInterval, initialCrawlPeriod]);

  const handleEnabledChange = (checked: boolean) => {
    if (!checked) {
      // When disabling, clear interval and notify parent
      setEnabled(false);
      setInterval(null);
      onChange?.(false, null, crawlPeriod || null);
    } else {
      // When enabling, set default interval if none selected
      setEnabled(true);
      const finalInterval = interval || 60; // Default to 1 hour
      setInterval(finalInterval);
      onChange?.(true, finalInterval, crawlPeriod || null);
    }
  };

  const handleIntervalChange = (value: number) => {
    setInterval(value);
    if (enabled) {
      onChange?.(true, value, crawlPeriod || null);
    }
  };

  const handleCrawlPeriodChange = (value: string) => {
    setCrawlPeriod(value);
    // Always notify parent of crawl_period change
    onChange?.(enabled, interval, value || null);
  };

  // Validation message
  const validationMessage = !isActive && enabled
    ? 'Schedule cannot be enabled for inactive categories'
    : null;

  return (
    <div className="space-y-4 p-4 border border-gray-200 rounded-lg bg-gray-50">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h3 className="text-sm font-medium text-gray-900">Auto-Crawl Schedule</h3>
          <p className="text-xs text-gray-500 mt-1">
            Automatically crawl this category at regular intervals
          </p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => handleEnabledChange(e.target.checked)}
            disabled={!isActive}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
        </label>
      </div>

      {validationMessage && (
        <div className="text-sm text-amber-600 bg-amber-50 p-2 rounded border border-amber-200">
          ⚠️ {validationMessage}
        </div>
      )}

      {/* Crawl Period - Always visible */}
      <div className="space-y-2 pt-2 border-t border-gray-200">
        <label className="block text-sm font-medium text-gray-700">
          Crawl Period (Optional)
        </label>
        <select
          value={crawlPeriod || ''}
          onChange={(e) => handleCrawlPeriodChange(e.target.value)}
          className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
        >
          <option value="">No limit (all available articles)</option>
          <option value="1h">Past 1 hour</option>
          <option value="2h">Past 2 hours</option>
          <option value="6h">Past 6 hours</option>
          <option value="12h">Past 12 hours</option>
          <option value="1d">Past 1 day</option>
          <option value="2d">Past 2 days</option>
          <option value="7d">Past 7 days</option>
          <option value="1m">Past 1 month</option>
          <option value="3m">Past 3 months</option>
          <option value="6m">Past 6 months</option>
          <option value="1y">Past 1 year</option>
        </select>
        <p className="text-xs text-gray-500">
          Limit articles to this time window. Only applies to scheduled crawls.
        </p>
      </div>

      {enabled && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Interval
          </label>
          <select
            value={interval || ''}
            onChange={(e) => handleIntervalChange(Number(e.target.value))}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          >
            <option value="" disabled>Select interval...</option>
            {INTERVAL_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {interval && (
            <p className="text-xs text-gray-500">
              Category will be crawled every {INTERVAL_OPTIONS.find(o => o.value === interval)?.label.toLowerCase()}
            </p>
          )}
        </div>
      )}

      {!enabled && (
        <p className="text-xs text-gray-500 italic">
          Schedule is disabled. Enable to configure automatic crawling.
        </p>
      )}
    </div>
  );
}
