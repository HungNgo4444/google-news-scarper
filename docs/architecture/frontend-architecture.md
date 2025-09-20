# Frontend Architecture

## Overview

The frontend architecture for the Google News Scraper job-centric enhancement is built on React 19 with TypeScript, following modern component-based patterns with efficient state management and API integration. The architecture supports the primary workflows of job management, article viewing, and integrated category scheduling.

## Component Architecture

### Component Organization

```
src/
├── components/           # Reusable UI components
│   ├── ui/              # Shadcn UI base components
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── tabs.tsx
│   │   └── badge.tsx
│   ├── jobs/            # Job-related components
│   │   ├── JobsList.tsx
│   │   ├── JobArticlesModal.tsx
│   │   ├── JobEditModal.tsx
│   │   ├── JobStatusBadge.tsx
│   │   ├── PriorityControls.tsx
│   │   └── JobActionButtons.tsx
│   ├── articles/        # Article components
│   │   ├── ArticleList.tsx
│   │   ├── ArticleExport.tsx
│   │   ├── ArticlePreview.tsx
│   │   ├── ArticleSearchFilters.tsx
│   │   └── ArticleCard.tsx
│   ├── categories/      # Enhanced category components
│   │   ├── CategoryForm.tsx
│   │   ├── CategoriesList.tsx
│   │   ├── ScheduleTab.tsx
│   │   ├── ScheduleHistory.tsx
│   │   └── ScheduleConfigModal.tsx
│   └── common/          # Shared components
│       ├── LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx
│       ├── ConfirmDialog.tsx
│       ├── DataTable.tsx
│       └── StatusIndicator.tsx
├── hooks/               # Custom React hooks
│   ├── useJobs.ts
│   ├── useArticles.ts
│   ├── useSchedules.ts
│   ├── useRealTimeUpdates.ts
│   ├── useExport.ts
│   └── useDebounce.ts
├── services/            # API client services
│   ├── apiClient.ts
│   ├── JobsService.ts
│   ├── ArticlesService.ts
│   ├── CategoriesService.ts
│   └── SchedulesService.ts
├── types/               # TypeScript type definitions
│   ├── job.ts
│   ├── article.ts
│   ├── category.ts
│   ├── schedule.ts
│   └── api.ts
├── utils/               # Helper functions
│   ├── formatters.ts
│   ├── dateUtils.ts
│   ├── exportUtils.ts
│   └── validation.ts
├── contexts/            # React Context providers
│   ├── JobsContext.tsx
│   ├── ArticlesContext.tsx
│   ├── NotificationContext.tsx
│   └── ThemeContext.tsx
├── pages/               # Page components
│   ├── JobsPage.tsx
│   ├── CategoriesPage.tsx
│   ├── ArticlesPage.tsx
│   └── DashboardPage.tsx
└── styles/              # Global styles
    ├── globals.css
    ├── components.css
    └── tailwind.config.js
```

### Component Template

