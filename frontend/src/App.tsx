import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useParams, useLocation } from 'react-router-dom'
import { NewspaperMasthead } from './components/NewspaperMasthead'
import { NavigationSidebar, type NavigationItem } from './components/NavigationSidebar'
import { CalendarView } from './components/CalendarView'
import { DayView } from './components/DayView'
import { ChatView } from './components/ChatView'
import { SettingsView } from './components/SettingsView'
import { DocumentsView } from './components/DocumentsView'
import { DateNavigation } from './components/DateNavigation'

const navigationItems = [
  { id: 'day', label: 'Day', icon: '📅', path: '/day' },
  { id: 'calendar', label: 'Calendar', icon: '🗓️', path: '/calendar' },
  { id: 'documents', label: 'Notes & Prompts', icon: '📝', path: '/documents' },
  { id: 'settings', label: 'Settings', icon: '⚙️', path: '/settings' },
];

// Main layout component that handles navigation
function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { date } = useParams<{ date: string }>();
  
  // Manual URL parsing as fallback since useParams is broken
  const manualDateExtraction = location.pathname.match(/\/day\/(\d{4}-\d{2}-\d{2})/)?.[1];
  const effectiveDate = date || manualDateExtraction;
  
  // Debug logging for URL parameter changes
  useEffect(() => {
    console.log('[App] URL params analysis:', { 
      useParamsDate: date, 
      manualExtraction: manualDateExtraction, 
      effectiveDate, 
      pathname: location.pathname 
    });
  }, [date, manualDateExtraction, effectiveDate, location.pathname]);
  
  // Determine active view based on current route
  const getActiveView = useCallback(() => {
    const path = location.pathname;
    if (path.startsWith('/day')) return 'day';
    if (path.startsWith('/calendar')) return 'calendar';
    if (path.startsWith('/documents')) return 'documents';
    if (path.startsWith('/settings')) return 'settings';
    if (path.startsWith('/chat')) return 'chat';
    return 'day';
  }, [location.pathname]);

  const [activeView, setActiveView] = useState(getActiveView());
  const [formattedDate, setFormattedDate] = useState('Loading...');

  // Update active view when route changes
  useEffect(() => {
    setActiveView(getActiveView());
  }, [location.pathname, getActiveView]);

  // Clear formatted date when not in day view
  useEffect(() => {
    console.log('[App] Active view changed:', activeView);
    if (activeView !== 'day') {
      console.log('[App] Clearing date (not day view)');
      setFormattedDate('');
    }
  }, [activeView]);

  const handleNavigation = (item: NavigationItem) => {
    // Force documents view to list mode when navigating to it
    if (item.id === 'documents') {
      window.dispatchEvent(new CustomEvent('forceDocumentsList'));
    }
    navigate(item.path);
  };

  const handleDateSelect = (selectedDate: string) => {
    navigate(`/day/${selectedDate}`);
  };

  const handleDateChange = (newDate: string) => {
    console.log('[App] handleDateChange called with:', newDate);
    console.log('[App] Navigating to:', `/day/${newDate}`);
    navigate(`/day/${newDate}`, { replace: false });
  };

  return (
    <div className="min-h-screen bg-background font-body">
      <NewspaperMasthead formattedDate={formattedDate} />
      
      {/* Horizontal Navigation Bar */}
      <div className="flex justify-between items-center w-full px-4 py-2 bg-white shadow-md">
        <NavigationSidebar
          items={navigationItems.filter(item => item.id !== 'chat')}
          activeItem={activeView}
          onItemClick={handleNavigation}
        />
        <DateNavigation
          selectedDate={effectiveDate}
          onDateChange={handleDateChange}
          isDayViewActive={activeView === 'day'}
        />
      </div>
      
      {/* Main Content Area */}
      <div className="container mx-auto px-4 py-8">
        <Routes>
          <Route path="/day/:date" element={<DayView selectedDate={effectiveDate} onDateChange={handleDateChange} setFormattedDate={setFormattedDate} />} />
          <Route path="/day" element={<DayView selectedDate={effectiveDate} onDateChange={handleDateChange} setFormattedDate={setFormattedDate} />} />
          <Route path="/" element={<DayView selectedDate={effectiveDate} onDateChange={handleDateChange} setFormattedDate={setFormattedDate} />} />
          <Route path="/calendar" element={<CalendarView onDateSelect={handleDateSelect} />} />
          <Route path="/documents" element={<DocumentsView />} />
          <Route path="/chat" element={<ChatView />} />
          <Route path="/settings" element={<SettingsView />} />
        </Routes>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <MainLayout />
    </BrowserRouter>
  );
}

export default App