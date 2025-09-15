import { useState, useEffect } from 'react';
import type { Category, CreateCategoryRequest, UpdateCategoryRequest } from '../../../types/shared';

interface CategoryFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateCategoryRequest | UpdateCategoryRequest) => Promise<void>;
  initialData?: Category | null;
  title: string;
}

export function CategoryForm({ 
  isOpen, 
  onClose, 
  onSubmit, 
  initialData = null, 
  title 
}: CategoryFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    keywords: [] as string[],
    exclude_keywords: [] as string[],
    is_active: true
  });
  
  const [keywordsInput, setKeywordsInput] = useState('');
  const [excludeKeywordsInput, setExcludeKeywordsInput] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name,
        keywords: initialData.keywords,
        exclude_keywords: initialData.exclude_keywords,
        is_active: initialData.is_active
      });
      setKeywordsInput(initialData.keywords.join(', '));
      setExcludeKeywordsInput(initialData.exclude_keywords.join(', '));
    } else {
      setFormData({
        name: '',
        keywords: [],
        exclude_keywords: [],
        is_active: true
      });
      setKeywordsInput('');
      setExcludeKeywordsInput('');
    }
    setErrors({});
  }, [initialData, isOpen]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Category name is required';
    } else if (formData.name.length < 2) {
      newErrors.name = 'Category name must be at least 2 characters';
    } else if (formData.name.length > 100) {
      newErrors.name = 'Category name must be less than 100 characters';
    }

    if (formData.keywords.length === 0) {
      newErrors.keywords = 'At least one keyword is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const parseKeywords = (input: string): string[] => {
    return input
      .split(',')
      .map(keyword => keyword.trim())
      .filter(keyword => keyword.length > 0)
      .filter((keyword, index, array) => array.indexOf(keyword) === index); // Remove duplicates
  };

  const handleKeywordsChange = (value: string) => {
    setKeywordsInput(value);
    const parsedKeywords = parseKeywords(value);
    setFormData(prev => ({ ...prev, keywords: parsedKeywords }));
  };

  const handleExcludeKeywordsChange = (value: string) => {
    setExcludeKeywordsInput(value);
    const parsedKeywords = parseKeywords(value);
    setFormData(prev => ({ ...prev, exclude_keywords: parsedKeywords }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      setSubmitting(true);
      setErrors({});
      await onSubmit(formData);
      onClose();
    } catch (err) {
      if (err instanceof Error) {
        const message = err.message;
        if (message.includes('409') || message.toLowerCase().includes('already exists')) {
          setErrors({ name: 'A category with this name already exists' });
        } else if (message.includes('400') || message.toLowerCase().includes('validation')) {
          setErrors({ general: 'Please check your input and try again' });
        } else {
          setErrors({ general: 'An error occurred while saving the category' });
        }
      } else {
        setErrors({ general: 'An unexpected error occurred' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <span className="sr-only">Close</span>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errors.general && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="text-red-800 text-sm">{errors.general}</div>
            </div>
          )}

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              Category Name *
            </label>
            <input
              type="text"
              id="name"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className={`w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.name ? 'border-red-300' : 'border-gray-300'
              }`}
              placeholder="e.g., Technology, Sports, Politics"
            />
            {errors.name && (
              <div className="text-red-600 text-sm mt-1">{errors.name}</div>
            )}
          </div>

          <div>
            <label htmlFor="keywords" className="block text-sm font-medium text-gray-700 mb-1">
              Keywords *
            </label>
            <input
              type="text"
              id="keywords"
              value={keywordsInput}
              onChange={(e) => handleKeywordsChange(e.target.value)}
              className={`w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.keywords ? 'border-red-300' : 'border-gray-300'
              }`}
              placeholder="AI, machine learning, technology (comma-separated)"
            />
            <div className="text-xs text-gray-500 mt-1">
              Separate keywords with commas. Current: {formData.keywords.length} keyword(s)
            </div>
            {errors.keywords && (
              <div className="text-red-600 text-sm mt-1">{errors.keywords}</div>
            )}
          </div>

          <div>
            <label htmlFor="exclude_keywords" className="block text-sm font-medium text-gray-700 mb-1">
              Exclude Keywords (Optional)
            </label>
            <input
              type="text"
              id="exclude_keywords"
              value={excludeKeywordsInput}
              onChange={(e) => handleExcludeKeywordsChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="spam, advertisement (comma-separated)"
            />
            <div className="text-xs text-gray-500 mt-1">
              Articles containing these words will be excluded. Current: {formData.exclude_keywords.length} keyword(s)
            </div>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) => setFormData(prev => ({ ...prev, is_active: e.target.checked }))}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="is_active" className="ml-2 block text-sm text-gray-900">
              Active (will be used for crawling)
            </label>
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {submitting ? 'Saving...' : (initialData ? 'Update' : 'Create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}