```typescript
import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CrawlJob, CrawlJobStatus } from '@/types/job';
import { useJobs } from '@/hooks/useJobs';
import { useNotifications } from '@/hooks/useNotifications';

interface JobActionButtonsProps {
  job: CrawlJob;
  onJobUpdate?: (job: CrawlJob) => void;
  className?: string;
}

export const JobActionButtons: React.FC<JobActionButtonsProps> = ({
  job,
  onJobUpdate,
  className
}) => {
  const { updateJobPriority, deleteJob } = useJobs();
  const { showSuccess, showError } = useNotifications();
  const [isUpdating, setIsUpdating] = useState(false);

  const handleRunNow = useCallback(async () => {
    if (job.status !== CrawlJobStatus.PENDING) {
      showError('Only pending jobs can be prioritized');
      return;
    }

    setIsUpdating(true);
    try {
      const updatedJob = await updateJobPriority(job.id, 10);
      showSuccess('Job priority updated - will run shortly');
      onJobUpdate?.(updatedJob);
    } catch (error) {
      showError('Failed to update job priority');
    } finally {
      setIsUpdating(false);
    }
  }, [job, updateJobPriority, showSuccess, showError, onJobUpdate]);

  const canRunNow = job.status === CrawlJobStatus.PENDING;
  const canEdit = job.status !== CrawlJobStatus.RUNNING;
  const canDelete = job.status !== CrawlJobStatus.RUNNING;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {canRunNow && (
        <Button
          size="sm"
          variant="default"
          onClick={handleRunNow}
          disabled={isUpdating}
          className="bg-green-600 hover:bg-green-700"
        >
          🚀 Run Now
        </Button>
      )}

      {canEdit && (
        <Button
          size="sm"
          variant="outline"
          onClick={() => console.log('Edit job', job.id)}
        >
          ✏️ Edit
        </Button>
      )}

      <Button
        size="sm"
        variant="outline"
        onClick={() => console.log('View articles', job.id)}
      >
        👁️ View Articles
      </Button>

      {canDelete && (
        <Button
          size="sm"
          variant="destructive"
          onClick={() => console.log('Delete job', job.id)}
        >
          🗑️ Delete
        </Button>
      )}

      {job.priority > 0 && (
        <Badge variant="secondary" className="ml-2">
          ⚡ Priority: {job.priority}
        </Badge>
      )}
    </div>
  );
};

export default JobActionButtons;
```

## State Management Architecture

### State Structure

```typescript
// Global Application State using React Context
interface AppState {
  user: UserState;
  jobs: JobsState;
  articles: ArticlesState;
  categories: CategoriesState;
  schedules: SchedulesState;
  ui: UIState;
}

interface JobsState {
  jobs: CrawlJob[];
  currentJob: CrawlJob | null;
  loading: boolean;
  error: string | null;
  filters: JobFilters;
  pagination: PaginationState;
  realTimeUpdates: boolean;
}

interface ArticlesState {
  articles: Article[];
  loading: boolean;
  error: string | null;
  filters: ArticleFilters;
  exportStatus: ExportStatus;
  selectedJobArticles: Map<string, Article[]>; // Keyed by job_id
}

interface SchedulesState {
  schedules: Map<string, CategorySchedule>; // Keyed by category_id
  loading: boolean;
  error: string | null;
  activeSchedules: string[]; // Array of category_ids with active schedules
}

interface UIState {
  modals: {
    jobArticles: { isOpen: boolean; jobId: string | null };
    jobEdit: { isOpen: boolean; jobId: string | null };
    scheduleConfig: { isOpen: boolean; categoryId: string | null };
    confirmDialog: { isOpen: boolean; config: ConfirmConfig | null };
  };
  notifications: Notification[];
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
}
```

### State Management Patterns

#### Context Providers

```typescript
// JobsContext.tsx
import React, { createContext, useContext, useReducer, useCallback } from 'react';
import { CrawlJob, JobFilters, PaginationState } from '@/types/job';
import { JobsService } from '@/services/JobsService';

interface JobsContextType {
  // State
  jobs: CrawlJob[];
  loading: boolean;
  error: string | null;
  filters: JobFilters;
  pagination: PaginationState;

  // Actions
  fetchJobs: (filters?: JobFilters) => Promise<void>;
  updateJobPriority: (jobId: string, priority: number) => Promise<CrawlJob>;
  deleteJob: (jobId: string) => Promise<void>;
  setFilters: (filters: Partial<JobFilters>) => void;
  clearError: () => void;
}

const JobsContext = createContext<JobsContextType | undefined>(undefined);

export const JobsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(jobsReducer, initialJobsState);

  const fetchJobs = useCallback(async (filters?: JobFilters) => {
    dispatch({ type: 'FETCH_JOBS_START' });
    try {
      const response = await JobsService.getJobs({
        ...state.filters,
        ...filters,
        page: state.pagination.page,
        size: state.pagination.size
      });

      dispatch({
        type: 'FETCH_JOBS_SUCCESS',
        payload: {
          jobs: response.items,
          pagination: {
            page: response.page,
            pages: response.pages,
            total: response.total,
            size: response.size
          }
        }
      });
    } catch (error) {
      dispatch({
        type: 'FETCH_JOBS_ERROR',
        payload: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }, [state.filters, state.pagination]);

  const updateJobPriority = useCallback(async (jobId: string, priority: number) => {
    try {
      const updatedJob = await JobsService.updateJobPriority(jobId, priority);
      dispatch({ type: 'UPDATE_JOB_SUCCESS', payload: updatedJob });
      return updatedJob;
    } catch (error) {
      dispatch({
        type: 'UPDATE_JOB_ERROR',
        payload: error instanceof Error ? error.message : 'Update failed'
      });
      throw error;
    }
  }, []);

  const value = {
    ...state,
    fetchJobs,
    updateJobPriority,
    deleteJob,
    setFilters: (filters: Partial<JobFilters>) =>
      dispatch({ type: 'SET_FILTERS', payload: filters }),
    clearError: () => dispatch({ type: 'CLEAR_ERROR' })
  };

  return (
    <JobsContext.Provider value={value}>
      {children}
    </JobsContext.Provider>
  );
};

export const useJobs = () => {
  const context = useContext(JobsContext);
  if (!context) {
    throw new Error('useJobs must be used within JobsProvider');
  }
  return context;
};
```

