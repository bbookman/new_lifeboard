import { useState, useEffect, useRef } from 'react';
import { getTodayYYYYMMDD } from '../lib/utils';

interface CalendarDay {
  date: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  hasEvents?: boolean; // Keep for general data presence
  hasNewsEvents?: boolean;
  hasLimitlessEvents?: boolean;
  hasTwitterEvents?: boolean;
}

interface SyncStatus {
  is_complete: boolean;
  is_in_progress: boolean;
  completed_sources: number;
  failed_sources: number;
  in_progress_sources: number;
  total_sources: number;
  overall_progress: number;
  sources: Record<string, {
    namespace: string;
    source_type: string;
    status: string;
    progress_percentage: number;
    error_message?: string;
  }>;
}

interface DaysWithDataResponse {
  data: {
    [key: string]: string[]; // Allows for dynamic keys like 'news', 'limitless', etc.
    all: string[]; // Still expect 'all' to be present
  };
  sync_status?: SyncStatus;
}

interface CalendarViewProps {
  onDateSelect?: (date: string) => void;
}

export const CalendarView = ({ onDateSelect }: CalendarViewProps) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [allDaysWithData, setAllDaysWithData] = useState<Set<string>>(new Set());
  const [newsDaysWithData, setNewsDaysWithData] = useState<Set<string>>(new Set());
  const [limitlessDaysWithData, setLimitlessDaysWithData] = useState<Set<string>>(new Set());
  const [twitterDaysWithData, setTwitterDaysWithData] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [serverToday, setServerToday] = useState<string>('');
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  
  // Initialize server today on component mount
  useEffect(() => {
    const initializeServerToday = async () => {
      const today = await getTodayYYYYMMDD();
      setServerToday(today);
    };
    initializeServerToday();
  }, []);
  
  // Calculate date range for calendar view (includes prev/next month dates)
  const getCalendarDateRange = (year: number, month: number) => {
    const firstDayOfMonth = new Date(year, month, 1);
    const firstDayOfWeek = firstDayOfMonth.getDay();
    
    // Calculate start date (previous month's trailing days)
    const startDate = new Date(year, month, 1 - firstDayOfWeek);
    
    // Calculate end date (6 weeks from start = 42 days)
    const endDate = new Date(startDate);
    endDate.setDate(startDate.getDate() + 41);
    
    return {
      startYear: startDate.getFullYear(),
      startMonth: startDate.getMonth() + 1,
      endYear: endDate.getFullYear(),
      endMonth: endDate.getMonth() + 1
    };
  };

  // Fetch days with data from the API
  const fetchDaysWithData = async (year: number, month: number, signal?: AbortSignal) => {
    console.log(`[CALENDAR] Fetching data for ${year}-${month + 1}`);
    
    try {
      setLoading(true);
      
      const { startYear, startMonth, endYear, endMonth } = getCalendarDateRange(year, month);
      console.log(`[CALENDAR] Date range: ${startYear}-${startMonth} to ${endYear}-${endMonth}`);
      
      // Fetch data for all months that appear in the calendar view
      const monthsToFetch = new Set<string>();
      
      // Add start month
      monthsToFetch.add(`${startYear}-${startMonth}`);
      
      // Add current month
      monthsToFetch.add(`${year}-${month + 1}`);
      
      // Add end month if different
      if (endYear !== startYear || endMonth !== startMonth) {
        monthsToFetch.add(`${endYear}-${endMonth}`);
      }
      
      console.log(`[CALENDAR] Fetching data for months: ${Array.from(monthsToFetch).join(', ')}`);
      
      // Fetch data for each month and combine results
      const allDataSets: DaysWithDataResponse[] = [];
      
      for (const monthKey of monthsToFetch) {
        const [fetchYear, fetchMonth] = monthKey.split('-').map(Number);
        const apiUrl = `http://localhost:8000/calendar/days-with-data?year=${fetchYear}&month=${fetchMonth}`;
        
        const response = await fetch(apiUrl, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          mode: 'cors',
          signal,
          cache: 'no-cache',
        });
        
        if (response.ok) {
          const monthData: DaysWithDataResponse = await response.json();
          allDataSets.push(monthData);
        } else {
          console.error(`[CALENDAR] HTTP Error for ${monthKey}:`, response.status, response.statusText);
        }
      }
      
      if (allDataSets.length === 0) {
        throw new Error('No data retrieved from any month');
      }
      
      // Combine all data from different months
      const combinedData: { [key: string]: string[] } = {
        all: [],
        news: [],
        limitless: [],
        twitter: []
      };
      
      let latestSyncStatus: SyncStatus | null = null;
      
      for (const dataSet of allDataSets) {
        if (dataSet.data) {
          Object.keys(dataSet.data).forEach(key => {
            if (!combinedData[key]) {
              combinedData[key] = [];
            }
            combinedData[key] = [...combinedData[key], ...dataSet.data[key]];
          });
        }
        
        // Use the most recent sync status
        if (dataSet.sync_status) {
          latestSyncStatus = dataSet.sync_status;
        }
      }
      
      // Remove duplicates from combined data
      Object.keys(combinedData).forEach(key => {
        combinedData[key] = [...new Set(combinedData[key])];
      });
      
      console.log(`[CALENDAR] Combined data: all=${combinedData.all?.length || 0}, news=${combinedData.news?.length || 0}, limitless=${combinedData.limitless?.length || 0}, twitter=${combinedData.twitter?.length || 0}`);
      
      if (!signal?.aborted) {
        setAllDaysWithData(new Set(combinedData.all || []));
        setNewsDaysWithData(new Set(combinedData.news || []));
        setLimitlessDaysWithData(new Set(combinedData.limitless || []));
        setTwitterDaysWithData(new Set(combinedData.twitter || []));
        
        // Update sync status
        setSyncStatus(latestSyncStatus);
        
        if (latestSyncStatus) {
          console.log(`[CALENDAR] Sync status: ${latestSyncStatus.completed_sources}/${latestSyncStatus.total_sources} complete`);
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return; // Silently handle aborted requests
      }
      
      console.error('[CALENDAR] Fetch error:', error);
      
      // Set empty data sets as fallback to prevent UI issues
      if (!signal?.aborted) {
        setAllDaysWithData(new Set());
        setNewsDaysWithData(new Set());
        setLimitlessDaysWithData(new Set());
        setTwitterDaysWithData(new Set());
        setSyncStatus(null);
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  };

  // Monitor allDaysWithData state changes  
  useEffect(() => {
    console.log(`[CALENDAR] All days with data updated: ${allDaysWithData.size} days`);
  }, [allDaysWithData]);

  // WebSocket for real-time sync updates
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;

    const connectWebSocket = () => {
      try {
        ws = new WebSocket('ws://localhost:8000/ws/processing');
        
        ws.onopen = () => {
          console.log('[CALENDAR] WebSocket connected for sync updates');
          // Subscribe to sync status updates
          ws?.send(JSON.stringify({
            type: 'subscribe',
            topics: ['sync_status', 'sync_progress']
          }));
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log('[CALENDAR] WebSocket message received:', message);
            
            if (message.type === 'sync_status' || message.type === 'sync_progress') {
              // Refresh calendar data when sync updates occur
              fetchDaysWithData(currentDate.getFullYear(), currentDate.getMonth());
            }
          } catch (error) {
            console.error('[CALENDAR] Error parsing WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.log('[CALENDAR] WebSocket error:', error);
        };

        ws.onclose = () => {
          console.log('[CALENDAR] WebSocket disconnected');
          // Attempt to reconnect after 5 seconds
          reconnectTimeout = setTimeout(connectWebSocket, 5000);
        };

      } catch (error) {
        console.error('[CALENDAR] Failed to connect WebSocket:', error);
        // Attempt to reconnect after 5 seconds
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
      }
    };

    // Only connect WebSocket if sync is not complete
    if (!syncStatus || !syncStatus.is_complete) {
      connectWebSocket();
    }

    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (ws) {
        ws.close();
      }
    };
  }, [currentDate, syncStatus?.is_complete]); // Reconnect when month changes or sync completes

  // Fetch data when component mounts or date changes
  useEffect(() => {
    const abortController = new AbortController();
    
    const fetchWithRetry = async (retries = 2) => {
      try {
        await fetchDaysWithData(currentDate.getFullYear(), currentDate.getMonth(), abortController.signal);
      } catch (error) {
        if (retries > 0 && !abortController.signal.aborted) {
          console.log(`[CALENDAR] Retrying... (${retries} attempts left)`);
          setTimeout(() => fetchWithRetry(retries - 1), 1000);
        }
      }
    };
    
    fetchWithRetry();
    
    return () => {
      abortController.abort();
    };
  }, [currentDate]);
  
  const generateCalendarDays = (): CalendarDay[] => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const firstDayOfMonth = new Date(year, month, 1);
    const lastDayOfMonth = new Date(year, month + 1, 0);
    const firstDayOfWeek = firstDayOfMonth.getDay();
    const daysInMonth = lastDayOfMonth.getDate();
    
    const days: CalendarDay[] = [];
    
    // Previous month's trailing days
    const prevMonth = new Date(year, month - 1, 0);
    const prevMonthYear = month === 0 ? year - 1 : year;
    const prevMonthMonth = month === 0 ? 11 : month - 1;
    
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      const dayNumber = prevMonth.getDate() - i;
      const dateString = `${prevMonthYear}-${String(prevMonthMonth + 1).padStart(2, '0')}-${String(dayNumber).padStart(2, '0')}`;
      
      const hasEvents = allDaysWithData.has(dateString);
      const hasNewsEvents = newsDaysWithData.has(dateString);
      const hasLimitlessEvents = limitlessDaysWithData.has(dateString);
      const hasTwitterEvents = twitterDaysWithData.has(dateString);
      
      days.push({
        date: dayNumber,
        isCurrentMonth: false,
        isToday: false,
        hasEvents,
        hasNewsEvents,
        hasLimitlessEvents,
        hasTwitterEvents
      });
    }
    
    // Current month's days
    for (let day = 1; day <= daysInMonth; day++) {
      // Check if this day matches the server's today and has data
      const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isToday = dateString === serverToday;
      const hasEvents = allDaysWithData.has(dateString); // General data presence
      const hasNewsEvents = newsDaysWithData.has(dateString);
      const hasLimitlessEvents = limitlessDaysWithData.has(dateString);
      const hasTwitterEvents = twitterDaysWithData.has(dateString);
      
      days.push({
        date: day,
        isCurrentMonth: true,
        isToday,
        hasEvents,
        hasNewsEvents,
        hasLimitlessEvents,
        hasTwitterEvents
      });
    }
    
    // Next month's leading days
    const remainingDays = 42 - days.length; // 6 weeks * 7 days
    const nextMonthYear = month === 11 ? year + 1 : year;
    const nextMonthMonth = month === 11 ? 0 : month + 1;
    
    for (let day = 1; day <= remainingDays; day++) {
      const dateString = `${nextMonthYear}-${String(nextMonthMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      
      const hasEvents = allDaysWithData.has(dateString);
      const hasNewsEvents = newsDaysWithData.has(dateString);
      const hasLimitlessEvents = limitlessDaysWithData.has(dateString);
      const hasTwitterEvents = twitterDaysWithData.has(dateString);
      
      days.push({
        date: day,
        isCurrentMonth: false,
        isToday: false,
        hasEvents,
        hasNewsEvents,
        hasLimitlessEvents,
        hasTwitterEvents
      });
    }
    
    return days;
  };
  
  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentDate(prev => {
      const newDate = new Date(prev);
      if (direction === 'prev') {
        newDate.setMonth(prev.getMonth() - 1);
      } else {
        newDate.setMonth(prev.getMonth() + 1);
      }
      return newDate;
    });
  };

  const handleDayClick = (day: CalendarDay, dayIndex: number) => {
    // Handle clicks for any day that has events (including prev/next month)
    if (day.hasEvents && onDateSelect) {
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth();
      
      // Calculate the actual date based on position in the calendar
      const firstDayOfMonth = new Date(year, month, 1);
      const firstDayOfWeek = firstDayOfMonth.getDay();
      const startDate = new Date(year, month, 1 - firstDayOfWeek);
      const targetDate = new Date(startDate);
      targetDate.setDate(startDate.getDate() + dayIndex);
      
      const dateString = `${targetDate.getFullYear()}-${String(targetDate.getMonth() + 1).padStart(2, '0')}-${String(targetDate.getDate()).padStart(2, '0')}`;
      console.log('[CALENDAR] Day clicked:', dateString);
      onDateSelect(dateString);
    }
  };
  
  const calendarDays = generateCalendarDays();
  
  return (
    <div className="calendar-view">
      {/* Sync Status Banner */}
      {syncStatus && !syncStatus.is_complete && (
        <div className="sync-status-banner mb-6">
          <div className="card">
            <div className="card-content" style={{ padding: '1rem' }}>
              <div className="alert" style={{ 
                backgroundColor: '#e3f2fd', 
                border: '1px solid #2196f3',
                borderRadius: '8px',
                padding: '1rem'
              }}>
                <div className="flex items-center gap-3 mb-3">
                  <span style={{ fontSize: '1.2rem' }}>📡</span>
                  <div>
                    <strong>Data syncing in progress</strong>
                    <div style={{ fontSize: '0.9rem', color: '#666' }}>
                      {syncStatus.completed_sources} of {syncStatus.total_sources} sources complete 
                      ({Math.round(syncStatus.overall_progress)}%)
                    </div>
                  </div>
                </div>
                
                {/* Progress Bar */}
                <div style={{ 
                  backgroundColor: '#f0f0f0', 
                  borderRadius: '4px', 
                  height: '8px',
                  marginBottom: '1rem',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    backgroundColor: '#2196f3',
                    height: '100%',
                    width: `${syncStatus.overall_progress}%`,
                    transition: 'width 0.3s ease'
                  }} />
                </div>
                
                {/* Source Status */}
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                  {Object.entries(syncStatus.sources).map(([namespace, source]) => (
                    <div key={namespace} style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '0.5rem',
                      fontSize: '0.85rem'
                    }}>
                      <span>
                        {source.status === 'completed' ? '✅' : 
                         source.status === 'in_progress' ? '⏳' : 
                         source.status === 'failed' ? '❌' : 
                         source.status === 'skipped' ? '⏭️' : '⭕'}
                      </span>
                      <span style={{ textTransform: 'capitalize' }}>
                        {namespace}
                      </span>
                      {source.status === 'in_progress' && (
                        <span style={{ color: '#666' }}>
                          ({Math.round(source.progress_percentage)}%)
                        </span>
                      )}
                      {source.status === 'skipped' && source.error_message && (
                        <span style={{ color: '#ff9800', fontSize: '0.8rem' }}>
                          Skipped
                        </span>
                      )}
                      {source.status === 'failed' && source.error_message && (
                        <span style={{ color: '#d32f2f', fontSize: '0.8rem' }}>
                          Error
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {syncStatus && syncStatus.is_complete && (
        <div className="sync-complete-banner mb-6">
          <div className="card">
            <div className="card-content" style={{ padding: '1rem' }}>
              <div className="alert" style={{ 
                backgroundColor: '#e8f5e8', 
                border: '1px solid #4caf50',
                borderRadius: '8px',
                padding: '1rem'
              }}>
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: '1.2rem' }}>✅</span>
                  <strong style={{ color: '#2e7d32' }}>All data sources synchronized</strong>
                  <span style={{ fontSize: '0.9rem', color: '#666', marginLeft: '1rem' }}>
                    {syncStatus.total_sources} sources up to date
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Calendar Header */}
      <div className="card mb-8">
        <div className="card-header">
          <div className="flex justify-between items-center">
            <button 
              onClick={() => navigateMonth('prev')}
              className="button button-outline"
              style={{ padding: '0.5rem 1rem' }}
            >
              ← Previous
            </button>
            
            <h2 className="text-2xl font-bold">
              {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
            </h2>
            
            <button 
              onClick={() => navigateMonth('next')}
              className="button button-outline"
              style={{ padding: '0.5rem 1rem' }}
            >
              Next →
            </button>
          </div>
        </div>
      </div>
      
      {/* Calendar Grid */}
      <div className="card">
        <div className="card-content" style={{ padding: '1.5rem' }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
              Loading calendar data...
            </div>
          )}
          
          {!loading && (
            <>
              {/* Day Headers */}
              <div className="calendar-grid-header">
                {dayNames.map(day => (
                  <div key={day} className="calendar-day-header">
                    {day}
                  </div>
                ))}
              </div>
              
              {/* Calendar Days */}
              <div className="calendar-grid">
                {calendarDays.map((day, index) => (
                  <div
                    key={index}
                    className={`calendar-day ${
                      day.isCurrentMonth ? 'current-month' : 'other-month'
                    } ${day.isToday ? 'today' : ''} ${day.hasEvents ? 'has-events' : ''} ${
                      day.hasEvents ? 'clickable' : ''
                    }`}
                    onClick={() => handleDayClick(day, index)}
                    style={{
                      cursor: day.hasEvents ? 'pointer' : 'default'
                    }}
                  >
                    <span className="calendar-day-number">{day.date}</span>
                    {(day.hasNewsEvents || day.hasLimitlessEvents || day.hasTwitterEvents) && (
                      <div className="calendar-icons-container">
                        {day.hasLimitlessEvents && (
                          <img src="/src/assets/limitless-logo.svg" alt="Limitless Data" className="calendar-icon limitless-icon" />
                        )}
                        {day.hasNewsEvents && (
                          <span className="calendar-icon news-icon">📰</span>
                        )}
                        {day.hasTwitterEvents && (
                          <img src="/src/assets/logo-black.png" alt="Twitter Data" className="calendar-icon twitter-icon" />
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      
      {/* Legend */}
      <div className="mt-6">
        <div className="card">
          <div className="card-content">
            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <div className="legend-today"></div>
                <span className="text-sm">Today</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="legend-events"></div>
                <span className="text-sm">Has Data</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="legend-other"></div>
                <span className="text-sm">Other Months</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};