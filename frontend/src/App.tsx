import { useState } from 'react'
import { CategoriesPage } from './pages/CategoriesPage'
import { JobsPage } from './pages/JobsPage'
import { ArticlesPage } from './pages/ArticlesPage'

type Page = 'home' | 'categories' | 'jobs' | 'articles'

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('home')
  const [currentJobId, setCurrentJobId] = useState<string>('')

  const navigateToArticles = (jobId: string) => {
    setCurrentJobId(jobId)
    setCurrentPage('articles')
  }

  const navigateToJobs = () => {
    setCurrentPage('jobs')
    setCurrentJobId('')
  }


  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">Google News Scraper</h1>
            </div>
            <div className="flex space-x-8">
              <button
                onClick={() => setCurrentPage('home')}
                className={`inline-flex items-center px-1 pt-1 text-sm font-medium border-b-2 ${
                  currentPage === 'home'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Home
              </button>
              <button
                onClick={() => setCurrentPage('categories')}
                className={`inline-flex items-center px-1 pt-1 text-sm font-medium border-b-2 ${
                  currentPage === 'categories'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Categories Management
              </button>
              <button
                onClick={() => setCurrentPage('jobs')}
                className={`inline-flex items-center px-1 pt-1 text-sm font-medium border-b-2 ${
                  currentPage === 'jobs'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Jobs Management
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      {currentPage === 'home' && (
        <div className="container mx-auto py-8">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-gray-900 mb-4">Google News Scraper</h2>
              <p className="text-lg text-gray-600 mb-8">Manage your news categories and scraping preferences</p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button
                  onClick={() => setCurrentPage('categories')}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg text-lg font-medium shadow-lg hover:shadow-xl transition-all"
                >
                  🗂️ Manage Categories
                </button>
                <button
                  onClick={() => setCurrentPage('jobs')}
                  className="bg-green-600 hover:bg-green-700 text-white px-8 py-4 rounded-lg text-lg font-medium shadow-lg hover:shadow-xl transition-all"
                >
                  🚀 Manage Jobs
                </button>
              </div>
            </div>

            <div className="grid md:grid-cols-3 gap-6 mt-12">
              <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">📰 News Scraping</h3>
                <p className="text-gray-600">Automatically collect news articles from Google News based on your configured categories.</p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">🏷️ Category Management</h3>
                <p className="text-gray-600">Create, edit, and organize news categories with custom keywords and filters.</p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">⚙️ Smart Filtering</h3>
                <p className="text-gray-600">Use include/exclude keywords to fine-tune your news collection.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {currentPage === 'categories' && <CategoriesPage />}
      {currentPage === 'jobs' && <JobsPage onNavigateToArticles={navigateToArticles} />}
      {currentPage === 'articles' && <ArticlesPage jobId={currentJobId} onNavigateBack={navigateToJobs} />}
    </div>
  )
}

export default App