#### Custom Hooks for Complex Logic

```typescript
// useJobArticles.ts
import { useState, useEffect, useCallback } from 'react';
import { Article, ArticleFilters, PaginatedResponse } from '@/types';
import { ArticlesService } from '@/services/ArticlesService';
import { useDebounce } from './useDebounce';

interface UseJobArticlesOptions {
  jobId: string;
  autoFetch?: boolean;
  debounceMs?: number;
}

export const useJobArticles = ({
  jobId,
  autoFetch = true,
  debounceMs = 300
}: UseJobArticlesOptions) => {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<ArticleFilters>({ job_id: jobId });
  const [pagination, setPagination] = useState({
    page: 1,
    pages: 1,
    total: 0,
    size: 20
  });

  const debouncedFilters = useDebounce(filters, debounceMs);

  const fetchArticles = useCallback(async (newFilters?: Partial<ArticleFilters>) => {
    setLoading(true);
    setError(null);

    try {
      const params = { ...debouncedFilters, ...newFilters };
      const response = await ArticlesService.getArticles(params);

      setArticles(response.items);
      setPagination({
        page: response.page,
        pages: response.pages,
        total: response.total,
        size: response.size
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch articles';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [debouncedFilters]);

  const exportArticles = useCallback(async (format: 'json' | 'csv' | 'xlsx') => {
    try {
      const blob = await ArticlesService.exportArticles(jobId, format);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `articles_${jobId}_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
      return false;
    }
  }, [jobId]);

  const updateFilters = useCallback((newFilters: Partial<ArticleFilters>) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
  }, []);

  const changePage = useCallback((page: number) => {
    setPagination(prev => ({ ...prev, page }));
    fetchArticles({ page });
  }, [fetchArticles]);

  // Auto-fetch on mount and filter changes
  useEffect(() => {
    if (autoFetch && jobId) {
      fetchArticles();
    }
  }, [fetchArticles, autoFetch, jobId]);

  return {
    articles,
    loading,
    error,
    filters,
    pagination,
    fetchArticles,
    exportArticles,
    updateFilters,
    changePage,
    refetch: () => fetchArticles()
  };
};
```

## Routing Architecture

### Route Organization

```typescript
// App.tsx with React Router setup
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';

