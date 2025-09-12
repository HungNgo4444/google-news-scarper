# Database Schema

Transform conceptual data models thành concrete PostgreSQL schema với indexes, constraints và relationships.

## Schema Definition

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Categories table
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    exclude_keywords JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT keywords_not_empty CHECK (jsonb_array_length(keywords) > 0),
    CONSTRAINT name_not_empty CHECK (length(trim(name)) > 0)
);

-- Articles table
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT,
    author VARCHAR(255),
    publish_date TIMESTAMP WITH TIME ZONE,
    source_url TEXT NOT NULL,
    url_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA-256 hash of source_url
    content_hash VARCHAR(64), -- SHA-256 hash of content for duplicate detection
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT title_not_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT source_url_not_empty CHECK (length(trim(source_url)) > 0),
    CONSTRAINT valid_url_hash CHECK (length(url_hash) = 64),
    CONSTRAINT valid_image_url CHECK (image_url IS NULL OR image_url ~ '^https?://.*')
);

-- Junction table for many-to-many relationship
CREATE TABLE article_categories (
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    relevance_score DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (article_id, category_id),
    
    -- Constraints
    CONSTRAINT valid_relevance_score CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0)
);

-- Crawl jobs tracking table
CREATE TABLE crawl_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    articles_found INTEGER NOT NULL DEFAULT 0,
    articles_saved INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0, -- Higher number = higher priority
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    CONSTRAINT valid_articles_count CHECK (articles_found >= 0 AND articles_saved >= 0),
    CONSTRAINT valid_retry_count CHECK (retry_count >= 0),
    CONSTRAINT completed_jobs_have_end_time CHECK (
        (status = 'completed' AND completed_at IS NOT NULL) OR 
        (status != 'completed')
    ),
    CONSTRAINT running_jobs_have_start_time CHECK (
        (status IN ('running', 'completed', 'failed') AND started_at IS NOT NULL) OR
        (status = 'pending')
    )
);
```

## Performance Indexes

```sql
-- Category indexes
CREATE INDEX idx_categories_active ON categories(is_active) WHERE is_active = true;
CREATE INDEX idx_categories_name ON categories(name);

-- Article indexes
CREATE INDEX idx_articles_publish_date ON articles(publish_date DESC);
CREATE INDEX idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX idx_articles_source_url ON articles(source_url);
CREATE INDEX idx_articles_url_hash ON articles(url_hash); -- For deduplication
CREATE INDEX idx_articles_content_hash ON articles(content_hash) WHERE content_hash IS NOT NULL;

-- Composite indexes for common queries
CREATE INDEX idx_article_categories_category_created ON article_categories(category_id, created_at DESC);
CREATE INDEX idx_article_categories_article_relevance ON article_categories(article_id, relevance_score DESC);

-- Crawl job indexes
CREATE INDEX idx_crawl_jobs_status_created ON crawl_jobs(status, created_at DESC);
CREATE INDEX idx_crawl_jobs_category_status ON crawl_jobs(category_id, status);
CREATE INDEX idx_crawl_jobs_priority_created ON crawl_jobs(priority DESC, created_at ASC) WHERE status = 'pending';

-- Full-text search indexes (optional)
CREATE INDEX idx_articles_title_fts ON articles USING gin(to_tsvector('english', title));
CREATE INDEX idx_articles_content_fts ON articles USING gin(to_tsvector('english', content)) WHERE content IS NOT NULL;
```

## Trigger Functions

```sql
-- Trigger function cho updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_categories_updated_at 
    BEFORE UPDATE ON categories 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_articles_updated_at 
    BEFORE UPDATE ON articles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## Utility Functions

```sql
-- Function để generate URL hash
CREATE OR REPLACE FUNCTION generate_url_hash(url TEXT)
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN encode(digest(lower(trim(url)), 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function để generate content hash
CREATE OR REPLACE FUNCTION generate_content_hash(content TEXT)
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN CASE 
        WHEN content IS NULL OR length(trim(content)) = 0 THEN NULL
        ELSE encode(digest(content, 'sha256'), 'hex')
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

## Views for Common Queries

```sql
-- Active categories view
CREATE VIEW active_categories AS
SELECT * FROM categories 
WHERE is_active = true 
ORDER BY name;

-- Recent articles with category names
CREATE VIEW recent_articles AS
SELECT 
    a.*,
    array_agg(c.name) as category_names
FROM articles a
JOIN article_categories ac ON a.id = ac.article_id
JOIN categories c ON ac.category_id = c.id
WHERE a.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY a.id
ORDER BY a.created_at DESC;

-- Crawl job summary
CREATE VIEW crawl_job_summary AS
SELECT 
    c.name as category_name,
    cj.status,
    COUNT(*) as job_count,
    SUM(cj.articles_found) as total_articles_found,
    SUM(cj.articles_saved) as total_articles_saved,
    AVG(EXTRACT(EPOCH FROM (cj.completed_at - cj.started_at))) as avg_duration_seconds
FROM crawl_jobs cj
JOIN categories c ON cj.category_id = c.id
WHERE cj.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY c.name, cj.status
ORDER BY c.name, cj.status;
```

## Data Partitioning (Optional)

```sql
-- Partitioning cho articles table (for large datasets)
-- Uncomment when needed for scale

-- ALTER TABLE articles PARTITION BY RANGE (created_at);
-- CREATE TABLE articles_y2024 PARTITION OF articles FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
-- CREATE TABLE articles_y2025 PARTITION OF articles FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
```

## Key Design Decisions

1. **UUID Primary Keys:** Better cho distributed systems, avoid collision
2. **JSONB cho keywords:** Flexible, có thể query và index efficiently  
3. **Hash-based deduplication:** URL hash cho fast duplicate detection, content hash cho content changes
4. **Comprehensive constraints:** Data integrity at database level
5. **Strategic indexing:** Based on expected query patterns
6. **Partitioning ready:** Commented out nhưng ready cho large datasets
7. **Audit trails:** created_at, updated_at, last_seen timestamps
8. **Views cho common queries:** Simplify application code

## Migration Strategy

```sql
-- Initial migration (V1)
-- Run schema creation scripts above

-- Example future migration (V2) 
-- ALTER TABLE categories ADD COLUMN crawl_frequency INTEGER DEFAULT 3600; -- seconds
-- CREATE INDEX idx_categories_crawl_frequency ON categories(crawl_frequency);

-- Example V3 migration
-- ADD new column for better article categorization
-- ALTER TABLE article_categories ADD COLUMN confidence_score DECIMAL(3,2) DEFAULT 1.0;
```