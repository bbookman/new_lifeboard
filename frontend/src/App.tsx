import { useState } from 'react'
import { NewspaperMasthead } from './components/NewspaperMasthead'
import { NavigationSidebar, type NavigationItem } from './components/NavigationSidebar'
import { CalendarView } from './components/CalendarView'
import { DayView } from './components/DayView'
import { ChatView } from './components/ChatView'
import { SettingsView } from './components/SettingsView'
import { DateNavigation } from './components/DateNavigation'

const navigationItems = [
  { id: 'day', label: 'Day', icon: '📅', path: '/day' },
  { id: 'calendar', label: 'Calendar', icon: '🗓️', path: '/calendar' },
  { id: 'chat', label: 'Chat', icon: '💬', path: '/chat' },
  { id: 'settings', label: 'Settings', icon: '⚙️', path: '/settings' },
];

function App() {
  const [activeView, setActiveView] = useState('day');
  const [selectedDate, setSelectedDate] = useState<string | undefined>(undefined);

  const handleNavigation = (item: NavigationItem) => {
    setActiveView(item.id);
    // Clear selected date when navigating away from day view
    if (item.id !== 'day') {
      setSelectedDate(undefined);
    }
  };

  const handleDateSelect = (date: string) => {
    setSelectedDate(date);
    setActiveView('day');
  };

  const handleDateChange = (date: string) => {
    setSelectedDate(date);
  };

  const renderMainContent = () => {
    switch (activeView) {
      case 'day':
        return <DayView selectedDate={selectedDate} onDateChange={handleDateChange} />;
      case 'calendar':
        return <CalendarView onDateSelect={handleDateSelect} />;
      case 'chat':
        return <ChatView />;
      case 'settings':
        return <SettingsView />;
      default:
        return <DayView selectedDate={selectedDate} onDateChange={handleDateChange} />;
    }
  };

  return (
    <div className="min-h-screen bg-background font-body">
                <NewspaperMasthead selectedDate={selectedDate} />
      
      {/* Horizontal Navigation Bar */}
      <div className="flex justify-between items-center w-full px-4 py-2 bg-white shadow-md">
        <NavigationSidebar
          items={navigationItems}
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
      <div className="container mx-auto px-4 py-8">
        {renderMainContent()}
      </div>
    </div>
  )
}

export default App