// Lazy load pages for code splitting
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const JobsPage = lazy(() => import('@/pages/JobsPage'));
const JobDetailPage = lazy(() => import('@/pages/JobDetailPage'));
const CategoriesPage = lazy(() => import('@/pages/CategoriesPage'));
const ArticlesPage = lazy(() => import('@/pages/ArticlesPage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            {/* Dashboard */}
            <Route path="/" element={<DashboardPage />} />

            {/* Jobs Management */}
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/jobs/:jobId/articles" element={<JobArticlesPage />} />

            {/* Categories with Scheduling */}
            <Route path="/categories" element={<CategoriesPage />} />
            <Route path="/categories/:categoryId" element={<CategoryDetailPage />} />
            <Route path="/categories/:categoryId/schedule" element={<CategorySchedulePage />} />

            {/* Global Articles View */}
            <Route path="/articles" element={<ArticlesPage />} />

            {/* Settings */}
            <Route path="/settings" element={<SettingsPage />} />

            {/* Redirects */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </div>
    </BrowserRouter>
  );
}
```

### Protected Route Pattern

```typescript
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'admin' | 'user';
  fallbackPath?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
  fallbackPath = '/login'
}) => {
  const { user, loading, isAuthenticated } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={fallbackPath}
        state={{ from: location.pathname }}
        replace
      />
    );
  }

  if (requiredRole && user?.role !== requiredRole) {
    return (
      <Navigate
        to="/unauthorized"
        state={{ requiredRole, currentRole: user?.role }}
        replace
      />
    );
  }

  return <>{children}</>;
};

// Usage in routing
<Route
  path="/jobs/:jobId/delete"
  element={
    <ProtectedRoute requiredRole="admin">
      <JobDeletePage />
    </ProtectedRoute>
  }
/>
```

## Frontend Services Layer

### API Client Setup

```typescript
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { ApiError } from '@/types/api';

