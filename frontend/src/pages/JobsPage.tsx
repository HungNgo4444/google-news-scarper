import { useState } from 'react';
import { ManualCrawlTrigger } from '../components/features/jobs/ManualCrawlTrigger';
import { JobStatus } from '../components/features/jobs/JobStatus';
import { JobsList } from '../components/features/jobs/JobsList';
import type { JobResponse } from '../types/shared';

export function JobsPage() {
  const [currentJob, setCurrentJob] = useState<JobResponse | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleJobTriggered = (job: JobResponse) => {
    setCurrentJob(job);
    // Trigger refresh of jobs list
    setRefreshTrigger(prev => prev + 1);
  };

  const handleJobComplete = () => {
    // Trigger refresh of jobs list when job completes
    setRefreshTrigger(prev => prev + 1);
  };

  const clearCurrentJob = () => {
    setCurrentJob(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Job Management</h1>
          <p className="mt-2 text-gray-600">
            Trigger manual crawl jobs and monitor their progress
          </p>
        </div>

        <div className="space-y-8">
          {/* Manual Crawl Trigger */}
          <ManualCrawlTrigger onJobTriggered={handleJobTriggered} />

          {/* Current Job Status */}
          {currentJob && (
            <div className="relative">
              <button
                onClick={clearCurrentJob}
                className="absolute top-4 right-4 z-10 text-gray-400 hover:text-gray-600 bg-white rounded-full p-1 shadow-sm"
                aria-label="Dismiss job status"
              >
                <span className="sr-only">Dismiss</span>
                ✕
              </button>
              <JobStatus
                jobId={currentJob.id}
                onJobComplete={handleJobComplete}
              />
            </div>
          )}

          {/* Job History */}
          <JobsList refreshTrigger={refreshTrigger} />
        </div>
      </div>
    </div>
  );
}