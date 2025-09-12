# Data Models

Định nghĩa các core data models dựa trên PRD requirements, sẽ được share giữa database schema và application logic.

## Article

**Purpose:** Lưu trữ thông tin bài báo đã crawl từ Google News, bao gồm metadata và content được extract bởi newspaper4k-master

**Key Attributes:**
- id: UUID - Primary key duy nhất
- title: str - Tiêu đề bài báo
- content: text - Nội dung chính được extract
- author: str - Tác giả (có thể null)  
- publish_date: datetime - Ngày đăng bài
- source_url: str - URL gốc của bài báo
- image_url: str - URL hình ảnh đại diện (có thể null)
- created_at: datetime - Thời điểm crawl
- updated_at: datetime - Lần update cuối

### TypeScript Interface
```typescript
interface Article {
  id: string;
  title: string;
  content: string;
  author?: string;
  publish_date: Date;
  source_url: string;
  image_url?: string;
  created_at: Date;
  updated_at: Date;
}
```

### Relationships
- Many-to-many với Category qua ArticleCategory junction table

## Category

**Purpose:** Quản lý categories để organize crawling targets, mỗi category có danh sách keywords với logic OR

**Key Attributes:**
- id: UUID - Primary key
- name: str - Tên category (unique)
- keywords: list[str] - Danh sách keywords cho OR search
- exclude_keywords: list[str] - Keywords cần exclude (optional)
- is_active: bool - Enable/disable category
- created_at: datetime - Thời điểm tạo
- updated_at: datetime - Lần update cuối

### TypeScript Interface  
```typescript
interface Category {
  id: string;
  name: string;
  keywords: string[];
  exclude_keywords?: string[];
  is_active: boolean;
  created_at: Date;
  updated_at: Date;
}
```

### Relationships
- Many-to-many với Article qua ArticleCategory junction table
- One-to-many với CrawlJob

## ArticleCategory

**Purpose:** Junction table cho many-to-many relationship giữa articles và categories

**Key Attributes:**
- article_id: UUID - Foreign key to Article
- category_id: UUID - Foreign key to Category
- relevance_score: float - Optional relevance score (0.0-1.0)
- created_at: datetime - Thời điểm associate

### TypeScript Interface
```typescript
interface ArticleCategory {
  article_id: string;
  category_id: string;
  relevance_score?: number;
  created_at: Date;
}
```

## CrawlJob

**Purpose:** Track scheduled crawling jobs và their status để monitoring và retry logic

**Key Attributes:**
- id: UUID - Primary key
- category_id: UUID - Category được crawl
- status: enum - (pending, running, completed, failed)
- started_at: datetime - Thời điểm start (nullable)
- completed_at: datetime - Thời điểm complete (nullable)
- articles_found: int - Số articles tìm được
- error_message: str - Error details nếu failed (nullable)
- retry_count: int - Số lần retry
- created_at: datetime - Thời điểm tạo job

### TypeScript Interface
```typescript
enum CrawlJobStatus {
  PENDING = 'pending',
  RUNNING = 'running', 
  COMPLETED = 'completed',
  FAILED = 'failed'
}

interface CrawlJob {
  id: string;
  category_id: string;
  status: CrawlJobStatus;
  started_at?: Date;
  completed_at?: Date;
  articles_found: number;
  error_message?: string;
  retry_count: number;
  created_at: Date;
}
```

### Relationships
- Many-to-one với Category

## Design Decisions

- **UUID primary keys:** Tránh collision và better cho distributed systems
- **JSON arrays cho keywords:** PostgreSQL JSON support tốt, flexible hơn separate table
- **Junction table explicit:** Cho phép thêm metadata như relevance score
- **CrawlJob tracking:** Essential cho monitoring và debugging scheduled jobs
- **Timestamps everywhere:** Audit trail và debugging