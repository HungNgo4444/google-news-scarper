import { useState, useEffect } from 'react';
import { JobsService, type JobUpdateRequest } from '../../../services/jobsService';
import type { JobResponse } from '../../../types/shared';

interface JobEditModalProps {
  job: JobResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onJobUpdated?: (updatedJob: JobResponse) => void;
}

export function JobEditModal({ job, isOpen, onClose, onJobUpdated }: JobEditModalProps) {
  const [formData, setFormData] = useState({
    priority: 0,
    retry_count: 0,
    metadata: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when job changes
  useEffect(() => {
    if (job) {
      setFormData({
        priority: job.priority,
        retry_count: job.retry_count,
        metadata: job.correlation_id ? JSON.stringify({ correlation_id: job.correlation_id }, null, 2) : ''
      });
      setError(null);
    }
  }, [job]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!job) return;

    try {
      setLoading(true);
      setError(null);

      // Parse metadata JSON
      let jobMetadata: Record<string, any> | undefined;
      if (formData.metadata.trim()) {
        try {
          jobMetadata = JSON.parse(formData.metadata);
        } catch (err) {
          throw new Error('Invalid JSON in metadata field');
        }
      }

      // Prepare update request
      const updateRequest: JobUpdateRequest = {
        priority: formData.priority,
        retry_count: formData.retry_count,
        job_metadata: jobMetadata
      };

      // Update job
      const updatedJob = await JobsService.updateJob(job.id, updateRequest);

      // Notify parent component
      onJobUpdated?.(updatedJob);

      // Close modal
      onClose();
    } catch (err: any) {
      console.error('Failed to update job:', err);
      setError(err.message || 'Failed to update job');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    // Reset form to original values
    if (job) {
      setFormData({
        priority: job.priority,
        retry_count: job.retry_count,
        metadata: job.correlation_id ? JSON.stringify({ correlation_id: job.correlation_id }, null, 2) : ''
      });
    }
    setError(null);
    onClose();
  };

  const getPriorityLabel = (priority: number) => {
    if (priority >= 8) return 'Critical';
    if (priority >= 5) return 'High';
    if (priority >= 2) return 'Medium';
    return 'Low';
  };

  const getPriorityColor = (priority: number) => {
    if (priority >= 8) return 'text-red-600';
    if (priority >= 5) return 'text-orange-600';
    if (priority >= 2) return 'text-yellow-600';
    return 'text-gray-600';
  };

  if (!isOpen || !job) return null;

  const canEdit = job.status !== 'running';

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Edit Job</h2>
            <p className="text-sm text-gray-600 mt-1">
              Job ID: {job.id.substring(0, 8)}... | Category: {job.category_name}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col h-full">
          <div className="flex-1 overflow-y-auto p-6">
            {!canEdit && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 mb-4">
                <div className="text-yellow-800 text-sm">
                  ⚠️ This job is currently running and cannot be edited. Please wait for it to complete or fail before making changes.
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
                <div className="text-red-800 text-sm">{error}</div>
              </div>
            )}

            {/* Job Status Info */}
            <div className="bg-gray-50 border border-gray-200 rounded-md p-4 mb-6">
              <h3 className="text-sm font-medium text-gray-900 mb-2">Current Job Status</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Status:</span>
                  <span className="ml-2 font-medium">{job.status.toUpperCase()}</span>
                </div>
                <div>
                  <span className="text-gray-600">Articles Found:</span>
                  <span className="ml-2 font-medium">{job.articles_found}</span>
                </div>
                <div>
                  <span className="text-gray-600">Created:</span>
                  <span className="ml-2 font-medium">
                    {new Date(job.created_at).toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600">Last Updated:</span>
                  <span className="ml-2 font-medium">
                    {new Date(job.updated_at).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Priority Field */}
            <div className="mb-6">
              <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-2">
                Priority
              </label>
              <div className="flex items-center space-x-4">
                <input
                  type="range"
                  id="priority"
                  min="0"
                  max="10"
                  value={formData.priority}
                  onChange={(e) => setFormData(prev => ({ ...prev, priority: parseInt(e.target.value) }))}
                  disabled={!canEdit || loading}
                  className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                />
                <div className="flex flex-col items-center min-w-[80px]">
                  <span className="text-lg font-semibold">{formData.priority}</span>
                  <span className={`text-xs font-medium ${getPriorityColor(formData.priority)}`}>
                    {getPriorityLabel(formData.priority)}
                  </span>
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Higher priority jobs (5+) are processed before lower priority jobs.
                Priority 10 jobs run immediately.
              </div>
            </div>

            {/* Retry Count Field */}
            <div className="mb-6">
              <label htmlFor="retry_count" className="block text-sm font-medium text-gray-700 mb-2">
                Retry Count
              </label>
              <select
                id="retry_count"
                value={formData.retry_count}
                onChange={(e) => setFormData(prev => ({ ...prev, retry_count: parseInt(e.target.value) }))}
                disabled={!canEdit || loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:bg-gray-100"
              >
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(count => (
                  <option key={count} value={count}>
                    {count} {count === 0 ? '(No retries)' : count === 1 ? 'retry' : 'retries'}
                  </option>
                ))}
              </select>
              <div className="text-xs text-gray-500 mt-1">
                Number of times the job should be retried if it fails. Maximum is 10.
              </div>
            </div>

            {/* Metadata Field */}
            <div className="mb-6">
              <label htmlFor="metadata" className="block text-sm font-medium text-gray-700 mb-2">
                Job Metadata (JSON)
              </label>
              <textarea
                id="metadata"
                value={formData.metadata}
                onChange={(e) => setFormData(prev => ({ ...prev, metadata: e.target.value }))}
                disabled={!canEdit || loading}
                placeholder='{"key": "value", "description": "Additional job metadata"}'
                rows={6}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:bg-gray-100 font-mono text-sm"
              />
              <div className="text-xs text-gray-500 mt-1">
                Optional JSON metadata for this job. Must be valid JSON format.
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 bg-gray-50">
            <button
              type="button"
              onClick={handleCancel}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canEdit || loading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:bg-gray-400"
            >
              {loading ? (
                <>
                  <span className="animate-spin mr-2">⟳</span>
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default JobEditModal;