import { useState, useEffect } from 'react';
import { CategoriesService } from '../../../services/categoriesService';
import { JobsService } from '../../../services/jobsService';
import type { Category, JobResponse } from '../../../types/shared';

interface ManualCrawlTriggerProps {
  onJobTriggered?: (job: JobResponse) => void;
}

export function ManualCrawlTrigger({ onJobTriggered }: ManualCrawlTriggerProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [maxResults, setMaxResults] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      setLoading(true);
      setError(null);
      const activeCategories = await CategoriesService.getCategories(true);
      setCategories(activeCategories);
    } catch (err) {
      setError('Failed to load categories. Please try again.');
      console.error('Error loading categories:', err);
    } finally {
      setLoading(false);
    }
  };

  const validateInputs = (): boolean => {
    // Validate date range
    if (startDate && endDate) {
      const start = new Date(startDate);
      const end = new Date(endDate);
      if (start >= end) {
        setError('End date must be after start date.');
        return false;
      }
    }

    // Validate max results
    if (maxResults) {
      const maxResultsNum = parseInt(maxResults);
      if (isNaN(maxResultsNum) || maxResultsNum < 1 || maxResultsNum > 500) {
        setError('Max results must be a number between 1 and 500.');
        return false;
      }
    }

    return true;
  };

  const handleTriggerClick = () => {
    if (!selectedCategoryId) {
      setError('Please select a category first.');
      return;
    }

    if (!validateInputs()) {
      return;
    }

    setShowConfirmation(true);
  };

  const handleConfirmTrigger = async () => {
    if (!selectedCategoryId) return;

    try {
      setTriggering(true);
      setError(null);
      setSuccess(null);
      setShowConfirmation(false);

      const selectedCategory = categories.find(c => c.id === selectedCategoryId);

      // Prepare job request with optional date filtering
      const jobRequest: any = {
        category_id: selectedCategoryId,
        priority: 1
      };

      // Add date filters if provided
      if (startDate) {
        jobRequest.start_date = new Date(startDate).toISOString();
      }
      if (endDate) {
        jobRequest.end_date = new Date(endDate).toISOString();
      }

      // Add max results if provided
      if (maxResults) {
        jobRequest.max_results = parseInt(maxResults);
      }

      const job = await JobsService.createJob(jobRequest);

      let successMessage = `Crawl job started successfully for "${selectedCategory?.name}" (Job ID: ${job.id})`;

      const filters = [];
      if (startDate || endDate) {
        filters.push(`dates: ${startDate || 'beginning'} to ${endDate || 'now'}`);
      }
      if (maxResults) {
        filters.push(`max articles: ${maxResults}`);
      }

      if (filters.length > 0) {
        successMessage += ` with ${filters.join(', ')}`;
      }

      setSuccess(successMessage);
      setSelectedCategoryId('');
      setStartDate('');
      setEndDate('');
      setMaxResults('');

      if (onJobTriggered) {
        onJobTriggered(job);
      }

    } catch (err) {
      if (err instanceof Error) {
        const message = err.message;
        if (message.includes('400')) {
          setError('Invalid category or category is not active.');
        } else if (message.includes('404')) {
          setError('Category not found.');
        } else if (message.includes('500')) {
          setError('System error occurred. Please try again later.');
        } else {
          setError('Failed to start crawl job. Please try again.');
        }
      } else {
        setError('An unexpected error occurred.');
      }
      console.error('Error triggering crawl job:', err);
    } finally {
      setTriggering(false);
    }
  };

  const selectedCategory = categories.find(c => c.id === selectedCategoryId);

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Manual Crawl Job Trigger</h2>
        <div className="text-center py-4">
          <div className="text-gray-500">Loading categories...</div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Manual Crawl Job Trigger</h2>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
            <div className="text-red-800 text-sm">{error}</div>
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 rounded-md p-3 mb-4">
            <div className="text-green-800 text-sm">{success}</div>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label htmlFor="category-select" className="block text-sm font-medium text-gray-700 mb-2">
              Select Category *
            </label>
            <select
              id="category-select"
              value={selectedCategoryId}
              onChange={(e) => {
                setSelectedCategoryId(e.target.value);
                setError(null);
                setSuccess(null);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Choose a category to crawl...</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} ({category.keywords.length} keywords)
                </option>
              ))}
            </select>
            {categories.length === 0 && (
              <div className="text-sm text-gray-500 mt-1">
                No active categories available. Please create and activate a category first.
              </div>
            )}
          </div>

          {/* Date and Limits Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="start-date" className="block text-sm font-medium text-gray-700 mb-2">
                Start Date (optional)
              </label>
              <input
                type="date"
                id="start-date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setError(null);
                  setSuccess(null);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                max={endDate || undefined}
              />
              <p className="text-xs text-gray-500 mt-1">
                Filter articles from this date onwards
              </p>
            </div>

            <div>
              <label htmlFor="end-date" className="block text-sm font-medium text-gray-700 mb-2">
                End Date (optional)
              </label>
              <input
                type="date"
                id="end-date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setError(null);
                  setSuccess(null);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                min={startDate || undefined}
              />
              <p className="text-xs text-gray-500 mt-1">
                Filter articles until this date
              </p>
            </div>

            <div>
              <label htmlFor="max-results" className="block text-sm font-medium text-gray-700 mb-2">
                Max Articles (optional)
              </label>
              <input
                type="number"
                id="max-results"
                value={maxResults}
                onChange={(e) => {
                  setMaxResults(e.target.value);
                  setError(null);
                  setSuccess(null);
                }}
                placeholder="Default: 100"
                min="1"
                max="500"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Maximum number of articles to crawl (1-500)
              </p>
            </div>
          </div>

          {/* Filters Summary */}
          {(startDate || endDate || maxResults) && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <div className="text-blue-800 text-sm">
                <strong>Filters Applied:</strong>
                <ul className="mt-1 space-y-1">
                  {(startDate || endDate) && (
                    <li>
                      • <strong>Date range:</strong>
                      {startDate && endDate && ` ${startDate} to ${endDate}`}
                      {startDate && !endDate && ` from ${startDate} onwards`}
                      {!startDate && endDate && ` until ${endDate}`}
                    </li>
                  )}
                  {maxResults && (
                    <li>• <strong>Max articles:</strong> {maxResults}</li>
                  )}
                </ul>
              </div>
            </div>
          )}

          {selectedCategory && (
            <div className="bg-gray-50 p-3 rounded-md">
              <h4 className="text-sm font-medium text-gray-900 mb-1">Category Details:</h4>
              <div className="text-sm text-gray-600">
                <div><strong>Keywords:</strong> {selectedCategory.keywords.join(', ')}</div>
                {selectedCategory.exclude_keywords.length > 0 && (
                  <div><strong>Exclude:</strong> {selectedCategory.exclude_keywords.join(', ')}</div>
                )}
              </div>
            </div>
          )}

          <div className="flex justify-end">
            <button
              onClick={handleTriggerClick}
              disabled={!selectedCategoryId || triggering}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {triggering ? 'Starting Job...' : 'Start Crawl Job'}
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Confirm Crawl Job
              </h3>
              <div className="text-sm text-gray-600 mb-4">
                <p className="mb-2">
                  Are you sure you want to start a crawl job for category "{selectedCategory?.name}"?
                  This will search for articles using the configured keywords.
                </p>
                {(startDate || endDate || maxResults) && (
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-2 mt-2">
                    <p className="text-blue-800 text-xs">
                      <strong>Filters:</strong>
                    </p>
                    <ul className="text-blue-800 text-xs mt-1 space-y-1">
                      {(startDate || endDate) && (
                        <li>
                          • Date range:
                          {startDate && endDate && ` ${startDate} to ${endDate}`}
                          {startDate && !endDate && ` from ${startDate} onwards`}
                          {!startDate && endDate && ` until ${endDate}`}
                        </li>
                      )}
                      {maxResults && (
                        <li>• Max articles: {maxResults}</li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowConfirmation(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmTrigger}
                  disabled={triggering}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {triggering ? 'Starting...' : 'Start Job'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}