import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Clock, 
  CheckCircle, 
  AlertCircle, 
  Loader2, 
  Play, 
  RefreshCw,
  TrendingUp,
  Database,
  Wifi,
  WifiOff
} from 'lucide-react';
import { useProcessingStatus } from '../hooks/useProcessingStatus';

interface ProcessingStatusProps {
  className?: string;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ className = '' }) => {
  const { data: stats, isLoading, error, refetch, lastSuccessfulPoll } = useProcessingStatus();
  
  const handleRefresh = () => {
    refetch();
  };

  const handleTriggerProcessing = async () => {
    try {
      const response = await fetch('/api/processing/trigger', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to trigger processing: ${response.status}`);
      }

      // Refresh stats after triggering
      setTimeout(() => refetch(), 1000);
    } catch (error) {
      console.error('Error triggering processing:', error);
    }
  };

  const getPollingHealthIndicator = () => {
    if (!lastSuccessfulPoll) {
      return { color: 'bg-yellow-500', status: 'Unknown' };
    }

    const timeSinceLastPoll = Date.now() - lastSuccessfulPoll;
    
    if (timeSinceLastPoll < 10000) { // Less than 10 seconds
      return { color: 'bg-green-500', status: 'Healthy' };
    } else if (timeSinceLastPoll < 30000) { // Less than 30 seconds
      return { color: 'bg-yellow-500', status: 'Stale' };
    } else {
      return { color: 'bg-red-500', status: 'Disconnected' };
    }
  };

  const formatLastUpdated = () => {
    if (!lastSuccessfulPoll) return 'Never';
    
    const secondsAgo = Math.floor((Date.now() - lastSuccessfulPoll) / 1000);
    
    if (secondsAgo < 60) {
      return `${secondsAgo} seconds ago`;
    } else if (secondsAgo < 3600) {
      return `${Math.floor(secondsAgo / 60)} minutes ago`;
    } else {
      return `${Math.floor(secondsAgo / 3600)} hours ago`;
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Processing Queue Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            <span>Loading processing status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Processing Queue Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <div className="space-y-2">
                <div>Error loading processing status</div>
                <div className="text-sm">{error.message}</div>
                <Button size="sm" onClick={handleRefresh} variant="outline">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Retry
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  // No data state
  if (!stats) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Processing Queue Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            No data available
          </div>
        </CardContent>
      </Card>
    );
  }

  const pollingHealth = getPollingHealthIndicator();
  const completionPercentage = stats.total_days > 0 
    ? Math.round((stats.completed_days / stats.total_days) * 100) 
    : 0;

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Processing Queue Status
          </div>
          <div className="flex items-center gap-2">
            {/* Polling health indicator */}
            <div 
              data-testid="polling-health-indicator"
              className={`w-3 h-3 rounded-full ${pollingHealth.color}`}
              title={`Polling status: ${pollingHealth.status}`}
            />
            <Button 
              size="sm" 
              variant="outline" 
              onClick={handleRefresh}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Connection Status */}
        <div className="flex items-center justify-between text-sm">
          <span>Last updated: {formatLastUpdated()}</span>
          <div className="flex items-center gap-2">
            {stats.active_processing ? (
              <>
                <div data-testid="active-processing-indicator" className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                <span className="text-blue-600">Processing Active</span>
              </>
            ) : (
              <span className="text-gray-500">Idle</span>
            )}
          </div>
        </div>

        {/* Statistics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{stats.total_days}</div>
            <div className="text-sm text-gray-500">Total Days:</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{stats.completed_days}</div>
            <div className="text-sm text-gray-500">Completed:</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-600">{stats.pending_days}</div>
            <div className="text-sm text-gray-500">Pending:</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{stats.processing_days}</div>
            <div className="text-sm text-gray-500">Processing:</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{stats.failed_days}</div>
            <div className="text-sm text-gray-500">Failed:</div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Overall Progress</span>
            <span>{completionPercentage}%</span>
          </div>
          <Progress value={completionPercentage} className="w-full" />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          <Button 
            size="sm" 
            onClick={handleTriggerProcessing}
            disabled={isLoading}
          >
            <Play className="h-4 w-4 mr-2" />
            Trigger Processing
          </Button>
          
          <Button 
            size="sm" 
            variant="outline" 
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export { ProcessingStatus };
export default ProcessingStatus;