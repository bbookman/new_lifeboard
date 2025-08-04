import { useState, useEffect, useRef } from 'react';
import { SectionHeader } from './SectionHeader';

interface CalendarDay {
  date: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  hasEvents?: boolean;
}

interface DaysWithDataResponse {
  all: string[];
  twitter: string[];
}

export const CalendarView = () => {
  // Component instance tracking for debugging
  const instanceId = useRef(Math.random().toString(36).substring(7));
  const renderCount = useRef(0);
  renderCount.current += 1;
  
  const [currentDate, setCurrentDate] = useState(new Date());
  const [daysWithData, setDaysWithData] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  
  // Debug logging for component lifecycle
  console.log(`[CALENDAR-${instanceId.current}] Component render #${renderCount.current} at:`, new Date().toISOString());
  console.log(`[CALENDAR-${instanceId.current}] Current state - daysWithData.size:`, daysWithData.size);
  console.log(`[CALENDAR-${instanceId.current}] Current state - daysWithData contents:`, Array.from(daysWithData));
  console.log(`[CALENDAR-${instanceId.current}] Current state - loading:`, loading);
  console.log(`[CALENDAR-${instanceId.current}] Current state - currentDate:`, currentDate.toISOString());
  
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  
  // Fetch days with data from the API
  const fetchDaysWithData = async (year: number, month: number, signal?: AbortSignal) => {
    const requestId = Math.random().toString(36).substring(7);
    const timestamp = new Date().toISOString();
    
    console.log(`[FETCH-${instanceId.current}-${requestId}] === STARTING FETCH REQUEST ===`);
    console.log(`[FETCH-${instanceId.current}-${requestId}] Timestamp: ${timestamp}`);
    console.log(`[FETCH-${instanceId.current}-${requestId}] Parameters: year=${year}, month=${month}`);
    console.log(`[FETCH-${instanceId.current}-${requestId}] Signal present: ${!!signal}`);
    console.log(`[FETCH-${instanceId.current}-${requestId}] Signal aborted: ${signal?.aborted}`);
    console.log(`[FETCH-${instanceId.current}-${requestId}] Current daysWithData state BEFORE request:`, {
      size: daysWithData.size,
      contents: Array.from(daysWithData),
      isEmpty: daysWithData.size === 0
    });
    
    try {
      setLoading(true);
      console.log(`[FETCH-${instanceId.current}-${requestId}] Loading state set to true`);
      
      const apiUrl = `http://localhost:8000/calendar/api/days-with-data?year=${year}&month=${month + 1}`;
      console.log(`[FETCH-${instanceId.current}-${requestId}] Making request to: ${apiUrl}`);
      console.log(`[FETCH-${instanceId.current}-${requestId}] Request starting at:`, new Date().toISOString());
      
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        mode: 'cors',
        signal, // Add abort signal for cleanup
      });
      
      console.log(`[FETCH-${instanceId.current}-${requestId}] Response received at:`, new Date().toISOString());
      console.log(`[FETCH-${instanceId.current}-${requestId}] Response status:`, response.status);
      console.log(`[FETCH-${instanceId.current}-${requestId}] Response statusText:`, response.statusText);
      console.log(`[FETCH-${instanceId.current}-${requestId}] Response ok:`, response.ok);
      console.log(`[FETCH-${instanceId.current}-${requestId}] Signal aborted after fetch:`, signal?.aborted);
      
      if (response.ok) {
        console.log(`[FETCH-${instanceId.current}-${requestId}] Parsing JSON response...`);
        const data: DaysWithDataResponse = await response.json();
        console.log(`[FETCH-${instanceId.current}-${requestId}] JSON parsed successfully`);
        console.log(`[FETCH-${instanceId.current}-${requestId}] Raw API Response:`, data);
        console.log(`[FETCH-${instanceId.current}-${requestId}] data.all type:`, typeof data.all);
        console.log(`[FETCH-${instanceId.current}-${requestId}] data.all isArray:`, Array.isArray(data.all));
        console.log(`[FETCH-${instanceId.current}-${requestId}] data.all length:`, data.all?.length || 0);
        console.log(`[FETCH-${instanceId.current}-${requestId}] data.all contents:`, data.all);
        
        // Detailed analysis of each date string
        if (data.all && Array.isArray(data.all)) {
          data.all.forEach((dateStr, index) => {
            console.log(`[FETCH-${instanceId.current}-${requestId}] Date ${index}: "${dateStr}" (type: ${typeof dateStr}, length: ${dateStr.length})`);
            console.log(`[FETCH-${instanceId.current}-${requestId}] Date ${index} char codes:`, Array.from(dateStr).map(c => c.charCodeAt(0)));
          });
        }
        
        // Convert array of date strings to Set for faster lookup
        console.log(`[FETCH-${instanceId.current}-${requestId}] Creating Set from data.all...`);
        const dataSet = new Set(data.all);
        console.log(`[FETCH-${instanceId.current}-${requestId}] Set created successfully`);
        console.log(`[FETCH-${instanceId.current}-${requestId}] Set size:`, dataSet.size);
        console.log(`[FETCH-${instanceId.current}-${requestId}] Set contents:`, Array.from(dataSet));
        
        // Test specific date lookups
        const testDates = ['2025-08-03', '2025-08-02', '2025-08-01', '2025-08-04'];
        testDates.forEach(testDate => {
          const hasDate = dataSet.has(testDate);
          console.log(`[FETCH-${instanceId.current}-${requestId}] Set.has("${testDate}"):`, hasDate);
        });
        
        // Only update state if request wasn't cancelled
        console.log(`[FETCH-${instanceId.current}-${requestId}] Checking if request was cancelled...`);
        console.log(`[FETCH-${instanceId.current}-${requestId}] Signal exists:`, !!signal);
        console.log(`[FETCH-${instanceId.current}-${requestId}] Signal aborted:`, signal?.aborted);
        
        if (!signal?.aborted) {
          console.log(`[FETCH-${instanceId.current}-${requestId}] === CALLING setDaysWithData ===`);
          console.log(`[FETCH-${instanceId.current}-${requestId}] About to set state with Set of size:`, dataSet.size);
          console.log(`[FETCH-${instanceId.current}-${requestId}] State update timestamp:`, new Date().toISOString());
          
          setDaysWithData(dataSet);
          
          console.log(`[FETCH-${instanceId.current}-${requestId}] setDaysWithData called successfully`);
          console.log(`[FETCH-${instanceId.current}-${requestId}] Note: State update is async, will check actual state in useEffect`);
        } else {
          console.log(`[FETCH-${instanceId.current}-${requestId}] Request was aborted, NOT updating state`);
        }
      } else {
        console.error(`[FETCH-${instanceId.current}-${requestId}] HTTP Error:`, response.status, response.statusText);
        try {
          const errorText = await response.text();
          console.error(`[FETCH-${instanceId.current}-${requestId}] Error response body:`, errorText);
        } catch (e) {
          console.error(`[FETCH-${instanceId.current}-${requestId}] Could not read error response body`);
        }
      }
    } catch (error) {
      // Don't log errors for aborted requests
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[CALENDAR DEBUG] Request was aborted');
        return;
      }
      
      console.error('[CALENDAR DEBUG] Fetch exception:', error);
      console.log('[CALENDAR DEBUG] Error type:', typeof error);
      console.log('[CALENDAR DEBUG] Error name:', error?.name);
      console.log('[CALENDAR DEBUG] Error message:', error?.message);
      console.log('[CALENDAR DEBUG] Error stack:', error?.stack);
      
      // Check for common network errors
      if (error instanceof TypeError) {
        console.error('[CALENDAR DEBUG] Network error - possible causes:');
        console.error('[CALENDAR DEBUG] - Backend server not running');
        console.error('[CALENDAR DEBUG] - CORS issues');
        console.error('[CALENDAR DEBUG] - Invalid URL');
        console.error('[CALENDAR DEBUG] - Firewall blocking requests');
      }
    } finally {
      console.log(`[CALENDAR DEBUG] Fetch operation completed at:`, new Date().toISOString());
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  };

  // Monitor daysWithData state changes
  useEffect(() => {
    console.log(`[STATE-${instanceId.current}] === daysWithData STATE CHANGED ===`);
    console.log(`[STATE-${instanceId.current}] Timestamp:`, new Date().toISOString());
    console.log(`[STATE-${instanceId.current}] New daysWithData size:`, daysWithData.size);
    console.log(`[STATE-${instanceId.current}] New daysWithData contents:`, Array.from(daysWithData));
    console.log(`[STATE-${instanceId.current}] Is empty:`, daysWithData.size === 0);
    
    // Test specific date lookups after state change
    const criticalDates = ['2025-08-01', '2025-08-02', '2025-08-03', '2025-08-04'];
    criticalDates.forEach(date => {
      const hasDate = daysWithData.has(date);
      console.log(`[STATE-${instanceId.current}] After state change - daysWithData.has("${date}"):`, hasDate);
    });
  }, [daysWithData]);

  // Fetch data when component mounts or date changes
  useEffect(() => {
    const abortController = new AbortController();
    
    console.log(`[EFFECT-${instanceId.current}] === useEffect triggered for date change ===`);
    console.log(`[EFFECT-${instanceId.current}] Date:`, currentDate.toISOString());
    console.log(`[EFFECT-${instanceId.current}] Current daysWithData before fetch:`, {
      size: daysWithData.size,
      contents: Array.from(daysWithData)
    });
    
    fetchDaysWithData(currentDate.getFullYear(), currentDate.getMonth(), abortController.signal);
    
    // Cleanup function to abort the request if component unmounts or date changes
    return () => {
      console.log(`[EFFECT-${instanceId.current}] useEffect cleanup - aborting request`);
      abortController.abort();
    };
  }, [currentDate]);
  
  const generateCalendarDays = (): CalendarDay[] => {
    const generationId = Math.random().toString(36).substring(7);
    const timestamp = new Date().toISOString();
    
    console.log(`[GENERATE-${instanceId.current}-${generationId}] === STARTING CALENDAR GENERATION ===`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Timestamp: ${timestamp}`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Render count: ${renderCount.current}`);
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const today = new Date();
    
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Generating for: ${year}-${month + 1}`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] daysWithData state at generation time:`, {
      size: daysWithData.size,
      contents: Array.from(daysWithData),
      isEmpty: daysWithData.size === 0,
      setObject: daysWithData
    });
    
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
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Processing ${daysInMonth} days for current month`);
    
    for (let day = 1; day <= daysInMonth; day++) {
      const isToday =
        year === today.getFullYear() &&
        month === today.getMonth() &&
        day === today.getDate();
      
      // Check if this day has data in the database
      const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      
      console.log(`[GENERATE-${instanceId.current}-${generationId}] === Processing Day ${day} ===`);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] Generated dateString: "${dateString}"`);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] dateString length: ${dateString.length}`);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] dateString type: ${typeof dateString}`);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] dateString char codes:`, Array.from(dateString).map(c => c.charCodeAt(0)));
      
      // State verification at the moment of lookup
      console.log(`[GENERATE-${instanceId.current}-${generationId}] daysWithData reference check:`, daysWithData === daysWithData);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] daysWithData.size at lookup: ${daysWithData.size}`);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] daysWithData contents at lookup:`, Array.from(daysWithData));
      
      // Perform the actual lookup
      const hasEvents = daysWithData.has(dateString);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] daysWithData.has("${dateString}") = ${hasEvents}`);
      
      // Double-check with manual iteration
      let manualCheck = false;
      for (const item of daysWithData) {
        if (item === dateString) {
          manualCheck = true;
          break;
        }
      }
      console.log(`[GENERATE-${instanceId.current}-${generationId}] Manual iteration check: ${manualCheck}`);
      
      // String comparison tests
      const setArray = Array.from(daysWithData);
      const exactMatches = setArray.filter(item => item === dateString);
      const looseMatches = setArray.filter(item => item == dateString);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] Exact matches (===): ${exactMatches.length}`, exactMatches);
      console.log(`[GENERATE-${instanceId.current}-${generationId}] Loose matches (==): ${looseMatches.length}`, looseMatches);
      
      // Log detailed comparison for critical dates
      if (day <= 4) {
        console.log(`[GENERATE-${instanceId.current}-${generationId}] CRITICAL DAY ${day} ANALYSIS:`);
        setArray.forEach((setItem, index) => {
          console.log(`[GENERATE-${instanceId.current}-${generationId}]   Set item ${index}: "${setItem}" (${setItem.length} chars)`);
          console.log(`[GENERATE-${instanceId.current}-${generationId}]   === comparison: ${setItem === dateString}`);
          console.log(`[GENERATE-${instanceId.current}-${generationId}]   Character codes:`, Array.from(setItem).map(c => c.charCodeAt(0)));
        });
      }
      
      console.log(`[GENERATE-${instanceId.current}-${generationId}] FINAL RESULT - Day ${day}: hasEvents=${hasEvents}`);
      
      days.push({
        date: day,
        isCurrentMonth: true,
        isToday,
        hasEvents
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
    
    // Summary of generated calendar
    const currentMonthDays = days.filter(d => d.isCurrentMonth);
    const daysWithEvents = currentMonthDays.filter(d => d.hasEvents);
    
    console.log(`[GENERATE-${instanceId.current}-${generationId}] === CALENDAR GENERATION COMPLETE ===`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Total days generated: ${days.length}`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Current month days: ${currentMonthDays.length}`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Days with events: ${daysWithEvents.length}`);
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Days with events details:`, daysWithEvents.map(d => ({ date: d.date, hasEvents: d.hasEvents })));
    console.log(`[GENERATE-${instanceId.current}-${generationId}] Final daysWithData state:`, {
      size: daysWithData.size,
      contents: Array.from(daysWithData)
    });
    
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
  
  const calendarDays = generateCalendarDays();
  
  return (
    <div className="calendar-view">
      <SectionHeader 
        title="Editorial Calendar"
        subtitle="Your digital life, organized by date"
        accentColor="border-news-accent"
      />
      
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
                    } ${day.isToday ? 'today' : ''} ${day.hasEvents ? 'has-events' : ''}`}
                  >
                    <span className="calendar-day-number">{day.date}</span>
                    {day.hasEvents && day.isCurrentMonth && (
                      <div className="calendar-events">
                        <div className="event-dot"></div>
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
          <div className="card-header">
            <h3 className="card-title">Legend</h3>
          </div>
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