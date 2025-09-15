import '@testing-library/jest-dom'
import { beforeEach, vi } from 'vitest'

// Mock fetch globally
global.fetch = vi.fn()

beforeEach(() => {
  vi.resetAllMocks()
})