class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor for auth token and correlation ID
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token
        const token = this.getAuthToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // Add correlation ID for request tracing
        const correlationId = this.generateCorrelationId();
        config.headers['X-Correlation-ID'] = correlationId;

        // Log API calls in development
        if (import.meta.env.DEV) {
          console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
            params: config.params,
            data: config.data,
            correlationId
          });
        }

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling and logging
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        // Log successful responses in development
        if (import.meta.env.DEV) {
          console.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`, {
            status: response.status,
            correlationId: response.headers['x-correlation-id']
          });
        }
        return response;
      },
      (error) => {
        const correlationId = error.response?.headers?.['x-correlation-id'];

        // Handle different error types
        if (error.response?.status === 401) {
          this.handleUnauthorized();
        } else if (error.response?.status === 403) {
          this.handleForbidden();
        }

        // Log errors
        console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
          status: error.response?.status,
          message: error.response?.data?.error?.message,
          correlationId
        });

        return Promise.reject(this.transformError(error));
      }
    );
  }

  private getAuthToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  private generateCorrelationId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private handleUnauthorized() {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
  }

  private handleForbidden() {
    // Could show a toast notification or redirect to access denied page
    console.warn('Access denied - insufficient permissions');
  }

  private transformError(error: any): ApiError {
    if (error.response?.data?.error) {
      return error.response.data.error;
    }

    // Fallback for network errors
    return {
      code: 'NETWORK_ERROR',
      message: error.message || 'Network connection failed',
      timestamp: new Date().toISOString(),
      requestId: 'unknown'
    };
  }

  // Generic HTTP methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  // File download method for exports
  async downloadFile(url: string, params?: any): Promise<Blob> {
    const response = await this.client.post(url, params, {
      responseType: 'blob'
    });
    return response.data;
  }
}

export const apiClient = new ApiClient(
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
);
```

### Service Example

```typescript
// JobsService.ts
import { apiClient } from './apiClient';
import {
  CrawlJob,
  PaginatedResponse,
  JobFilters,
  JobUpdateRequest,
  PriorityUpdateRequest
} from '@/types';

export class JobsService {
  private static readonly BASE_PATH = '/jobs';

  static async getJobs(params?: JobFilters & {
    page?: number;
    size?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }): Promise<PaginatedResponse<CrawlJob>> {
    return apiClient.get<PaginatedResponse<CrawlJob>>(this.BASE_PATH, { params });
  }

  static async getJob(jobId: string): Promise<CrawlJob> {
    return apiClient.get<CrawlJob>(`${this.BASE_PATH}/${jobId}`);
  }

  static async createJob(request: {
    category_id: string;
    priority?: number;
    job_metadata?: Record<string, any>;
  }): Promise<CrawlJob> {
    return apiClient.post<CrawlJob>(this.BASE_PATH, request);
  }

  static async updateJob(jobId: string, updates: JobUpdateRequest): Promise<CrawlJob> {
    return apiClient.patch<CrawlJob>(`${this.BASE_PATH}/${jobId}`, updates);
  }

  static async updateJobPriority(jobId: string, priority: number): Promise<CrawlJob> {
    const request: PriorityUpdateRequest = { priority };
    return apiClient.patch<CrawlJob>(`${this.BASE_PATH}/${jobId}/priority`, request);
  }

  static async deleteJob(jobId: string, force = false): Promise<{
    message: string;
    impact: { articles_affected: number; dependent_schedules: string[] }
  }> {
    return apiClient.delete(`${this.BASE_PATH}/${jobId}`, {
      params: { force }
    });
  }

  // Real-time job monitoring
  static async subscribeToJobUpdates(
    jobId: string,
    callback: (job: CrawlJob) => void
  ): Promise<() => void> {
    // WebSocket connection for real-time updates
    const ws = new WebSocket(`${import.meta.env.VITE_WS_URL}/jobs/${jobId}/updates`);

    ws.onmessage = (event) => {
      const jobUpdate = JSON.parse(event.data);
      callback(jobUpdate);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    // Return cleanup function
    return () => {
      ws.close();
    };
  }
}
```

## Performance Optimization

### Code Splitting and Lazy Loading

```typescript
// Lazy load heavy components
const JobArticlesModal = lazy(() => import('@/components/jobs/JobArticlesModal'));
const ArticleExport = lazy(() => import('@/components/articles/ArticleExport'));

// Use Suspense for loading states
<Suspense fallback={<div>Loading articles...</div>}>
  <JobArticlesModal jobId={jobId} isOpen={isOpen} onClose={onClose} />
</Suspense>
```

### Memoization and Optimization

```typescript
// Memoize expensive calculations
const MemoizedJobsList = React.memo(JobsList, (prevProps, nextProps) => {
  return (
    prevProps.jobs === nextProps.jobs &&
    prevProps.loading === nextProps.loading &&
    prevProps.filters === nextProps.filters
  );
});

// Use useMemo for derived state
const sortedJobs = useMemo(() => {
  return jobs.sort((a, b) => {
    if (a.priority !== b.priority) {
      return b.priority - a.priority; // Higher priority first
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}, [jobs]);

// Debounce search inputs
const debouncedSearch = useDebounce(searchTerm, 300);
```

### Virtual Scrolling for Large Lists

```typescript
import { FixedSizeList as List } from 'react-window';

const VirtualizedArticleList: React.FC<{ articles: Article[] }> = ({ articles }) => {
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => (
    <div style={style}>
      <ArticleCard article={articles[index]} />
    </div>
  );

  return (
    <List
      height={600}
      itemCount={articles.length}
      itemSize={120}
      width="100%"
    >
      {Row}
    </List>
  );
};
```

## Error Boundaries and Error Handling

```typescript
// ErrorBoundary.tsx
class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ComponentType<{ error: Error }> },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error boundary caught an error:', error, errorInfo);

    // Send error to monitoring service
    if (import.meta.env.PROD) {
      // Sentry.captureException(error, { extra: errorInfo });
    }
  }

  render() {
    if (this.state.hasError) {
      const FallbackComponent = this.props.fallback || DefaultErrorFallback;
      return <FallbackComponent error={this.state.error!} />;
    }

    return this.props.children;
  }
}

const DefaultErrorFallback: React.FC<{ error: Error }> = ({ error }) => (
  <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
    <h2 className="text-lg font-semibold text-red-800 mb-2">
      Something went wrong
    </h2>
    <p className="text-red-700 mb-4">
      {error.message}
    </p>
    <Button onClick={() => window.location.reload()}>
      Reload Page
    </Button>
  </div>
);
```

This frontend architecture provides a scalable, maintainable foundation for the job-centric article management enhancement while leveraging modern React patterns and ensuring excellent user experience.