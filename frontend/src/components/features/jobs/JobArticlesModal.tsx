import { useState, useEffect } from 'react';
import { ArticlesService, type ArticleResponse } from '../../../services/articlesService';
import type { JobResponse } from '../../../types/shared';
import ArticleExport from '../articles/ArticleExport';

interface JobArticlesModalProps {
  job: JobResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function JobArticlesModal({ job, isOpen, onClose }: JobArticlesModalProps) {
  const [articles, setArticles] = useState<ArticleResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showExport, setShowExport] = useState(false);
  const [exportMessage, setExportMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const pageSize = 10;

  // Load articles when modal opens or job changes
  useEffect(() => {
    if (isOpen && job) {
      loadArticles();
    }
  }, [isOpen, job, currentPage, searchQuery]);

  const loadArticles = async () => {
    if (!job) return;

    try {
      setLoading(true);
      setError(null);

      const params = {
        job_id: job.id,
        page: currentPage,
        size: pageSize,
        ...(searchQuery && { search: searchQuery })
      };

      const response = await ArticlesService.getArticles(params);
      setArticles(response.articles);
      setTotal(response.total);
      setTotalPages(response.pages);
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

  const truncateText = (text: string, maxLength: number = 100) => {
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Articles from Job: {job?.category_name}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Job ID: {job?.id?.substring(0, 8)}... |
              Status: {job?.status} |
              Found: {job?.articles_found} articles
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowExport(!showExport)}
              className="px-3 py-1 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              📥 {showExport ? 'Hide Export' : 'Export Data'}
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
            >
              ×
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-gray-200">
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
          <div className="p-4 border-b border-gray-200">
            <ArticleExport
              jobId={job?.id}
              onExportComplete={handleExportComplete}
              onExportError={handleExportError}
            />
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {/* Export Messages */}
          {exportMessage && (
            <div className={`border rounded-md p-3 mb-4 ${
              exportMessage.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-800'
            }`}>
              <div className="text-sm">{exportMessage.text}</div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
              <div className="text-red-800 text-sm">{error}</div>
            </div>
          )}

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

              {/* Articles list */}
              <div className="space-y-4">
                {articles.map((article) => (
                  <div
                    key={article.id}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-lg font-medium text-gray-900 mb-1">
                        {article.title}
                      </h3>
                      <div className="flex items-center space-x-2">
                        {/* Relevance score */}
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${
                            article.relevance_score >= 0.7
                              ? 'bg-green-100 text-green-800'
                              : article.relevance_score >= 0.4
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {Math.round(article.relevance_score * 100)}% relevant
                        </span>
                        {/* External link button */}
                        <button
                          onClick={() => openArticleInNewTab(article.source_url)}
                          className="text-blue-600 hover:text-blue-800 text-sm underline"
                          title="Open article in new tab"
                        >
                          View Original ↗
                        </button>
                      </div>
                    </div>

                    <div className="text-sm text-gray-600 mb-2">
                      <div className="flex items-center space-x-4">
                        {article.author && <span>By {article.author}</span>}
                        {article.publish_date && (
                          <span>Published: {formatDateTime(article.publish_date)}</span>
                        )}
                        <span>Found: {formatDateTime(article.created_at)}</span>
                      </div>
                    </div>

                    {/* Keywords matched */}
                    {article.keywords_matched && article.keywords_matched.length > 0 && (
                      <div className="mb-2">
                        <span className="text-xs text-gray-500">Matched keywords: </span>
                        <div className="inline-flex flex-wrap gap-1">
                          {article.keywords_matched.map((keyword, index) => (
                            <span
                              key={index}
                              className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full"
                            >
                              {keyword}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Article content preview */}
                    {article.content && (
                      <div className="text-sm text-gray-700">
                        {truncateText(article.content, 200)}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center space-x-2 mt-6 pt-4 border-t border-gray-200">
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

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default JobArticlesModal;