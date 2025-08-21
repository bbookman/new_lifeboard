import { useState } from 'react';
import { NewspaperMasthead } from './components/NewspaperMasthead';
import { NavigationSidebar, type NavigationItem } from './components/NavigationSidebar';
import { CalendarView } from './components/CalendarView';
import { DayView } from './components/DayView';
import { ChatView } from './components/ChatView';
import { SettingsView } from './components/SettingsView';
import { DocumentsView } from './components/DocumentsView';
import { DateNavigation } from './components/DateNavigation';
import { LimitlessExpandedView } from './components/LimitlessExpandedView';

const navigationItems = [
  { id: 'day', label: 'Day', icon: '📅', path: '/day' },
  { id: 'calendar', label: 'Calendar', icon: '🗓️', path: '/calendar' },
  { id: 'documents', label: 'Notes & Prompts', icon: '📝', path: '/documents' },
  { id: 'settings', label: 'Settings', icon: '⚙️', path: '/settings' },
];

function App() {
  const [activeView, setActiveView] = useState('day');
  const [selectedDate, setSelectedDate] = useState<string | undefined>(undefined);
  const [showLimitlessExpanded, setShowLimitlessExpanded] = useState(false);
  const [limitlessExpandedContent, setLimitlessExpandedContent] = useState<string>('');

  const handleNavigation = (item: NavigationItem) => {
    setActiveView(item.id);
    // Clear selected date when navigating away from day view
    if (item.id !== 'day') {
      setSelectedDate(undefined);
    }
    // Force documents view to list mode when navigating to it
    if (item.id === 'documents') {
      window.dispatchEvent(new CustomEvent('forceDocumentsList'));
    }
  };

  const handleDateSelect = (date: string) => {
    setSelectedDate(date);
    setActiveView('day');
  };

  const handleDateChange = (date: string) => {
    setSelectedDate(date);
  };

  const handleExpandLimitless = (content: string) => {
    setLimitlessExpandedContent(content);
    setShowLimitlessExpanded(true);
  };

  const handleCloseLimitlessExpanded = () => {
    setShowLimitlessExpanded(false);
  };

  const renderMainContent = () => {
    switch (activeView) {
      case 'day':
        return (
          <DayView
            selectedDate={selectedDate}
            onDateChange={handleDateChange}
            onExpandLimitless={handleExpandLimitless}
          />
        );
      case 'calendar':
        return <CalendarView onDateSelect={handleDateSelect} />;
      case 'documents':
        return <DocumentsView />;
      case 'chat':
        return <ChatView />;
      case 'settings':
        return <SettingsView />;
      default:
        return (
          <DayView
            selectedDate={selectedDate}
            onDateChange={handleDateChange}
            onExpandLimitless={handleExpandLimitless}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-background font-body">
      <NewspaperMasthead selectedDate={selectedDate} />

      {/* Horizontal Navigation Bar */}
      <div className="flex justify-between items-center w-full px-4 py-2 bg-white shadow-md">
        <NavigationSidebar
          items={navigationItems.filter((item) => item.id !== 'chat')}
          activeItem={activeView}
          onItemClick={handleNavigation}
        />
        <DateNavigation
          selectedDate={selectedDate}
          onDateChange={handleDateChange}
          isDayViewActive={activeView === 'day'}
        />
      </div>

      {/* Main Content Area */}
      <div className="container mx-auto px-4 py-8">{renderMainContent()}</div>

      {/* Limitless Expanded View Overlay */}
      {showLimitlessExpanded && (
        <LimitlessExpandedView
          selectedDate={selectedDate}
          content={limitlessExpandedContent}
          onClose={handleCloseLimitlessExpanded}
        />
      )}
    </div>
  );
}

export default App;
