import { useState } from 'react';
import type { Category, CreateCategoryRequest, UpdateCategoryRequest } from '../types/shared';
import { CategoriesService } from '../services/categoriesService';
import { CategoriesList } from '../components/features/categories/CategoriesList';
import { CategoryForm } from '../components/features/categories/CategoryForm';
import { DeleteConfirmationDialog } from '../components/features/categories/DeleteConfirmationDialog';

type FormMode = 'create' | 'edit' | null;

export function CategoriesPage() {
  const [formMode, setFormMode] = useState<FormMode>(null);
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);
  const [deleteCategory, setDeleteCategory] = useState<Category | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const showSuccess = (message: string) => {
    setSuccess(message);
    setTimeout(() => setSuccess(null), 3000);
  };

  const showError = (message: string) => {
    setError(message);
    setTimeout(() => setError(null), 5000);
  };

  const refresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  const handleCreateNew = () => {
    setSelectedCategory(null);
    setFormMode('create');
  };

  const handleEdit = (category: Category) => {
    setSelectedCategory(category);
    setFormMode('edit');
  };

  const handleDelete = (category: Category) => {
    setDeleteCategory(category);
  };

  const handleToggleStatus = async (category: Category) => {
    try {
      const newStatus = !category.is_active;
      await CategoriesService.toggleCategoryStatus(category.id, newStatus);
      showSuccess(`Category "${category.name}" ${newStatus ? 'activated' : 'deactivated'} successfully`);
      refresh();
    } catch (err) {
      showError(`Failed to update category status: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleFormSubmit = async (data: CreateCategoryRequest | UpdateCategoryRequest) => {
    let result;
    if (formMode === 'create') {
      result = await CategoriesService.createCategory(data as CreateCategoryRequest);
      showSuccess('Category created successfully');
    } else if (formMode === 'edit' && selectedCategory) {
      result = await CategoriesService.updateCategory(selectedCategory.id, data);
      showSuccess('Category updated successfully');
    }
    setFormMode(null);
    setSelectedCategory(null);
    refresh();
    return result; // Return created/updated category for schedule config
  };

  const handleConfirmDelete = async () => {
    if (!deleteCategory) return;

    try {
      setIsDeleting(true);
      await CategoriesService.deleteCategory(deleteCategory.id);
      showSuccess(`Category "${deleteCategory.name}" deleted successfully`);
      setDeleteCategory(null);
      refresh();
    } catch (err) {
      showError(`Failed to delete category: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setDeleteCategory(null);
  };

  const handleCloseForm = () => {
    setFormMode(null);
    setSelectedCategory(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Success/Error Messages */}
        {success && (
          <div className="mb-4 bg-green-50 border border-green-200 rounded-md p-4">
            <div className="text-green-800">{success}</div>
          </div>
        )}
        
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
            <div className="text-red-800">{error}</div>
          </div>
        )}

        {/* Main Content */}
        <CategoriesList
          onEdit={handleEdit}
          onDelete={handleDelete}
          onToggleStatus={handleToggleStatus}
          onCreateNew={handleCreateNew}
          refreshTrigger={refreshTrigger}
        />

        {/* Modals */}
        <CategoryForm
          isOpen={formMode !== null}
          onClose={handleCloseForm}
          onSubmit={handleFormSubmit}
          initialData={selectedCategory}
          title={formMode === 'create' ? 'Create Category' : 'Edit Category'}
        />

        <DeleteConfirmationDialog
          isOpen={deleteCategory !== null}
          category={deleteCategory}
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
          isDeleting={isDeleting}
        />
      </div>
    </div>
  );
}