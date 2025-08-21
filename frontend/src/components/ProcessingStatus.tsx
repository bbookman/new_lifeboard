import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Clock, CheckCircle, AlertCircle, Loader2, Play, RefreshCw, TrendingUp, Database } from 'lucide-react';

interface ProcessingStats {
  total_days: number;
  completed_days: number;
  pending_days: number;
  processing_days: number;
  failed_days: number;
  active_processing: string[];
  last_updated: string;
}

interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  message_id: string;
}

interface ProcessingStatusProps {
  className?: string;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ className = '' }) => {
  const [stats, setStats] = useState<ProcessingStats | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [realtimeUpdates, setRealtimeUpdates] = useState<WebSocketMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // WebSocket connection
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);

  const connectWebSocket = useCallback(() => {
    try {
      // Determine WebSocket URL (adjust for your environment)
      const wsUrl =
        process.env.NODE_ENV === 'production'
          ? `wss://${window.location.host}/ws/processing`
          : `ws://localhost:8000/ws/processing`;

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setConnectionError(null);

        // Subscribe to processing updates
        ws.send(
          JSON.stringify({
            type: 'subscription',
            data: {
              topics: ['processing_updates', 'queue_stats', 'day_updates'],
            },
          }),
        );
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          // Handle different message types
          switch (message.type) {
            case 'queue_stats':
              setStats(message.data);
              break;

            case 'processing_status':
            case 'day_update':
              setRealtimeUpdates((prev) => [message, ...prev.slice(0, 9)]); // Keep last 10 updates
              break;

            case 'heartbeat':
              // Respond to heartbeat
              if (message.data?.status === 'ping') {
                ws.send(
                  JSON.stringify({
                    type: 'heartbeat',
                    data: { status: 'pong' },
                  }),
                );
              }
              break;

            case 'error':
              console.error('WebSocket error:', message.data);
              setConnectionError(message.data.message);
              break;
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.reason);
        setIsConnected(false);

        // Attempt reconnection after delay
        setTimeout(() => {
          if (!event.wasClean) {
            connectWebSocket();
          }
        }, 5000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('WebSocket connection failed');
        setIsConnected(false);
      };

      setWebsocket(ws);
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionError('Failed to establish WebSocket connection');
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch('/api/clean-up-crew/queue');
      if (!response.ok) throw new Error('Failed to fetch stats');

      const data = await response.json();
      setStats(data);
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching stats:', error);
      setConnectionError('Failed to fetch processing stats');
      setIsLoading(false);
    }
  }, []);

  const triggerProcessing = async (daysDate?: string) => {
    try {
      const endpoint = daysDate ? `/api/clean-up-crew/day/${daysDate}/process` : '/api/clean-up-crew/batch/process';

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: false }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Processing failed');
      }

      const result = await response.json();
      console.log('Processing triggered:', result);

      // Refresh stats
      await fetchStats();
    } catch (error) {
      console.error('Error triggering processing:', error);
      setConnectionError(`Failed to trigger processing: ${error.message}`);
    }
  };

  useEffect(() => {
    // Initial data fetch
    fetchStats();

    // Connect WebSocket for real-time updates
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (websocket) {
        websocket.close();
      }
    };
  }, [connectWebSocket, fetchStats]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'processing':
        return 'bg-blue-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4" />;
      case 'processing':
        return <Loader2 className="h-4 w-4 animate-spin" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="ml-2">Loading processing status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const completionPercentage = stats ? Math.round((stats.completed_days / stats.total_days) * 100) || 0 : 0;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Connection Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">
            {isConnected ? 'Real-time updates active' : 'Real-time updates disconnected'}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={fetchStats} disabled={isLoading}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {/* Error Alert */}
      {connectionError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{connectionError}</AlertDescription>
        </Alert>
      )}

      {/* Main Stats Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center">
              <Database className="h-5 w-5 mr-2" />
              Semantic Processing Status
            </CardTitle>
            <Badge variant={isConnected ? 'default' : 'secondary'}>{isConnected ? 'Live' : 'Static'}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {stats ? (
            <div className="space-y-4">
              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Overall Progress</span>
                  <span>{completionPercentage}%</span>
                </div>
                <Progress value={completionPercentage} className="h-2" />
              </div>

              {/* Status Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-green-50 rounded-lg">
                  <div className="flex items-center justify-center mb-1">
                    <CheckCircle className="h-4 w-4 text-green-600 mr-1" />
                    <span className="text-sm font-medium text-green-700">Completed</span>
                  </div>
                  <div className="text-2xl font-bold text-green-600">{stats.completed_days}</div>
                </div>

                <div className="text-center p-3 bg-blue-50 rounded-lg">
                  <div className="flex items-center justify-center mb-1">
                    <Loader2 className="h-4 w-4 text-blue-600 mr-1" />
                    <span className="text-sm font-medium text-blue-700">Processing</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-600">{stats.processing_days}</div>
                </div>

                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-center mb-1">
                    <Clock className="h-4 w-4 text-gray-600 mr-1" />
                    <span className="text-sm font-medium text-gray-700">Pending</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-600">{stats.pending_days}</div>
                </div>

                <div className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="flex items-center justify-center mb-1">
                    <AlertCircle className="h-4 w-4 text-red-600 mr-1" />
                    <span className="text-sm font-medium text-red-700">Failed</span>
                  </div>
                  <div className="text-2xl font-bold text-red-600">{stats.failed_days}</div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex space-x-2">
                <Button onClick={() => triggerProcessing()} disabled={stats.pending_days === 0} className="flex-1">
                  <Play className="h-4 w-4 mr-1" />
                  Process Pending ({stats.pending_days})
                </Button>
                <Button variant="outline" onClick={() => window.open('/api/clean-up-crew/health', '_blank')}>
                  <TrendingUp className="h-4 w-4 mr-1" />
                  Health Check
                </Button>
              </div>

              {/* Active Processing */}
              {stats.active_processing.length > 0 && (
                <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                  <h4 className="font-medium text-blue-700 mb-2">Currently Processing:</h4>
                  <div className="flex flex-wrap gap-1">
                    {stats.active_processing.map((day) => (
                      <Badge key={day} variant="secondary" className="bg-blue-100 text-blue-700">
                        {day}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">No processing stats available</div>
          )}
        </CardContent>
      </Card>

      {/* Real-time Updates */}
      {realtimeUpdates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Updates</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {realtimeUpdates.map((update, index) => (
                <div
                  key={`${update.message_id}-${index}`}
                  className="flex items-center justify-between p-2 bg-gray-50 rounded"
                >
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(update.data.status)}
                    <span className="text-sm">
                      {update.type === 'processing_status'
                        ? `Day ${update.data.days_date}: ${update.data.status}`
                        : `${update.type}: ${update.data.message || 'Update received'}`}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {new Date(update.timestamp).toLocaleTimeString()}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ProcessingStatus;
