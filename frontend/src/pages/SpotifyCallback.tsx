import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from "@/components/ui/card";

/**
 * Spotify OAuth callback page
 * Handles the redirect from Spotify OAuth and processes the authorization code
 */
export const SpotifyCallback = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [message, setMessage] = useState('Processing Spotify authentication...');

  useEffect(() => {
    const processCallback = async () => {
      try {
        const success = searchParams.get('success');
        const error = searchParams.get('error');

        if (error) {
          setStatus('error');
          setMessage(`Authentication failed: ${decodeURIComponent(error)}`);
          return;
        }

        if (success === 'true') {
          setStatus('success');
          setMessage('Successfully connected to Spotify! You can close this window.');

          // Close the popup window after successful authentication
          setTimeout(() => {
            if (window.opener) {
              window.close();
            }
          }, 2000);
          return;
        }

        // If we get here, neither success nor error was provided
        setStatus('error');
        setMessage('Invalid callback - missing success or error parameter');

      } catch (error) {
        console.error('OAuth callback error:', error);
        setStatus('error');
        setMessage(error instanceof Error ? error.message : 'Authentication failed');
      }
    };

    processCallback();
  }, [searchParams]);

  const getStatusColor = () => {
    switch (status) {
      case 'processing': return 'text-blue-600';
      case 'success': return 'text-green-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'processing': return '🔄';
      case 'success': return '✅';
      case 'error': return '❌';
      default: return '⏳';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="p-8 max-w-md w-full text-center">
        <div className="mb-4 text-4xl">
          {getStatusIcon()}
        </div>
        <h1 className="text-xl font-bold mb-4">
          Spotify Authentication
        </h1>
        <p className={`${getStatusColor()} mb-4`}>
          {message}
        </p>
        {status === 'processing' && (
          <div className="flex justify-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
        )}
        {status === 'success' && (
          <p className="text-sm text-gray-600">
            This window will close automatically.
          </p>
        )}
        {status === 'error' && (
          <p className="text-sm text-gray-600">
            You can close this window and try again.
          </p>
        )}
      </Card>
    </div>
  );
};