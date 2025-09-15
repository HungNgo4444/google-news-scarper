# Data Models

## Category Model

**Purpose:** Represents news categories used for targeted crawling with associated keywords for content filtering.

**Key Attributes:**
- id: UUID - Unique identifier for each category
- name: string - Human-readable category name (unique)
- keywords: string[] - Search terms to include in crawling
- exclude_keywords: string[] - Terms to exclude from results
- is_active: boolean - Whether category is enabled for crawling
- created_at: datetime - Category creation timestamp
- updated_at: datetime - Last modification timestamp

### TypeScript Interface

```typescript
interface Category {
  id: string;
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
```

### Relationships
- One-to-Many with Article (one category can have many articles)
- Many-to-Many with CrawlJob (categories can be associated with multiple jobs)

## Article Model

**Purpose:** Stores crawled news articles with full content, metadata, and source information.

**Key Attributes:**
- id: UUID - Unique article identifier
- title: string - Article headline
- content: text - Full article content
- url: string - Source article URL (unique)
- published_at: datetime - Original publication date
- crawled_at: datetime - When article was scraped
- source: string - News source/publisher name
- category_id: UUID - Associated category reference

### TypeScript Interface

```typescript
interface Article {
  id: string;
  title: string;
  content: string;
  url: string;
  published_at: string;
  crawled_at: string;
  source: string;
  category_id: string;
}
```

### Relationships
- Many-to-One with Category (articles belong to one category)
- One-to-Many with CrawlJobResult (articles can be results of multiple crawl attempts)

## CrawlJob Model

**Purpose:** Tracks crawling job execution, status, and results for monitoring and debugging purposes.

**Key Attributes:**
- id: UUID - Unique job identifier
- category_id: UUID - Target category for crawling
- status: enum - Job status (pending, running, completed, failed)
- started_at: datetime - Job start time
- completed_at: datetime - Job completion time (nullable)
- articles_found: integer - Number of articles discovered
- error_message: string - Error details if job failed (nullable)

### TypeScript Interface

```typescript
interface CrawlJob {
  id: string;
  category_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
  articles_found: number;
  error_message: string | null;
}
```

### Relationships
- Many-to-One with Category (jobs target specific categories)
- One-to-Many with Article (jobs can discover multiple articles)
