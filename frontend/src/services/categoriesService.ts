import type {
  Category,
  CreateCategoryRequest,
  UpdateCategoryRequest,
  UpdateScheduleConfigRequest,
  ScheduleConfigResponse
} from '../types/shared';
import { apiClient } from './api';

export class CategoriesService {
  private static baseUrl = '/api/v1/categories';

  static async getCategories(activeOnly?: boolean): Promise<Category[]> {
    const params = new URLSearchParams();
    if (activeOnly !== undefined) {
      params.append('active_only', activeOnly.toString());
    }

    const url = params.toString()
      ? `${this.baseUrl}?${params.toString()}`
      : this.baseUrl;

    const response = await apiClient.get<{categories: Category[], total: number, active_count: number}>(url);
    return response.categories;
  }

  static async createCategory(data: CreateCategoryRequest): Promise<Category> {
    return apiClient.post<Category>(this.baseUrl, data);
  }

  static async updateCategory(id: string, data: UpdateCategoryRequest): Promise<Category> {
    return apiClient.put<Category>(`${this.baseUrl}/${id}`, data);
  }

  static async deleteCategory(id: string): Promise<void> {
    return apiClient.delete(`${this.baseUrl}/${id}`);
  }

  static async toggleCategoryStatus(id: string, isActive: boolean): Promise<Category> {
    return apiClient.patch<Category>(`${this.baseUrl}/${id}`, { is_active: isActive });
  }

  static async updateScheduleConfig(
    categoryId: string,
    config: UpdateScheduleConfigRequest
  ): Promise<ScheduleConfigResponse> {
    return apiClient.patch<ScheduleConfigResponse>(
      `${this.baseUrl}/${categoryId}/schedule`,
      config
    );
  }

  static async getScheduleConfig(categoryId: string): Promise<ScheduleConfigResponse> {
    return apiClient.get<ScheduleConfigResponse>(`${this.baseUrl}/${categoryId}/schedule`);
  }
}