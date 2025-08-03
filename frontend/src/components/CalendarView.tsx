import { useState, useEffect } from 'react';
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
  const [currentDate, setCurrentDate] = useState(new Date());
  const [daysWithData, setDaysWithData] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  
  // Fetch days with data from the API
  const fetchDaysWithData = async (year: number, month: number) => {
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8000/calendar/api/days-with-data?year=${year}&month=${month + 1}`);
      if (response.ok) {
        const data: DaysWithDataResponse = await response.json();
        // Convert array of date strings to Set for faster lookup
        const dataSet = new Set(data.all);
        setDaysWithData(dataSet);
      } else {
        console.error('Failed to fetch calendar data:', response.statusText);
      }
    } catch (error) {
      console.error('Error fetching calendar data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch data when component mounts or date changes
  useEffect(() => {
    fetchDaysWithData(currentDate.getFullYear(), currentDate.getMonth());
  }, [currentDate]);
  
  const generateCalendarDays = (): CalendarDay[] => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const today = new Date();
    
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
      const isToday = 
        year === today.getFullYear() &&
        month === today.getMonth() &&
        day === today.getDate();
      
      // Check if this day has data in the database
      const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const hasEvents = daysWithData.has(dateString);
      
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