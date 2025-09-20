import { useState } from 'react';
import { ArticlesService, type ArticleExportRequest } from '../../../services/articlesService';

interface ArticleExportProps {
  jobId?: string;
  categoryId?: string;
  onExportComplete?: (filename: string) => void;
  onExportError?: (error: string) => void;
}

export function ArticleExport({
  jobId,
  categoryId,
  onExportComplete,
  onExportError
}: ArticleExportProps) {
  const [selectedFormat, setSelectedFormat] = useState<'json' | 'csv' | 'xlsx'>('csv');
  const [selectedFields, setSelectedFields] = useState<string[]>([
    'title', 'author', 'publish_date', 'source_url', 'keywords_matched', 'relevance_score'
  ]);
  const [isExporting, setIsExporting] = useState(false);
  const [isAdvancedMode, setIsAdvancedMode] = useState(false);

  const availableFields = [
    { key: 'id', label: 'Article ID' },
    { key: 'title', label: 'Title' },
    { key: 'author', label: 'Author' },
    { key: 'publish_date', label: 'Publish Date' },
    { key: 'source_url', label: 'Source URL' },
    { key: 'keywords_matched', label: 'Keywords Matched' },
    { key: 'relevance_score', label: 'Relevance Score' },
    { key: 'created_at', label: 'Found Date' },
    { key: 'content', label: 'Full Content' },
    { key: 'image_url', label: 'Image URL' }
  ];

  const formatDescriptions = {
    json: 'JSON format with full data structure, best for programmatic use',
    csv: 'CSV format compatible with Excel and Google Sheets',
    xlsx: 'Native Excel format with proper formatting and UTF-8 support'
  };

  const handleExport = async () => {
    try {
      setIsExporting(true);

      const exportRequest: ArticleExportRequest = {
        format: selectedFormat,
        fields: selectedFields.length > 0 ? selectedFields : undefined,
        ...(jobId && { job_id: jobId }),
        ...(categoryId && { category_id: categoryId })
      };

      const blob = await ArticlesService.exportArticles(exportRequest);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[:.]/g, '-');
      const filename = `articles_export_${timestamp}.${selectedFormat}`;

      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Cleanup
      window.URL.revokeObjectURL(url);

      onExportComplete?.(filename);
    } catch (error: any) {
      console.error('Export failed:', error);
      onExportError?.(error.message || 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const handleFieldToggle = (field: string) => {
    setSelectedFields(prev =>
      prev.includes(field)
        ? prev.filter(f => f !== field)
        : [...prev, field]
    );
  };

  const selectAllFields = () => {
    setSelectedFields(availableFields.map(f => f.key));
  };

  const selectNoneFields = () => {
    setSelectedFields([]);
  };

  const selectDefaultFields = () => {
    setSelectedFields([
      'title', 'author', 'publish_date', 'source_url', 'keywords_matched', 'relevance_score'
    ]);
  };

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Export Articles</h3>
        <button
          onClick={() => setIsAdvancedMode(!isAdvancedMode)}
          className="text-sm text-blue-600 hover:text-blue-800 underline"
        >
          {isAdvancedMode ? 'Hide Advanced Options' : 'Show Advanced Options'}
        </button>
      </div>

      {/* Format Selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Export Format
        </label>
        <div className="space-y-3">
          {(Object.keys(formatDescriptions) as Array<keyof typeof formatDescriptions>).map(format => (
            <label key={format} className="flex items-start space-x-3">
              <input
                type="radio"
                name="format"
                value={format}
                checked={selectedFormat === format}
                onChange={(e) => setSelectedFormat(e.target.value as typeof selectedFormat)}
                className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
              />
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-900 uppercase">
                  {format}
                </div>
                <div className="text-xs text-gray-500">
                  {formatDescriptions[format]}
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Advanced Options */}
      {isAdvancedMode && (
        <div className="mb-4 p-3 bg-white border border-gray-200 rounded-md">
          <div className="flex items-center justify-between mb-3">
            <label className="block text-sm font-medium text-gray-700">
              Fields to Export
            </label>
            <div className="flex space-x-2 text-xs">
              <button
                onClick={selectAllFields}
                className="text-blue-600 hover:text-blue-800 underline"
              >
                Select All
              </button>
              <button
                onClick={selectDefaultFields}
                className="text-blue-600 hover:text-blue-800 underline"
              >
                Default
              </button>
              <button
                onClick={selectNoneFields}
                className="text-blue-600 hover:text-blue-800 underline"
              >
                None
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {availableFields.map(field => (
              <label key={field.key} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={selectedFields.includes(field.key)}
                  onChange={() => handleFieldToggle(field.key)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="text-sm text-gray-700">{field.label}</span>
              </label>
            ))}
          </div>
          {selectedFields.length === 0 && (
            <div className="text-xs text-orange-600 mt-2">
              ⚠️ No fields selected. All fields will be exported by default.
            </div>
          )}
        </div>
      )}

      {/* Export Summary */}
      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
        <div className="text-sm text-blue-800">
          <div className="font-medium mb-1">Export Summary:</div>
          <ul className="text-xs space-y-1">
            <li>• Format: {selectedFormat.toUpperCase()}</li>
            <li>• Fields: {selectedFields.length > 0 ? `${selectedFields.length} selected` : 'All fields'}</li>
            {jobId && <li>• Scope: Articles from specific job</li>}
            {categoryId && <li>• Scope: Articles from specific category</li>}
            <li>• Encoding: UTF-8 (supports Vietnamese characters)</li>
          </ul>
        </div>
      </div>

      {/* Export Button */}
      <button
        onClick={handleExport}
        disabled={isExporting}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isExporting ? (
          <>
            <span className="animate-spin mr-2">⟳</span>
            Exporting...
          </>
        ) : (
          <>
            <span className="mr-2">📥</span>
            Export Articles
          </>
        )}
      </button>

      {/* Help Text */}
      <div className="mt-3 text-xs text-gray-500">
        💡 <strong>Tip:</strong> CSV and Excel formats work best for data analysis.
        JSON format preserves all data structure and is best for programmatic use.
        All formats support Vietnamese characters with proper UTF-8 encoding.
      </div>
    </div>
  );
}

export default ArticleExport;