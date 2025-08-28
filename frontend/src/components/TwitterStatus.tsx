import { useEffect, useState } from "react";

interface TwitterStatusProps {
  selectedDate: string;
}

interface TwitterStatus {
  status: string;
  icon: string;
  type: "active" | "complete";
  minutes_until_next?: number;
}

const TwitterStatusComponent = ({ selectedDate }: TwitterStatusProps) => {
  const [status, setStatus] = useState<TwitterStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTwitterStatus = async () => {
      if (!selectedDate) return;
      
      try {
        setLoading(true);
        const response = await fetch(`/api/sources/twitter/status?date=${selectedDate}`);
        
        if (response.ok) {
          const statusData = await response.json();
          setStatus(statusData);
        } else {
          // If API doesn't exist yet or returns error, don't show status
          setStatus(null);
        }
      } catch (error) {
        console.log("[TwitterStatus] API not available yet:", error);
        setStatus(null);
      } finally {
        setLoading(false);
      }
    };

    fetchTwitterStatus();
  }, [selectedDate]);

  if (loading || !status) {
    return null; // Don't show anything while loading or if no status
  }

  return (
    <div className="flex items-center gap-2 text-xs text-gray-600 mt-1">
      <span>{status.icon}</span>
      <span>{status.status}</span>
    </div>
  );
};

export const TwitterStatus = TwitterStatusComponent;