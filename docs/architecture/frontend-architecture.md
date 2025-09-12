# Frontend Architecture (Optional)

Define frontend-specific architecture details cho optional management interface.

## Component Architecture

### Component Organization

```text
web/src/
├── components/           # Reusable UI components
│   ├── ui/              # Basic UI primitives
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Table.tsx
│   │   ├── Modal.tsx
│   │   └── Card.tsx
│   ├── forms/           # Form components
│   │   ├── CategoryForm.tsx
│   │   ├── KeywordInput.tsx
│   │   └── SearchForm.tsx
│   └── layout/          # Layout components
│       ├── Header.tsx
│       ├── Sidebar.tsx
│       ├── Layout.tsx
│       └── Navigation.tsx
├── pages/               # Page components/routes
│   ├── Dashboard.tsx
│   ├── Categories.tsx
│   ├── Articles.tsx
│   ├── CrawlJobs.tsx
│   └── Settings.tsx
├── hooks/               # Custom React hooks
│   ├── useCategories.tsx
│   ├── useArticles.tsx
│   ├── useCrawlJobs.tsx
│   └── useApi.tsx
├── services/            # API client services
│   ├── api.ts
│   ├── categoryService.ts
│   ├── articleService.ts
│   └── jobService.ts
├── stores/              # State management
│   ├── categoryStore.ts
│   ├── articleStore.ts
│   └── uiStore.ts
├── types/               # TypeScript definitions
│   ├── api.ts
│   ├── models.ts
│   └── ui.ts
├── utils/               # Utilities
│   ├── dateFormat.ts
│   ├── validation.ts
│   └── constants.ts
└── styles/              # Styling
    ├── globals.css
    ├── components.css
    └── variables.css
```

### Component Template Pattern

```typescript
// Component template pattern
interface CategoryCardProps {
  category: Category;
  onEdit?: (category: Category) => void;
  onDelete?: (categoryId: string) => void;
  onTriggerCrawl?: (categoryId: string) => void;
}

export function CategoryCard({ 
  category, 
  onEdit, 
  onDelete, 
  onTriggerCrawl 
}: CategoryCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  
  const handleTriggerCrawl = async () => {
    if (!onTriggerCrawl) return;
    
    setIsLoading(true);
    try {
      await onTriggerCrawl(category.id);
      // Show success toast
      toast.success(`Crawl triggered for ${category.name}`);
    } catch (error) {
      // Show error toast
      toast.error(`Failed to trigger crawl: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="category-card">
      <Card.Header>
        <h3>{category.name}</h3>
        <StatusBadge active={category.is_active} />
      </Card.Header>
      
      <Card.Body>
        <div className="keywords">
          {category.keywords.map(keyword => (
            <span key={keyword} className="keyword-tag">
              {keyword}
            </span>
          ))}
        </div>
        
        <div className="metadata">
          <span>Created: {formatDate(category.created_at)}</span>
          <span>Updated: {formatDate(category.updated_at)}</span>
        </div>
      </Card.Body>
      
      <Card.Footer>
        <div className="actions">
          <Button 
            variant="secondary" 
            onClick={() => onEdit?.(category)}
          >
            Edit
          </Button>
          <Button 
            variant="primary"
            onClick={handleTriggerCrawl} 
            disabled={isLoading}
          >
            {isLoading ? 'Crawling...' : 'Trigger Crawl'}
          </Button>
          <Button 
            variant="danger" 
            onClick={() => onDelete?.(category.id)}
            className="ml-auto"
          >
            Delete
          </Button>
        </div>
      </Card.Footer>
    </Card>
  );
}
```

## State Management Architecture

### Zustand Store Structure

```typescript
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { Category, Article, CrawlJob } from '../types/models';

interface AppState {
  // Categories state
  categories: Category[];
  selectedCategory: Category | null;
  categoriesLoading: boolean;
  categoriesError: string | null;
  
  // Articles state  
  articles: Article[];
  articlesLoading: boolean;
  articlesError: string | null;
  articlesFilters: ArticleFilters;
  articlesPagination: {
    page: number;
    size: number;
    total: number;
  };
  
  // Crawl jobs state
  crawlJobs: CrawlJob[];
  jobsLoading: boolean;
  jobsError: string | null;
  
  // UI state
  notifications: Notification[];
  modals: {
    editCategory: boolean;
    deleteConfirm: boolean;
    createCategory: boolean;
  };
  sidebarOpen: boolean;
}

interface AppActions {
  // Category actions
  fetchCategories: () => Promise<void>;
  createCategory: (data: CreateCategoryRequest) => Promise<void>;
  updateCategory: (id: string, data: UpdateCategoryRequest) => Promise<void>;
  deleteCategory: (id: string) => Promise<void>;
  triggerCrawl: (categoryId: string) => Promise<void>;
  setSelectedCategory: (category: Category | null) => void;
  
  // Article actions
  fetchArticles: (filters?: ArticleFilters) => Promise<void>;
  setArticleFilters: (filters: ArticleFilters) => void;
  setArticlesPage: (page: number) => void;
  
