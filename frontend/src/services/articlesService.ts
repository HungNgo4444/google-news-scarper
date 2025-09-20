import { apiClient } from './api';

// Article interfaces matching the backend API
export interface ArticleResponse {
  id: string;
  title: string;
  content: string | null;
  author: string | null;
  publish_date: string | null;
  source_url: string;
  image_url: string | null;
  url_hash: string;
  content_hash: string | null;
  last_seen: string;
  crawl_job_id: string | null;
  keywords_matched: string[];
  relevance_score: number;
  created_at: string;
  updated_at: string;
}

export interface ArticleListResponse {
  articles: ArticleResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ArticleSearchParams {
  job_id?: string;
  category_id?: string;
  search?: string;
  keywords?: string;
  min_relevance_score?: number;
  from_date?: string;
  to_date?: string;
  page?: number;
  size?: number;
}

export interface ArticleExportRequest {
  job_id?: string;
  category_id?: string;
  format: 'json' | 'csv' | 'xlsx';
  fields?: string[];
}

export class ArticlesService {
  private static baseUrl = '/api/v1/articles';

  static async getArticles(params: ArticleSearchParams = {}): Promise<ArticleListResponse> {
    const queryParams = new URLSearchParams();

    // Add all provided parameters to query string
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        queryParams.append(key, String(value));
      }
    });

    const url = queryParams.toString()
      ? `${this.baseUrl}?${queryParams.toString()}`
      : this.baseUrl;

    return apiClient.get<ArticleListResponse>(url);
  }

  static async getArticle(articleId: string): Promise<ArticleResponse> {
    return apiClient.get<ArticleResponse>(`${this.baseUrl}/${articleId}`);
  }

  static async exportArticles(request: ArticleExportRequest): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }

    return response.blob();
  }

  static async getArticleStats(): Promise<{
    total_articles: number;
    articles_by_job: Record<string, number>;
    articles_by_category: Record<string, number>;
    recent_articles_count: number;
    average_relevance_score: number;
  }> {
    return apiClient.get<any>(`${this.baseUrl}/stats`);
  }
}