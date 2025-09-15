import { useState } from 'react';
import { apiClient, ApiError } from '@/services/api';

export function HealthCheck() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string>('');

  const checkHealth = async () => {
    setStatus('loading');
    setMessage('Checking backend connection...');

    try {
      const result = await apiClient.healthCheck();
      setStatus('success');
      setMessage(`Backend is healthy: ${result.status}`);
    } catch (error) {
      setStatus('error');
      if (error instanceof ApiError) {
        setMessage(`Connection failed: ${error.message}`);
      } else {
        setMessage('Unknown error occurred');
      }
    }
  };

  return (
    <div className="p-4 border border-gray-300 rounded-lg">
      <h3 className="text-lg font-semibold mb-4">Backend Health Check</h3>
      
      <button
        onClick={checkHealth}
        disabled={status === 'loading'}
        className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50"
      >
        {status === 'loading' ? 'Checking...' : 'Test Connection'}
      </button>

      {message && (
        <div className={`mt-4 p-3 rounded ${
          status === 'success' ? 'bg-green-100 text-green-700' : 
          status === 'error' ? 'bg-red-100 text-red-700' : 
          'bg-blue-100 text-blue-700'
        }`}>
          {message}
        </div>
      )}
    </div>
  );
}