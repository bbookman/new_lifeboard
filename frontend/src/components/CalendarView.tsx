import { useState, useEffect, useRef } from 'react';
import { SectionHeader } from './SectionHeader';
import { getTodayYYYYMMDD } from '../lib/utils';

interface CalendarDay {
  date: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  hasEvents?: boolean; // Keep for general data presence
  hasNewsEvents?: boolean;
  hasLimitlessEvents?: boolean;
}

interface DaysWithDataResponse {
  [key: string]: string[]; // Allows for dynamic keys like 'news', 'limitless', etc.
  all: string[]; // Still expect 'all' to be present
}

interface CalendarViewProps {
  onDateSelect?: (date: string) => void;
}

export const CalendarView = ({ onDateSelect }: CalendarViewProps) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [allDaysWithData, setAllDaysWithData] = useState<Set<string>>(new Set());
  const [newsDaysWithData, setNewsDaysWithData] = useState<Set<string>>(new Set());
  const [limitlessDaysWithData, setLimitlessDaysWithData] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [serverToday, setServerToday] = useState<string>('');
  
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
  
  // Fetch days with data from the API
  const fetchDaysWithData = async (year: number, month: number, signal?: AbortSignal) => {
    console.log(`[CALENDAR] Fetching data for ${year}-${month + 1}`);
    
    try {
      setLoading(true);
      
      const apiUrl = `http://localhost:8000/calendar/api/days-with-data?year=${year}&month=${month + 1}`;
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        mode: 'cors',
        signal,
        // Add timeout and retry-friendly settings
        cache: 'no-cache',
      });
      
      if (response.ok) {
        const data: DaysWithDataResponse = await response.json();
        console.log(`[CALENDAR] Received data for ${Object.keys(data).length} namespaces`);
        
        if (!signal?.aborted) {
          setAllDaysWithData(new Set(data.all || []));
          setNewsDaysWithData(new Set(data.news || []));
          setLimitlessDaysWithData(new Set(data.limitless || []));
          // Add more sets for other namespaces as needed
        }
      } else {
        console.error(`[CALENDAR] HTTP Error:`, response.status, response.statusText);
        // Set empty data sets as fallback for HTTP errors too
        if (!signal?.aborted) {
          setAllDaysWithData(new Set());
          setNewsDaysWithData(new Set());
          setLimitlessDaysWithData(new Set());
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
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      days.push({
        date: prevMonth.getDate() - i,
        isCurrentMonth: false,
        isToday: false
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
      
      days.push({
        date: day,
        isCurrentMonth: true,
        isToday,
        hasEvents,
        hasNewsEvents,
        hasLimitlessEvents
      });
    }
    
    // Next month's leading days
    const remainingDays = 42 - days.length; // 6 weeks * 7 days
    for (let day = 1; day <= remainingDays; day++) {
      days.push({
        date: day,
        isCurrentMonth: false,
        isToday: false
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

  const handleDayClick = (day: CalendarDay) => {
    // Only handle clicks for current month days that have events
    if (day.isCurrentMonth && day.hasEvents && onDateSelect) {
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth();
      const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day.date).padStart(2, '0')}`;
      console.log('[CALENDAR] Day clicked:', dateString);
      onDateSelect(dateString);
    }
  };
  
  const calendarDays = generateCalendarDays();
  
  return (
    <div className="calendar-view">

      
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
                      day.isCurrentMonth && day.hasEvents ? 'clickable' : ''
                    }`}
                    onClick={() => handleDayClick(day)}
                    style={{
                      cursor: day.isCurrentMonth && day.hasEvents ? 'pointer' : 'default'
                    }}
                  >
                    <span className="calendar-day-number">{day.date}</span>
                    {day.isCurrentMonth && (day.hasNewsEvents || day.hasLimitlessEvents) && (
                      <div className="calendar-icons-container">
                        {day.hasLimitlessEvents && (
                          <img src="/src/assets/limitless-logo.svg" alt="Limitless Data" className="calendar-icon limitless-icon" />
                        )}
                        {day.hasNewsEvents && (
                          <span className="calendar-icon news-icon">📰</span>
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