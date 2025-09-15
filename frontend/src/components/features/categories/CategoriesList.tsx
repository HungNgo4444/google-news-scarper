import { useState, useEffect } from 'react';
import type { Category } from '../../../types/shared';
import { CategoriesService } from '../../../services/categoriesService';

interface CategoriesListProps {
  onEdit: (category: Category) => void;
  onDelete: (category: Category) => void;
  onToggleStatus: (category: Category) => void;
  onCreateNew: () => void;
  refreshTrigger?: number;
}

export function CategoriesList({ 
  onEdit, 
  onDelete, 
  onToggleStatus, 
  onCreateNew, 
  refreshTrigger = 0 
}: CategoriesListProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<'name' | 'created_at'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const loadCategories = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await CategoriesService.getCategories();
      setCategories(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load categories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, [refreshTrigger]);

  const handleSort = (field: 'name' | 'created_at') => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedCategories = [...categories].sort((a, b) => {
    const aValue = sortField === 'name' ? a.name : a.created_at;
    const bValue = sortField === 'name' ? b.name : b.created_at;
    
    const comparison = aValue.localeCompare(bValue);
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-600">Loading categories...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
        <div className="text-red-800 font-medium">Error loading categories</div>
        <div className="text-red-600 text-sm mt-1">{error}</div>
        <button 
          onClick={loadCategories}
          className="mt-2 bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Categories</h2>
        <button
          onClick={onCreateNew}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium"
        >
          Create Category
        </button>
      </div>

      {categories.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No categories found. Create your first category to get started.
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('name')}
                >
                  Name {sortField === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Keywords
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Exclude Keywords
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('created_at')}
                >
                  Created {sortField === 'created_at' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedCategories.map((category) => (
                <tr key={category.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{category.name}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">
                      {category.keywords.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {category.keywords.slice(0, 3).map((keyword, idx) => (
                            <span key={idx} className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                              {keyword}
                            </span>
                          ))}
                          {category.keywords.length > 3 && (
                            <span className="text-xs text-gray-500">
                              +{category.keywords.length - 3} more
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">No keywords</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">
                      {category.exclude_keywords.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {category.exclude_keywords.slice(0, 2).map((keyword, idx) => (
                            <span key={idx} className="inline-block bg-red-100 text-red-800 text-xs px-2 py-1 rounded">
                              {keyword}
                            </span>
                          ))}
                          {category.exclude_keywords.length > 2 && (
                            <span className="text-xs text-gray-500">
                              +{category.exclude_keywords.length - 2} more
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">None</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => onToggleStatus(category)}
                      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                        category.is_active 
                          ? 'bg-green-100 text-green-800 hover:bg-green-200' 
                          : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                      }`}
                    >
                      {category.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(category.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                    <button
                      onClick={() => onEdit(category)}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => onDelete(category)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}