  // Job actions
  fetchCrawlJobs: (filters?: JobFilters) => Promise<void>;
  
  // UI actions
  showNotification: (notification: Omit<Notification, 'id'>) => void;
  dismissNotification: (id: string) => void;
  openModal: (modal: keyof AppState['modals']) => void;
  closeModal: (modal: keyof AppState['modals']) => void;
  toggleSidebar: () => void;
  
  // Error handling
  setError: (section: string, error: string | null) => void;
  clearErrors: () => void;
}

type AppStore = AppState & AppActions;

export const useAppStore = create<AppStore>()(
  devtools((set, get) => ({
    // Initial state
    categories: [],
    selectedCategory: null,
    categoriesLoading: false,
    categoriesError: null,
    
    articles: [],
    articlesLoading: false,
    articlesError: null,
    articlesFilters: {},
    articlesPagination: { page: 1, size: 20, total: 0 },
    
    crawlJobs: [],
    jobsLoading: false,
    jobsError: null,
    
    notifications: [],
    modals: {
      editCategory: false,
      deleteConfirm: false,
      createCategory: false,
    },
    sidebarOpen: true,
    
    // Actions implementation
    fetchCategories: async () => {
      set({ categoriesLoading: true, categoriesError: null });
      try {
        const categories = await categoryService.getAll();
        set({ categories, categoriesLoading: false });
      } catch (error) {
        set({ 
          categoriesError: error.message, 
          categoriesLoading: false 
        });
      }
    },
    
    createCategory: async (data) => {
      try {
        const newCategory = await categoryService.create(data);
        set(state => ({ 
          categories: [...state.categories, newCategory]
        }));
        get().showNotification({
          type: 'success',
          message: `Category "${data.name}" created successfully`
        });
      } catch (error) {
        get().showNotification({
          type: 'error',
          message: `Failed to create category: ${error.message}`
        });
        throw error;
      }
    },
    
    triggerCrawl: async (categoryId) => {
      try {
        const job = await categoryService.triggerCrawl(categoryId);
        set(state => ({ 
          crawlJobs: [job, ...state.crawlJobs]
        }));
        get().showNotification({
          type: 'success',
          message: 'Crawl job triggered successfully'
        });
      } catch (error) {
        get().showNotification({
          type: 'error',
          message: `Failed to trigger crawl: ${error.message}`
        });
        throw error;
      }
    },
    
    showNotification: (notification) => {
      const id = Math.random().toString(36).substr(2, 9);
      const newNotification = { ...notification, id };
      
      set(state => ({
        notifications: [...state.notifications, newNotification]
      }));
      
      // Auto dismiss after 5 seconds
      if (notification.type !== 'error') {
        setTimeout(() => {
          get().dismissNotification(id);
        }, 5000);
      }
    },
    
    dismissNotification: (id) => {
      set(state => ({
        notifications: state.notifications.filter(n => n.id !== id)
      }));
    },
    
    openModal: (modal) => {
      set(state => ({
        modals: { ...state.modals, [modal]: true }
      }));
    },
    
    closeModal: (modal) => {
      set(state => ({
        modals: { ...state.modals, [modal]: false }
      }));
    },
    
    setError: (section, error) => {
      set({ [`${section}Error`]: error });
    },
    
    clearErrors: () => {
      set({
        categoriesError: null,
        articlesError: null,
        jobsError: null,
      });
    },
  }))
);
```

## Routing Architecture

### Route Organization

```typescript
// routes/index.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Dashboard from '../pages/Dashboard';
import Categories from '../pages/Categories';
import Articles from '../pages/Articles';
import CrawlJobs from '../pages/CrawlJobs';
import Settings from '../pages/Settings';
import ErrorBoundary from '../components/ErrorBoundary';

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    errorElement: <ErrorBoundary />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />
      },
      {
        path: "dashboard",
        element: <Dashboard />
      },
      {
        path: "categories",
        element: <Categories />
      },
      {
        path: "articles",
        element: <Articles />
      },
      {
        path: "crawl-jobs",
        element: <CrawlJobs />
      },
      {
        path: "settings",
        element: <Settings />
      }
    ]
  }
]);

// Route guards (future authentication)
interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAppStore(state => state.isAuthenticated);
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
}
```

## API Client Architecture

### API Service Layer

```typescript
// services/api.ts
class ApiClient {
  private baseURL: string;
  private timeout: number;
  
  constructor(baseURL = '/api/v1', timeout = 10000) {
    this.baseURL = baseURL;
    this.timeout = timeout;
  }
  
  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      signal: AbortSignal.timeout(this.timeout),
    };
    
    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
          response.status,
          errorData.error?.message || response.statusText,
          errorData
        );
      }
      
      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      
      // Handle network errors, timeouts, etc.
      throw new ApiError(
        0,
        'Network error or timeout occurred',
        { originalError: error.message }
      );
    }
  }
  
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }
  
  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }
  
  async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT', 
      body: JSON.stringify(data),
    });
  }
  
  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
  
  get isRetryable(): boolean {
    return this.status >= 500 || this.status === 0;
  }
}

