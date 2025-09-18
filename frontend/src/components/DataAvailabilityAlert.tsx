import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertTriangle } from "lucide-react";

interface DataAvailabilityAlertProps {
  messages: string[];
  className?: string;
}

/**
 * Displays data availability alerts when template variables are defined but have no data
 * 
 * This component shows user-friendly messages when data sources referenced in prompts
 * are currently unavailable, helping users understand why certain information might
 * be missing from their daily summary.
 */
export const DataAvailabilityAlert = ({ messages, className = "" }: DataAvailabilityAlertProps) => {
  // Don't render if no messages
  if (!messages || messages.length === 0) {
    return null;
  }

  return (
    <Alert className={`border-amber-200 bg-amber-50 ${className}`}>
      <AlertTriangle className="h-4 w-4 text-amber-600" />
      <AlertDescription className="text-amber-800">
        <div className="space-y-1">
          <div className="font-medium">Some data sources are currently unavailable:</div>
          {messages.map((message, index) => (
            <div key={index} className="text-sm">• {message}</div>
          ))}
          <div className="text-xs mt-2 text-amber-700">
            Your summary will be generated with available data sources.
          </div>
        </div>
      </AlertDescription>
    </Alert>
  );
};