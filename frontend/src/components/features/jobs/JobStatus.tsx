import { useState, useEffect, useRef } from 'react';
import { JobsService } from '../../../services/jobsService';
import type { JobResponse } from '../../../types/shared';

interface JobStatusProps {
  jobId: string;
  onJobComplete?: (job: JobResponse) => void;
}

const STATUS_COLORS = {
  pending: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  running: 'text-blue-600 bg-blue-50 border-blue-200',
  completed: 'text-green-600 bg-green-50 border-green-200',
  failed: 'text-red-600 bg-red-50 border-red-200'
};

const STATUS_ICONS = {
  pending: '⏳',
  running: '🔄',
  completed: '✅',
  failed: '❌'
};

export function JobStatus({ jobId, onJobComplete }: JobStatusProps) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const fetchStatus = async () => {
      try {
        setError(null);
        const jobData = await JobsService.getJobStatus(jobId);
        setJob(jobData);

        // Stop polling if job is completed or failed
        if (jobData.status === 'completed' || jobData.status === 'failed') {
          stopPolling();
          if (jobData.status === 'completed' && onJobComplete) {
            onJobComplete(jobData);
          }
        }
      } catch (err) {
        setError('Failed to fetch job status');
        console.error('Error fetching job status:', err);
        stopPolling();
      } finally {
        setLoading(false);
      }
    };

    const startPolling = () => {
      // Poll every 2 seconds as specified in the story
      pollingIntervalRef.current = setInterval(() => {
        fetchStatus();
      }, 2000);
    };

    fetchStatus();
    startPolling();

    return () => {
      stopPolling();
    };
  }, [jobId, onJobComplete]);


  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const getElapsedTime = (startTime: string | null) => {
    if (!startTime) return 'N/A';
    const start = new Date(startTime);
    const now = new Date();
    const elapsedMs = now.getTime() - start.getTime();
    const elapsedSeconds = Math.floor(elapsedMs / 1000);

    if (elapsedSeconds < 60) return `${elapsedSeconds}s`;
    const elapsedMinutes = Math.floor(elapsedSeconds / 60);
    const remainingSeconds = elapsedSeconds % 60;
    return `${elapsedMinutes}m ${remainingSeconds}s`;
  };

  if (loading && !job) {
    return (
      <div className="bg-white p-4 rounded-lg shadow">
        <div className="text-center py-4">
          <div className="text-gray-500">Loading job status...</div>
        </div>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="bg-white p-4 rounded-lg shadow">
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <div className="text-red-800 text-sm">{error}</div>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={() => {
              setLoading(true);
              setError(null);
              window.location.reload(); // Simple retry by reloading
            }}
            className="px-3 py-1 text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="bg-white p-4 rounded-lg shadow">
        <div className="text-center py-4">
          <div className="text-gray-500">Job not found</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Job Status</h3>
        {(job.status === 'running' || job.status === 'pending') && (
          <div className="text-sm text-gray-500">
            Auto-refreshing every 2 seconds
          </div>
        )}
      </div>

      <div className="space-y-3">
        {/* Status Badge */}
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-700">Status:</span>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLORS[job.status]}`}>
            <span className="mr-1">{STATUS_ICONS[job.status]}</span>
            {job.status.toUpperCase()}
          </span>
        </div>

        {/* Job Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-medium text-gray-700">Job ID:</span>
            <span className="ml-2 text-gray-600 font-mono">{job.id}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">Category:</span>
            <span className="ml-2 text-gray-600">{job.category_name}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">Created:</span>
            <span className="ml-2 text-gray-600">{formatDateTime(job.created_at)}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">Started:</span>
            <span className="ml-2 text-gray-600">{formatDateTime(job.started_at)}</span>
          </div>
          {job.completed_at && (
            <div>
              <span className="font-medium text-gray-700">Completed:</span>
              <span className="ml-2 text-gray-600">{formatDateTime(job.completed_at)}</span>
            </div>
          )}
          {job.started_at && (
            <div>
              <span className="font-medium text-gray-700">Duration:</span>
              <span className="ml-2 text-gray-600">
                {job.completed_at
                  ? getElapsedTime(job.started_at) + ' (finished)'
                  : getElapsedTime(job.started_at) + ' (running)'
                }
              </span>
            </div>
          )}
        </div>

        {/* Progress Information */}
        {job.status === 'running' && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
            <div className="text-blue-800 text-sm font-medium mb-1">
              Crawl in Progress
            </div>
            <div className="text-blue-700 text-sm">
              The system is actively searching for articles matching the category keywords.
              Status updates will appear here automatically.
            </div>
          </div>
        )}

        {job.status === 'completed' && (
          <div className="bg-green-50 border border-green-200 rounded-md p-3">
            <div className="text-green-800 text-sm font-medium mb-1">
              Crawl Completed Successfully
            </div>
            <div className="text-green-700 text-sm">
              The crawl job has finished successfully. Check the articles section for newly discovered content.
            </div>
          </div>
        )}

        {job.status === 'failed' && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <div className="text-red-800 text-sm font-medium mb-1">
              Crawl Job Failed
            </div>
            <div className="text-red-700 text-sm">
              The crawl job encountered an error and could not complete.
              Please try triggering a new job or check system logs.
            </div>
          </div>
        )}

        {/* Technical Details */}
        <details className="mt-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900">
            Technical Details
          </summary>
          <div className="mt-2 pl-4 space-y-1 text-sm text-gray-600">
            <div><span className="font-medium">Celery Task ID:</span> {job.celery_task_id}</div>
            <div><span className="font-medium">Correlation ID:</span> {job.correlation_id}</div>
            <div><span className="font-medium">Priority:</span> {job.priority}</div>
          </div>
        </details>
      </div>
    </div>
  );
}