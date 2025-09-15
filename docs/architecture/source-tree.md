# Source Tree

The Google News Scraper follows a **monorepo structure** that cleanly separates the existing backend system from the new frontend addition:

```
google-news-scraper/
├── src/                        # Existing FastAPI backend
│   ├── api/                    # REST API routes and schemas
│   ├── core/                   # Business logic (categories, crawler, scheduler)
│   ├── database/               # Models, repositories, migrations
│   └── shared/                 # Shared utilities and config
├── frontend/                   # New React frontend application
│   ├── src/
│   │   ├── components/         # React components (UI, common, features)
│   │   ├── pages/              # Page components/routes
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # API client services
│   │   └── utils/              # Frontend utilities
│   ├── public/                 # Static assets
│   └── tests/                  # Frontend tests
├── docs/                       # Project documentation
│   ├── prd/                    # Product requirements
│   └── architecture/           # Architecture documentation
├── docker/                     # Docker configurations
├── tests/                      # Backend tests
└── scripts/                    # Build/deploy scripts
```
