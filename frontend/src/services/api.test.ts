import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient, ApiError } from './api'

// Mock fetch globally
global.fetch = vi.fn()

describe('ApiClient', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  describe('healthCheck', () => {
    it('should return status when health check succeeds', async () => {
      const mockResponse = { status: 'healthy' }
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response)

      const result = await apiClient.healthCheck()

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/health',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      )
      expect(result).toEqual(mockResponse)
    })

    it('should throw ApiError when health check fails', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({}),
      } as Response)

      await expect(apiClient.healthCheck()).rejects.toThrow(ApiError)
    })

    it('should handle network errors', async () => {
      vi.mocked(fetch).mockRejectedValueOnce(new TypeError('fetch failed'))

      await expect(apiClient.healthCheck()).rejects.toThrow('Network error: Unable to connect to server')
    })
  })

  describe('ApiError', () => {
    it('should create error with correct properties', () => {
      const error = new ApiError('Test error', 400, { detail: 'Bad request' })
      
      expect(error.name).toBe('ApiError')
      expect(error.message).toBe('Test error')
      expect(error.status).toBe(400)
      expect(error.data).toEqual({ detail: 'Bad request' })
    })
  })
})