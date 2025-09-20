import { useState, useEffect, useCallback } from 'react';
import { JobsService } from '../../../services/jobsService';
import { CategoriesService } from '../../../services/categoriesService';
import type { JobResponse, Category } from '../../../types/shared';
import JobActionButtons from './JobActionButtons';
import JobArticlesModal from './JobArticlesModal';
import JobEditModal from './JobEditModal';

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

interface JobsListProps {
  refreshTrigger?: number;
}

export function JobsList({ refreshTrigger = 0 }: JobsListProps) {
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [selectedJobForArticles, setSelectedJobForArticles] = useState<JobResponse | null>(null);
  const [isArticlesModalOpen, setIsArticlesModalOpen] = useState(false);
  const [selectedJobForEdit, setSelectedJobForEdit] = useState<JobResponse | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [limit] = useState(20);

  const loadCategories = async () => {
    try {
      const allCategories = await CategoriesService.getCategories();
      setCategories(allCategories);
    } catch (err) {
      console.error('Error loading categories for filter:', err);
    }
  };

  const loadJobs = useCallback(async () => {
    try {
      setError(null);
      setLoading(true);

      const params = {
        limit,
        ...(statusFilter && { status: statusFilter }),
        ...(categoryFilter && { category_id: categoryFilter })
      };

      const response = await JobsService.getJobs(params);
      setJobs(response.jobs);

    } catch (err) {
      setError('Failed to load jobs. Please try again.');
      console.error('Error loading jobs:', err);
    } finally {
      setLoading(false);
    }
  }, [limit, statusFilter, categoryFilter]);

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    loadJobs();
  }, [statusFilter, categoryFilter, refreshTrigger, loadJobs]);

  const handleRefresh = () => {
    loadJobs();
  };

  // Handler functions for JobActionButtons
  const handleJobUpdated = (updatedJob: JobResponse) => {
    setJobs(prevJobs =>
      prevJobs.map(job =>
        job.id === updatedJob.id ? updatedJob : job
      )
    );
  };

  const handleJobDeleted = (jobId: string) => {
    setJobs(prevJobs => prevJobs.filter(job => job.id !== jobId));
  };

  const handleViewArticles = (jobId: string) => {
    const job = jobs.find(j => j.id === jobId);
    if (job) {
      setSelectedJobForArticles(job);
      setIsArticlesModalOpen(true);
    }
  };

  const handleEditJob = (job: JobResponse) => {
    setSelectedJobForEdit(job);
    setIsEditModalOpen(true);
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (startTime: string | null, endTime: string | null) => {
    if (!startTime) return 'N/A';
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const durationMs = end.getTime() - start.getTime();
    const durationSeconds = Math.floor(durationMs / 1000);

    if (durationSeconds < 60) return `${durationSeconds}s`;
    const minutes = Math.floor(durationSeconds / 60);
    const seconds = durationSeconds % 60;
    return `${minutes}m ${seconds}s`;
  };

  const getCategoryName = (categoryId: string) => {
    const category = categories.find(c => c.id === categoryId);
    return category ? category.name : 'Unknown Category';
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Job History</h2>
        <div className="text-center py-8">
          <div className="text-gray-500">Loading jobs...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-medium text-gray-900">Job History</h2>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <label htmlFor="status-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Filter by Status
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div>
          <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Filter by Category
          </label>
          <select
            id="category-filter"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
          <div className="text-red-800 text-sm">{error}</div>
        </div>
      )}

      {/* Results Summary */}
      {!loading && (
        <div className="mb-4 text-sm text-gray-600">
          Showing {jobs.length} jobs
          {statusFilter && ` with status "${statusFilter}"`}
          {categoryFilter && ` for category "${getCategoryName(categoryFilter)}"`}
        </div>
      )}

      {/* Jobs Table */}
      {jobs.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-500 mb-2">No jobs found</div>
          <div className="text-sm text-gray-400">
            {statusFilter || categoryFilter
              ? 'Try adjusting your filters to see more results.'
              : 'Jobs will appear here once you start crawling categories.'}
          </div>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Job ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Category
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-mono text-gray-900">
                        {job.id ? job.id.substring(0, 8) : 'unknown'}...
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{job.category_name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLORS[job.status]}`}>
                        <span className="mr-1">{STATUS_ICONS[job.status]}</span>
                        {job.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {formatDateTime(job.created_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {formatDuration(job.started_at, job.completed_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <JobActionButtons
                        job={job}
                        onJobUpdated={handleJobUpdated}
                        onJobDeleted={handleJobDeleted}
                        onViewArticles={handleViewArticles}
                        onEditJob={handleEditJob}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </>
      )}

      {/* Articles Modal */}
      <JobArticlesModal
        job={selectedJobForArticles}
        isOpen={isArticlesModalOpen}
        onClose={() => {
          setIsArticlesModalOpen(false);
          setSelectedJobForArticles(null);
        }}
      />

      {/* Edit Job Modal */}
      <JobEditModal
        job={selectedJobForEdit}
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setSelectedJobForEdit(null);
        }}
        onJobUpdated={handleJobUpdated}
      />
    </div>
  );
}