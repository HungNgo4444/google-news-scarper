import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CategoriesService } from './categoriesService';
import { apiClient } from './api';

// Mock the api client
vi.mock('./api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn()
  }
}));

const mockApiClient = vi.mocked(apiClient);

describe('CategoriesService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getCategories', () => {
    it('should call API with correct URL for all categories', async () => {
      const mockCategories = [
        {
          id: '1',
          name: 'Technology',
          keywords: ['AI', 'tech'],
          exclude_keywords: [],
          is_active: true,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ];
      
      const mockResponse = { categories: mockCategories, total: 1, active_count: 1 };
      mockApiClient.get.mockResolvedValue(mockResponse);

      const result = await CategoriesService.getCategories();

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v1/categories');
      expect(result).toEqual(mockCategories);
    });

    it('should call API with active_only parameter when specified', async () => {
      const mockResponse = { categories: [], total: 0, active_count: 0 };
      mockApiClient.get.mockResolvedValue(mockResponse);

      await CategoriesService.getCategories(true);

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v1/categories?active_only=true');
    });
  });

  describe('createCategory', () => {
    it('should call POST API with correct data', async () => {
      const createData = {
        name: 'Sports',
        keywords: ['football', 'basketball'],
        exclude_keywords: ['gambling'],
        is_active: true
      };
      
      const mockResponse = {
        id: '2',
        ...createData,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z'
      };

      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await CategoriesService.createCategory(createData);

      expect(mockApiClient.post).toHaveBeenCalledWith('/api/v1/categories', createData);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('updateCategory', () => {
    it('should call PUT API with correct ID and data', async () => {
      const updateData = {
        name: 'Updated Name',
        is_active: false
      };
      
      const mockResponse = {
        id: '1',
        name: 'Updated Name',
        keywords: ['old', 'keywords'],
        exclude_keywords: [],
        is_active: false,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-02T00:00:00Z'
      };

      mockApiClient.put.mockResolvedValue(mockResponse);

      const result = await CategoriesService.updateCategory('1', updateData);

      expect(mockApiClient.put).toHaveBeenCalledWith('/api/v1/categories/1', updateData);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('deleteCategory', () => {
    it('should call DELETE API with correct ID', async () => {
      mockApiClient.delete.mockResolvedValue(undefined);

      await CategoriesService.deleteCategory('1');

      expect(mockApiClient.delete).toHaveBeenCalledWith('/api/v1/categories/1');
    });
  });

  describe('toggleCategoryStatus', () => {
    it('should call PATCH API with is_active status', async () => {
      const mockResponse = {
        id: '1',
        name: 'Test',
        keywords: ['test'],
        exclude_keywords: [],
        is_active: false,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-02T00:00:00Z'
      };

      mockApiClient.patch.mockResolvedValue(mockResponse);

      const result = await CategoriesService.toggleCategoryStatus('1', false);

      expect(mockApiClient.patch).toHaveBeenCalledWith('/api/v1/categories/1', { is_active: false });
      expect(result).toEqual(mockResponse);
    });
  });
});