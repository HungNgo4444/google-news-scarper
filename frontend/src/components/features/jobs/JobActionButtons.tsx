import { useState } from 'react';
import type { JobResponse } from '../../../types/shared';
import { JobsService } from '../../../services/jobsService';

interface JobActionButtonsProps {
  job: JobResponse;
  onJobUpdated?: (updatedJob: JobResponse) => void;
  onJobDeleted?: (jobId: string) => void;
  onViewArticles?: (jobId: string) => void;
  onEditJob?: (job: JobResponse) => void;
}

export function JobActionButtons({
  job,
  onJobUpdated,
  onJobDeleted,
  onViewArticles,
  onEditJob
}: JobActionButtonsProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunNow = async () => {
    if (job.status !== 'pending') return;

    try {
      setLoading('execute');
      setError(null);

      // CRITICAL FIX: Use executeJobNow instead of just updating priority
      // This creates a new high-priority job and triggers immediate execution
      const newJob = await JobsService.executeJobNow(job.id);

      // Provide user feedback about immediate execution
      if (onJobUpdated) {
        onJobUpdated(newJob);
      }

      // Optional: Show success message
      console.log(`Job executed immediately. New job ID: ${newJob.id}`);
    } catch (err: any) {
      console.error('Failed to execute job immediately:', err);
      setError(err.message || 'Failed to execute job immediately');
    } finally {
      setLoading(null);
    }
  };

  const handleDelete = async () => {
    const confirmDelete = window.confirm(
      `Are you sure you want to delete this job?\n\n` +
      `Job ID: ${job.id.substring(0, 8)}...\n` +
      `Category: ${job.category_name}\n` +
      `Status: ${job.status}\n` +
      `Articles Found: ${job.articles_found}\n\n` +
      `This action cannot be undone.`
    );

    if (!confirmDelete) return;

    try {
      setLoading('delete');
      setError(null);

      await JobsService.deleteJob(job.id, {
        force: job.status === 'running', // Force delete if running
        delete_articles: false // Keep articles by default
      });

      onJobDeleted?.(job.id);
    } catch (err: any) {
      console.error('Failed to delete job:', err);
      setError(err.message || 'Failed to delete job');
    } finally {
      setLoading(null);
    }
  };

  const handleViewArticles = () => {
    onViewArticles?.(job.id);
  };

  const handleEdit = () => {
    onEditJob?.(job);
  };

  // Determine which buttons to show based on job status
  const canRunNow = job.status === 'pending';
  const canEdit = job.status !== 'running';
  const canDelete = true; // Allow delete for all statuses with confirmation
  const canViewArticles = true; // Always show to allow viewing even when no articles found

  // Priority indicator
  const isPriorityHigh = job.priority >= 5;

  return (
    <div className="flex items-center space-x-2">
      {/* Priority indicator */}
      {isPriorityHigh && (
        <span
          className="text-orange-500 text-lg"
          title={`High priority (${job.priority})`}
        >
          ⚡
        </span>
      )}

      {/* Run Now button */}
      {canRunNow && (
        <button
          onClick={handleRunNow}
          disabled={loading === 'execute'}
          className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md text-blue-600 bg-blue-50 border border-blue-200 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Execute job immediately with high priority"
        >
          {loading === 'execute' ? (
            <>
              <span className="animate-spin mr-1">⟳</span>
              Executing...
            </>
          ) : (
            <>
              <span className="mr-1">🚀</span>
              Run Now
            </>
          )}
        </button>
      )}

      {/* View Articles button */}
      {canViewArticles && (
        <button
          onClick={handleViewArticles}
          className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md text-green-600 bg-green-50 border border-green-200 hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1"
          title={`View ${job.articles_found} articles found by this job`}
        >
          <span className="mr-1">📄</span>
          View Articles {job.articles_found > 0 ? `(${job.articles_found})` : ''}
        </button>
      )}

      {/* Edit button */}
      {canEdit && (
        <button
          onClick={handleEdit}
          className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md text-gray-600 bg-gray-50 border border-gray-200 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-1"
          title="Edit job configuration"
        >
          <span className="mr-1">⚙️</span>
          Edit
        </button>
      )}

      {/* Delete button */}
      {canDelete && (
        <button
          onClick={handleDelete}
          disabled={loading === 'delete'}
          className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md text-red-600 bg-red-50 border border-red-200 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Delete this job"
        >
          {loading === 'delete' ? (
            <>
              <span className="animate-spin mr-1">⟳</span>
              Deleting...
            </>
          ) : (
            <>
              <span className="mr-1">🗑️</span>
              Delete
            </>
          )}
        </button>
      )}

      {/* Error message */}
      {error && (
        <div className="absolute z-10 mt-8 p-2 bg-red-100 border border-red-300 rounded-md shadow-lg">
          <div className="text-xs text-red-800">{error}</div>
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-600 hover:text-red-800"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

export default JobActionButtons;