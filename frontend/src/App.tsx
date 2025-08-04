import { useState } from 'react'
import { NewspaperLayout } from './components/NewspaperLayout'
import { NavigationSidebar, type NavigationItem } from './components/NavigationSidebar'
import { SectionHeader } from './components/SectionHeader'
import { CalendarView } from './components/CalendarView'
import { DayView } from './components/DayView'
import { ChatView } from './components/ChatView'
import { SettingsView } from './components/SettingsView'

const navigationItems = [
  { id: 'day', label: 'Day View', icon: '📅', path: '/day' },
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
        return (
          <>
            <SectionHeader 
              title="Welcome to Lifeboard"
              accentColor="border-news-accent"
            />
            
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Today's Overview</h3>
                </div>
                <div className="card-content">
                  <p className="text-muted">
                    Track your conversations, activities, and experiences in a beautiful newspaper-style interface.
                  </p>
                  <button 
                    onClick={() => setActiveView('calendar')}
                    className="button button-primary mt-4"
                  >
                    View Today
                  </button>
                </div>
              </div>
              
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Recent Activity</h3>
                </div>
                <div className="card-content">
                  <p className="text-muted">
                    Browse through your digital life with our intuitive calendar and search features.
                  </p>
                  <button 
                    onClick={() => setActiveView('calendar')}
                    className="button button-outline mt-4"
                  >
                    Browse Calendar
                  </button>
                </div>
              </div>
            </div>
            
            <div className="mt-8">
              <SectionHeader 
                title="Quick Stats"
                subtitle="Your digital life at a glance"
                accentColor="border-social-accent"
              />
              
              <div className="grid md:grid-cols-3 gap-4">
                <div className="card">
                  <div className="card-content p-6">
                    <div className="text-center">
                      <div className="text-3xl font-bold text-news-accent">42</div>
                      <div className="text-sm text-muted">Total Conversations</div>
                    </div>
                  </div>
                </div>
                
                <div className="card">
                  <div className="card-content p-6">
                    <div className="text-center">
                      <div className="text-3xl font-bold text-social-accent">128</div>
                      <div className="text-sm text-muted">Activities Tracked</div>
                    </div>
                  </div>
                </div>
                
                <div className="card">
                  <div className="card-content p-6">
                    <div className="text-center">
                      <div className="text-3xl font-bold text-music-accent">7</div>
                      <div className="text-sm text-muted">Days Active</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="mt-8">
              <SectionHeader 
                title="Get Started"
                subtitle="Explore your digital life"
                accentColor="border-music-accent"
              />
              
              <div className="grid md:grid-cols-2 gap-6">
                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">💬 Chat with Your Data</h3>
                  </div>
                  <div className="card-content">
                    <p className="text-muted">
                      Ask questions about your conversations, activities, and patterns. Get insights powered by AI.
                    </p>
                    <button 
                      onClick={() => setActiveView('chat')}
                      className="button button-primary mt-4"
                    >
                      Start Chatting
                    </button>
                  </div>
                </div>
                
                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">⚙️ Customize Experience</h3>
                  </div>
                  <div className="card-content">
                    <p className="text-muted">
                      Configure data sources, privacy settings, and AI behavior to match your preferences.
                    </p>
                    <button 
                      onClick={() => setActiveView('settings')}
                      className="button button-outline mt-4"
                    >
                      Open Settings
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </>
        );
    }
  };

  return (
    <NewspaperLayout>
      <div className="flex gap-8">
        {/* Navigation Sidebar */}
        <NavigationSidebar
          items={navigationItems}
          activeItem={activeView}
          onItemClick={handleNavigation}
        />
        
        {/* Main Content */}
        <div className="flex-1">
          {renderMainContent()}
        </div>
      </div>
    </NewspaperLayout>
  )
}

export default App