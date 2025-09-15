import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { HealthCheck } from './HealthCheck'
import { apiClient } from '@/services/api'

// Mock the API client
vi.mock('@/services/api', () => ({
  apiClient: {
    healthCheck: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    data?: unknown;
    
    constructor(message: string, status: number, data?: unknown) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.data = data;
    }
  }
}))

describe('HealthCheck Component', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('should render initial state correctly', () => {
    render(<HealthCheck />)
    
    expect(screen.getByText('Backend Health Check')).toBeInTheDocument()
    expect(screen.getByText('Test Connection')).toBeInTheDocument()
  })

  it('should display loading state when checking health', async () => {
    vi.mocked(apiClient.healthCheck).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(<HealthCheck />)
    
    fireEvent.click(screen.getByText('Test Connection'))
    
    expect(screen.getByText('Checking...')).toBeInTheDocument()
    expect(screen.getByText('Checking backend connection...')).toBeInTheDocument()
  })

  it('should display success message when health check passes', async () => {
    vi.mocked(apiClient.healthCheck).mockResolvedValue({ status: 'healthy' })

    render(<HealthCheck />)
    
    fireEvent.click(screen.getByText('Test Connection'))
    
    await waitFor(() => {
      expect(screen.getByText('Backend is healthy: healthy')).toBeInTheDocument()
    })

    // Check success styling
    const messageElement = screen.getByText('Backend is healthy: healthy')
    expect(messageElement).toHaveClass('bg-green-100', 'text-green-700')
  })

  it('should display error message when health check fails', async () => {
    const error = new Error('Connection failed')
    vi.mocked(apiClient.healthCheck).mockRejectedValue(error)

    render(<HealthCheck />)
    
    fireEvent.click(screen.getByText('Test Connection'))
    
    await waitFor(() => {
      expect(screen.getByText('Unknown error occurred')).toBeInTheDocument()
    })

    // Check error styling
    const messageElement = screen.getByText('Unknown error occurred')
    expect(messageElement).toHaveClass('bg-red-100', 'text-red-700')
  })
})