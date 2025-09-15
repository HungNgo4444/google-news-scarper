import type { Category } from '../../../types/shared';

interface DeleteConfirmationDialogProps {
  isOpen: boolean;
  category: Category | null;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

export function DeleteConfirmationDialog({ 
  isOpen, 
  category, 
  onConfirm, 
  onCancel, 
  isDeleting 
}: DeleteConfirmationDialogProps) {
  if (!isOpen || !category) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="p-6">
          <div className="flex items-center mb-4">
            <div className="flex-shrink-0 w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <span className="text-red-600 font-bold">⚠</span>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Delete Category</h3>
            </div>
          </div>

          <div className="mb-6">
            <p className="text-sm text-gray-600 mb-3">
              Are you sure you want to delete the category "<strong>{category.name}</strong>"?
            </p>
            
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
              <div className="text-yellow-800 text-sm">
                <strong>Warning:</strong> This action cannot be undone.
                {category.keywords.length > 0 && (
                  <div className="mt-2">
                    This will also remove all associated crawling configurations for keywords: {' '}
                    <span className="font-medium">
                      {category.keywords.slice(0, 3).join(', ')}
                      {category.keywords.length > 3 && ` and ${category.keywords.length - 3} more`}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onCancel}
              disabled={isDeleting}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={isDeleting}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
            >
              {isDeleting ? 'Deleting...' : 'Delete Category'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}