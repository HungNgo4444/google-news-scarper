# Technical Assumptions

## Repository Structure: Monorepo

Tất cả components (crawler, scheduler, database scripts) sẽ được tổ chức trong một single repository để dễ dàng quản lý và deployment.

## Service Architecture

Monolith architecture với modular components: crawler module sử dụng newspaper4k-master, scheduler module cho background jobs, và database module cho PostgreSQL operations.

## Testing Requirements

Unit testing cho core functions, integration testing cho database operations và Google News API interactions.

## Additional Technical Assumptions and Requests

- Python là ngôn ngữ chính để tận dụng newspaper4k-master codebase
- Sử dụng scheduling frameworks như Celery hoặc APScheduler cho background jobs
- PostgreSQL với proper indexing cho performance khi query large datasets
- Error handling và retry mechanisms cho network failures
- Configuration management để dễ dàng adjust crawling parameters