export const apiClient = new ApiClient();
```

### Service Implementation

```typescript
// services/categoryService.ts
export class CategoryService {
  static async getAll(activeOnly: boolean = true): Promise<Category[]> {
    const params = new URLSearchParams({ 
      active_only: activeOnly.toString() 
    });
    return apiClient.get<Category[]>(`/categories?${params}`);
  }
  
  static async getById(id: string): Promise<Category> {
    return apiClient.get<Category>(`/categories/${id}`);
  }
  
  static async create(data: CreateCategoryRequest): Promise<Category> {
    return apiClient.post<Category>('/categories', data);
  }
  
  static async update(
    id: string, 
    data: UpdateCategoryRequest
  ): Promise<Category> {
    return apiClient.put<Category>(`/categories/${id}`, data);
  }
  
  static async delete(id: string): Promise<void> {
    return apiClient.delete<void>(`/categories/${id}`);
  }
  
  static async triggerCrawl(id: string): Promise<CrawlJob> {
    return apiClient.post<CrawlJob>(`/categories/${id}/trigger-crawl`);
  }
}
```

## Custom Hooks

### Data Fetching Hooks

```typescript
// hooks/useCategories.tsx
export function useCategories() {
  const { 
    categories, 
    categoriesLoading, 
    categoriesError,
    fetchCategories,
    createCategory,
    updateCategory,
    deleteCategory,
    triggerCrawl
  } = useAppStore();
  
  // Auto-fetch on mount
  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);
  
  // Optimistic updates
  const optimisticCreate = async (data: CreateCategoryRequest) => {
    const optimisticCategory = {
      id: 'temp-' + Date.now(),
      ...data,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    
    // Add optimistic update
    useAppStore.setState(state => ({
      categories: [...state.categories, optimisticCategory]
    }));
    
    try {
      await createCategory(data);
      // Remove optimistic update, real data from server
      useAppStore.setState(state => ({
        categories: state.categories.filter(c => c.id !== optimisticCategory.id)
      }));
    } catch (error) {
      // Rollback optimistic update
      useAppStore.setState(state => ({
        categories: state.categories.filter(c => c.id !== optimisticCategory.id)
      }));
      throw error;
    }
  };
  
  return {
    categories,
    loading: categoriesLoading,
    error: categoriesError,
    refetch: fetchCategories,
    create: optimisticCreate,
    update: updateCategory,
    delete: deleteCategory,
    triggerCrawl,
  };
}

// hooks/useApi.tsx - Generic API hook
export function useApi<T>(
  fetchFn: () => Promise<T>,
  dependencies: any[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);
  
  useEffect(() => {
    refetch();
  }, dependencies);
  
  return { data, loading, error, refetch };
}
```

## UI Components

### Reusable Components

```typescript
// components/ui/Button.tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: React.ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  children,
  className = '',
  ...props
}: ButtonProps) {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';
  
  const variantClasses = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    ghost: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:ring-gray-500'
  };
  
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg'
  };
  
  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className} ${
        (disabled || loading) ? 'opacity-50 cursor-not-allowed' : ''
      }`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {children}
    </button>
  );
}
```

## Performance Optimization

### Code Splitting

```typescript
// Lazy load pages
import { lazy, Suspense } from 'react';
import LoadingSpinner from './components/LoadingSpinner';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Categories = lazy(() => import('./pages/Categories'));
const Articles = lazy(() => import('./pages/Articles'));

// Wrap trong Suspense
function App() {
  return (
    <Router>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/articles" element={<Articles />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
```

### Memoization

```typescript
// Optimize expensive calculations
const MemoizedCategoryCard = memo(CategoryCard, (prevProps, nextProps) => {
  return (
    prevProps.category.id === nextProps.category.id &&
    prevProps.category.updated_at === nextProps.category.updated_at
  );
});

// Optimize lists
const CategoryList = memo(function CategoryList({ categories }) {
  const sortedCategories = useMemo(() => {
    return categories.sort((a, b) => a.name.localeCompare(b.name));
  }, [categories]);

  return (
    <div className="category-list">
      {sortedCategories.map(category => (
        <MemoizedCategoryCard 
          key={category.id} 
          category={category} 
        />
      ))}
    </div>
  );
});
```

## Build Configuration

### Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  
  build: {
    target: 'esnext',
    minify: 'terser',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['zustand', 'react-router-dom'],
        },
      },
    },
  },
  
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

## Design Principles

1. **Component Composition:** Small, reusable components
2. **Type Safety:** TypeScript throughout cho better DX
3. **Performance First:** Lazy loading, memoization, code splitting
4. **Accessibility:** WCAG compliance for UI components
5. **Error Boundaries:** Graceful error handling
6. **Responsive Design:** Mobile-first approach
7. **Progressive Enhancement:** Works without JavaScript
8. **State Management:** Minimal, focused state với Zustand