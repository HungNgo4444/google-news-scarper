# Google News Scraper Fullstack Architecture

## Architecture Overview

This document outlines the complete fullstack architecture for Google News Scraper, including backend systems, frontend implementation, and their integration. It serves as the single source of truth for AI-driven development, ensuring consistency across the entire technology stack.

## Architecture Documents

### Core Architecture
- [High Level Architecture](high-level-architecture.md) - System overview, platform choices, architectural patterns
- [Tech Stack](tech-stack.md) - Complete technology selections with versions and rationale
- [Data Models](data-models.md) - Shared data structures and TypeScript interfaces

### API & Integration  
- [API Specification](rest-api-spec.md) - REST API endpoints and schemas
- [External APIs](external-apis.md) - Google News and newspaper4k integration details
- [Core Workflows](core-workflows.md) - System workflow sequence diagrams

### Implementation Details
- [Database Schema](database-schema.md) - PostgreSQL schema with indexes and constraints
- [Components](components.md) - System components and their responsibilities
- [Frontend Architecture](frontend-architecture.md) - Optional management interface design
- [Backend Architecture](backend-architecture.md) - Python service layer architecture

### Development & Operations
- [Unified Project Structure](source-tree.md) - Monorepo organization and file structure
- [Development Workflow](development-workflow.md) - Docker-based local development
- [Deployment Architecture](deployment.md) - VPS deployment with CI/CD
- [Testing Strategy](testing-strategy.md) - Comprehensive testing approach

### Standards & Guidelines
- [Coding Standards](coding-standards.md) - AI-focused development rules
- [Error Handling Strategy](error-handling.md) - Unified error management
- [Security and Performance](security-performance.md) - Production hardening
- [Monitoring and Observability](monitoring.md) - System monitoring and alerting

## Quick Start

1. **For Developers**: Start with [Tech Stack](tech-stack.md) and [Development Workflow](development-workflow.md)
2. **For System Design**: Review [High Level Architecture](high-level-architecture.md) and [Components](components.md)  
3. **For Database Work**: Check [Data Models](data-models.md) and [Database Schema](database-schema.md)
4. **For API Development**: See [API Specification](rest-api-spec.md) and [Backend Architecture](backend-architecture.md)

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|---------|
| 2025-09-11 | v1.0 | Initial architecture document creation | Winston the Architect |