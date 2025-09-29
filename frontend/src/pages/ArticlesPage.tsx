import { useState, useEffect } from 'react';
import { ArticlesService, type ArticleResponse } from '../services/articlesService';
import type { JobResponse } from '../types/shared';
import ArticleExport from '../components/features/articles/ArticleExport';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';

interface ArticlesPageProps {
  jobId: string;
  onNavigateBack: () => void;
}

export function ArticlesPage({ jobId, onNavigateBack }: ArticlesPageProps) {
  const [articles, setArticles] = useState<ArticleResponse[]>([]);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showExport, setShowExport] = useState(false);
  const [exportMessage, setExportMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const pageSize = 10;

  // Load job details and articles when component mounts
  useEffect(() => {
    if (jobId) {
      loadJobDetails();
      loadArticles();
    }
  }, [jobId, currentPage, searchQuery]);

  const loadJobDetails = async () => {
    try {
      // In a real implementation, you'd fetch job details from API
      // For now, we'll create a placeholder job object
      setJob({
        id: jobId,
        category_name: 'Loading...',
        status: 'unknown',
        articles_found: 0,
        articles_saved: 0,
        priority: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        category_id: '',
        last_run: null,
        next_run: null,
        is_active: true,
        error_message: null
      });
    } catch (err: any) {
      console.error('Error loading job details:', err);
      setError(err.message || 'Failed to load job details');
    }
  };

  const loadArticles = async () => {
    if (!jobId) return;

    try {
      setLoading(true);
      setError(null);

      const params = {
        job_id: jobId,
        page: currentPage,
        size: pageSize,
        ...(searchQuery && { search: searchQuery })
      };

      const response = await ArticlesService.getArticles(params);
      setArticles(response.articles);
      setTotal(response.total);
      setTotalPages(response.pages);

      // Update job info if we have it
      if (response.articles.length > 0 && job) {
        setJob(prev => prev ? { ...prev, articles_found: response.total } : null);
      }
    } catch (err: any) {
      console.error('Error loading articles:', err);
      setError(err.message || 'Failed to load articles');
      setArticles([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1); // Reset to first page when searching
    loadArticles();
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const truncateText = (text: string | null, maxLength: number = 50) => {
    if (!text) return 'N/A';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  const openArticleInNewTab = (url: string) => {
    window.open(url, '_blank');
  };

  const handleExportComplete = (filename: string) => {
    setExportMessage({
      type: 'success',
      text: `Export completed successfully! Downloaded: ${filename}`
    });
    setTimeout(() => setExportMessage(null), 5000);
  };

  const handleExportError = (error: string) => {
    setExportMessage({
      type: 'error',
      text: `Export failed: ${error}`
    });
    setTimeout(() => setExportMessage(null), 5000);
  };

  return (
    <div className="container mx-auto py-8 px-4">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center space-x-2 mb-6">
        <button
          onClick={onNavigateBack}
          className="text-blue-600 hover:text-blue-800 underline"
        >
          Jobs
        </button>
        <span className="text-gray-500">→</span>
        <span className="text-gray-900">Articles</span>
      </div>

      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Articles from Job
          </h1>
          {job && (
            <p className="text-sm text-gray-600 mt-1">
              Job ID: {job.id?.substring(0, 8)}... |
              Status: {job.status} |
              Found: {total} articles
            </p>
          )}
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onNavigateBack}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            ← Back to Jobs
          </button>
          <button
            onClick={() => setShowExport(!showExport)}
            className="px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            📥 {showExport ? 'Hide Export' : 'Export Data'}
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-6">
        <form onSubmit={handleSearchSubmit} className="flex space-x-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search articles by title or content..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setCurrentPage(1);
              }}
              className="px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Export Component */}
      {showExport && (
        <div className="mb-6">
          <ArticleExport
            jobId={jobId}
            onExportComplete={handleExportComplete}
            onExportError={handleExportError}
          />
        </div>
      )}

      {/* Export Messages */}
      {exportMessage && (
        <div className={`border rounded-md p-3 mb-6 ${
          exportMessage.type === 'success'
            ? 'bg-green-50 border-green-200 text-green-800'
            : 'bg-red-50 border-red-200 text-red-800'
        }`}>
          <div className="text-sm">{exportMessage.text}</div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-6">
          <div className="text-red-800 text-sm">{error}</div>
        </div>
      )}

      {/* Loading State */}
      {loading && articles.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-500">Loading articles...</div>
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-500 mb-2">No articles found</div>
          <div className="text-sm text-gray-400">
            {searchQuery
              ? 'Try adjusting your search terms.'
              : 'This job hasn\'t found any articles yet.'}
          </div>
        </div>
      ) : (
        <>
          {/* Results count */}
          <div className="mb-4 text-sm text-gray-600">
            Showing {articles.length} of {total} articles
            {searchQuery && ` matching "${searchQuery}"`}
          </div>

          {/* Articles Table */}
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">ID</TableHead>
                    <TableHead className="min-w-[200px]">Title</TableHead>
                    <TableHead>Author</TableHead>
                    <TableHead>Publish Date</TableHead>
                    <TableHead className="min-w-[150px]">Source URL</TableHead>
                    <TableHead>Keywords Matched</TableHead>
                    <TableHead>Relevance</TableHead>
                    <TableHead>Created At</TableHead>
                    <TableHead>Last Seen</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {articles.map((article) => (
                    <TableRow key={article.id} className="hover:bg-gray-50">
                      <TableCell className="text-xs font-mono">
                        {article.id.substring(0, 8)}...
                      </TableCell>
                      <TableCell className="font-medium">
                        <div className="max-w-[300px]">
                          <div className="truncate" title={article.title}>
                            {article.title}
                          </div>
                          {article.content && (
                            <div className="text-xs text-gray-500 mt-1 truncate" title={article.content}>
                              {truncateText(article.content, 80)}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{truncateText(article.author, 30)}</TableCell>
                      <TableCell className="text-sm">
                        {formatDateTime(article.publish_date)}
                      </TableCell>
                      <TableCell>
                        <div className="max-w-[150px]">
                          <a
                            href={article.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 text-sm truncate block"
                            title={article.source_url}
                          >
                            {new URL(article.source_url).hostname}
                          </a>
                        </div>
                      </TableCell>
                      <TableCell>
                        {article.keywords_matched && article.keywords_matched.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {article.keywords_matched.slice(0, 2).map((keyword, index) => (
                              <span
                                key={index}
                                className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full"
                              >
                                {keyword}
                              </span>
                            ))}
                            {article.keywords_matched.length > 2 && (
                              <span className="text-xs text-gray-500">
                                +{article.keywords_matched.length - 2}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">None</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${
                            article.relevance_score >= 0.7
                              ? 'bg-green-100 text-green-800'
                              : article.relevance_score >= 0.4
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {Math.round(article.relevance_score * 100)}%
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDateTime(article.created_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDateTime(article.last_seen)}
                      </TableCell>
                      <TableCell>
                        <button
                          onClick={() => openArticleInNewTab(article.source_url)}
                          className="text-blue-600 hover:text-blue-800 text-sm underline"
                          title="Open article in new tab"
                        >
                          View ↗
                        </button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center space-x-2 mt-6">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1 || loading}
                className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages || loading}
                className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ArticlesPage;