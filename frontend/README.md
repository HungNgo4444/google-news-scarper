# Google News Scraper - Frontend

React + TypeScript + Vite frontend for the Google News Scraper application.

## Tech Stack

- **React 18.x** with TypeScript 5.x
- **Vite** for fast development and optimized builds
- **TailwindCSS 3.x** + **Shadcn UI** for styling
- **API Integration** with centralized service layer

## Development Workflow

### Local Development

1. **Start development server:**
   ```bash
   npm run dev
   ```
   - Runs on `http://localhost:3000`
   - Hot module replacement enabled
   - Automatically connects to backend on `http://localhost:8000`

2. **Backend Integration:**
   - Ensure backend services are running on port 8000
   - API calls are centralized in `src/services/api.ts`
   - Health check component available for testing connectivity

### Docker Development

1. **Build and run with Docker Compose:**
   ```bash
   # From project root
   docker-compose up -d
   ```

2. **Services:**
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000`
   - Database: `localhost:5432`
   - Redis: `localhost:6379`

3. **Stop services:**
   ```bash
   docker-compose down
   ```

### Project Structure

```
frontend/
├── src/
│   ├── components/     # React components
│   ├── pages/          # Page components/routes  
│   ├── hooks/          # Custom React hooks
│   ├── services/       # API client services
│   ├── lib/            # Utility functions
│   └── utils/          # General utilities
├── public/             # Static assets
└── tests/              # Frontend tests
```

### API Integration

- All API calls go through `src/services/api.ts`
- Error handling with user-friendly messages
- Health check endpoint for connectivity testing
- CORS configured for localhost development

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      ...tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      ...tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      ...tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
