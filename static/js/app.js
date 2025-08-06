/**
 * Main application logic for Lifeboard simple UI
 */

const App = {
    // Current state
    currentView: 'day',
    currentDate: null,
    
    // Initialize the application
    init() {
        console.log('Initializing Lifeboard Simple UI...');
        
        // Set current date to today
        this.currentDate = Utils.getTodayYYYYMMDD();
        
        // Initialize components
        this.initNavigation();
        this.initDatePicker();
        this.initViews();
        
        // Update day view header with initial date
        this.updateDayViewHeader();
        
        // Initialize chat
        Chat.init();
        
        // Load initial data
        this.loadInitialData();
        
        console.log('Lifeboard Simple UI initialized successfully');
    },
    
    // Initialize navigation
    initNavigation() {
        const navButtons = document.querySelectorAll('.nav-button');
        
        navButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const view = button.dataset.view;
                if (view) {
                    this.switchView(view);
                }
            });
        });
    },
    
    // Initialize date picker
    initDatePicker() {
        const datePicker = document.getElementById('date-picker');
        const prevButton = document.getElementById('prev-date');
        const nextButton = document.getElementById('next-date');
        
        if (datePicker) {
            // Set initial date
            datePicker.value = this.currentDate;
            
            // Date picker change event
            datePicker.addEventListener('change', (e) => {
                this.setCurrentDate(e.target.value);
            });
        }
        
        if (prevButton) {
            prevButton.addEventListener('click', () => {
                this.navigateDate(-1);
            });
        }
        
        if (nextButton) {
            nextButton.addEventListener('click', () => {
                this.navigateDate(1);
            });
        }
    },
    
    // Initialize all views
    initViews() {
        this.initDayView();
        this.initCalendarView();
        this.initSettingsView();
        
        // Show initial view
        this.switchView(this.currentView);
    },
    
    // Initialize day view
    initDayView() {
        // Day view is initialized by loading data when switching to it
        console.log('Day view initialized');
    },
    
    // Initialize calendar view
    initCalendarView() {
        const prevMonthButton = document.getElementById('prev-month');
        const nextMonthButton = document.getElementById('next-month');
        
        if (prevMonthButton) {
            prevMonthButton.addEventListener('click', () => {
                this.navigateMonth(-1);
            });
        }
        
        if (nextMonthButton) {
            nextMonthButton.addEventListener('click', () => {
                this.navigateMonth(1);
            });
        }
        
        console.log('Calendar view initialized');
    },
    
    // Initialize settings view
    initSettingsView() {
        const syncButton = document.getElementById('sync-data');
        const clearCacheButton = document.getElementById('clear-cache');
        
        if (syncButton) {
            syncButton.addEventListener('click', () => {
                this.syncData();
            });
        }
        
        if (clearCacheButton) {
            clearCacheButton.addEventListener('click', () => {
                this.clearCache();
            });
        }
        
        console.log('Settings view initialized');
    },
    
    // Switch between views
    switchView(viewName) {
        console.log(`Switching to view: ${viewName}`);
        
        // Hide all views
        const views = document.querySelectorAll('.view-container');
        views.forEach(view => {
            view.style.display = 'none';
        });
        
        // Show selected view
        const targetView = document.getElementById(`${viewName}-view`);
        if (targetView) {
            targetView.style.display = 'block';
        }
        
        // Update navigation
        const navButtons = document.querySelectorAll('.nav-button');
        navButtons.forEach(button => {
            button.classList.remove('active');
            if (button.dataset.view === viewName) {
                button.classList.add('active');
            }
        });
        
        // Update current view
        this.currentView = viewName;
        
        // Load view-specific data
        this.loadViewData(viewName);
    },
    
    // Load data for specific view
    async loadViewData(viewName) {
        try {
            switch (viewName) {
                case 'day':
                    await this.loadDayViewData();
                    break;
                case 'calendar':
                    await this.loadCalendarViewData();
                    break;
                case 'settings':
                    await this.loadSettingsViewData();
                    break;
                case 'chat':
                    // Chat data is loaded by Chat module
                    break;
            }
        } catch (error) {
            console.error(`Failed to load data for ${viewName} view:`, error);
        }
    },
    
    // Load day view data
    async loadDayViewData() {
        console.log(`Loading day view data for ${this.currentDate}`);
        
        // Update the header with current date
        this.updateDayViewHeader();
        
        // Load weather data
        this.loadWeatherData();
        
        // Load news data
        this.loadNewsData();
        
        // Load activity data
        this.loadActivityData();
    },
    
    // Load weather data
    async loadWeatherData() {
        const weatherContent = document.getElementById('weather-content');
        if (!weatherContent) return;
        
        Utils.showLoading('weather-content', 'Loading weather...');
        
        try {
            const weatherData = await API.weather.getDateWeather(this.currentDate);
            
            if (weatherData && weatherData.forecast_days && weatherData.forecast_days.length > 0) {
                const forecast = weatherData.forecast_days[0];
                
                weatherContent.innerHTML = `
                    <div class="weather-summary">
                        <div class="weather-main">
                            <div class="weather-temp">
                                <span class="temp-high">${forecast.max_temp || 'N/A'}°</span>
                                <span class="temp-low">${forecast.min_temp || 'N/A'}°</span>
                            </div>
                            <div class="weather-desc">
                                <p><strong>${forecast.summary || 'No summary available'}</strong></p>
                                <p class="text-sm text-muted">
                                    Humidity: ${forecast.humidity || 'N/A'}% • 
                                    Wind: ${forecast.wind_speed || 'N/A'} mph
                                </p>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                Utils.showEmpty('weather-content', 'No weather data available for this date');
            }
        } catch (error) {
            console.error('Failed to load weather data:', error);
            Utils.showError('weather-content', 'Failed to load weather data');
        }
    },
    
    // Load news data
    async loadNewsData() {
        const newsContent = document.getElementById('news-content');
        if (!newsContent) return;
        
        Utils.showLoading('news-content', 'Loading news...');
        
        try {
            const calendarData = await API.calendar.getDateData(this.currentDate);
            
            if (calendarData && calendarData.news && calendarData.news.articles && calendarData.news.articles.length > 0) {
                const articles = calendarData.news.articles.slice(0, 5); // Show first 5 articles
                
                const articlesHtml = articles.map(article => `
                    <div class="news-article mb-4">
                        <h4 class="news-title text-sm font-bold">
                            ${article.link ? 
                                `<a href="${article.link}" target="_blank" rel="noopener">${Utils.escapeHtml(article.title)}</a>` : 
                                Utils.escapeHtml(article.title)
                            }
                        </h4>
                        ${article.snippet ? 
                            `<p class="news-snippet text-sm text-muted mt-1">${Utils.escapeHtml(Utils.truncateText(article.snippet, 120))}</p>` : 
                            ''
                        }
                    </div>
                `).join('');
                
                newsContent.innerHTML = articlesHtml;
            } else {
                Utils.showEmpty('news-content', 'No news available for this date');
            }
        } catch (error) {
            console.error('Failed to load news data:', error);
            Utils.showError('news-content', 'Failed to load news data');
        }
    },
    
    // Load activity data
    async loadActivityData() {
        const activityContent = document.getElementById('activity-content');
        if (!activityContent) return;
        
        Utils.showLoading('activity-content', 'Loading activities...');
        
        try {
            const calendarData = await API.calendar.getDateData(this.currentDate);
            
            // Check if we have Limitless data with markdown content
            if (calendarData && calendarData.limitless && calendarData.limitless.has_data) {
                const markdown = calendarData.limitless.markdown_content;
                if (markdown && markdown.length > 0) {
                    // Display markdown content as formatted text
                    const formattedContent = markdown
                        .replace(/^# (.+)/gm, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
                        .replace(/^## (.+)/gm, '<h4 class="text-md font-medium mt-3 mb-1">$1</h4>')
                        .replace(/^### (.+)/gm, '<h5 class="text-sm font-medium mt-2 mb-1">$1</h5>')
                        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                        .replace(/\*(.+?)\*/g, '<em>$1</em>')
                        .replace(/\n\n/g, '</p><p>')
                        .replace(/\n/g, '<br>');
                    
                    activityContent.innerHTML = `
                        <div class="activity-markdown p-3">
                            <p>${formattedContent}</p>
                        </div>
                    `;
                } else {
                    Utils.showEmpty('activity-content', 'No activity content available for this date');
                }
            } else {
                Utils.showEmpty('activity-content', 'No activities recorded for this date');
            }
        } catch (error) {
            console.error('Failed to load activity data:', error);
            Utils.showError('activity-content', 'Failed to load activity data');
        }
    },
    
    // Load calendar view data
    async loadCalendarViewData() {
        console.log('Loading calendar view data');
        
        const currentDate = new Date(this.currentDate);
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        
        this.renderCalendar(year, month);
    },
    
    // Render calendar
    async renderCalendar(year, month) {
        const currentMonthHeader = document.getElementById('current-month');
        const calendarGrid = document.getElementById('calendar-grid');
        const calendarHeader = document.getElementById('calendar-header');
        
        if (!currentMonthHeader || !calendarGrid || !calendarHeader) return;
        
        // Update month header
        const monthDate = new Date(year, month, 1);
        currentMonthHeader.textContent = Utils.formatMonthYear(monthDate);
        
        // Render day headers
        const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        calendarHeader.innerHTML = dayHeaders.map(day => 
            `<div class="calendar-day-header">${day}</div>`
        ).join('');
        
        // Get days with data for this month
        let daysWithData = [];
        try {
            const dataResponse = await API.calendar.getDaysWithData(year, month);
            daysWithData = dataResponse.all || [];
            console.log(`Calendar: Found ${daysWithData.length} days with data for ${year}-${month}`);
        } catch (error) {
            console.error('Failed to load calendar data:', error);
        }
        
        // Calculate calendar days
        const firstDay = Utils.getFirstDayOfMonth(year, month);
        const lastDay = Utils.getLastDayOfMonth(year, month);
        const startDate = new Date(firstDay);
        startDate.setDate(startDate.getDate() - firstDay.getDay());
        
        const days = [];
        const currentDate = new Date(startDate);
        
        // Generate 42 days (6 weeks)
        for (let i = 0; i < 42; i++) {
            const dateString = Utils.formatDateYYYYMMDD(currentDate);
            const dayData = {
                date: new Date(currentDate),
                dateString: dateString,
                dayNumber: currentDate.getDate(),
                isCurrentMonth: currentDate.getMonth() === month,
                isToday: dateString === Utils.getTodayYYYYMMDD(),
                hasEvents: daysWithData.includes(dateString)
            };
            
            days.push(dayData);
            currentDate.setDate(currentDate.getDate() + 1);
        }
        
        // Render calendar days
        const daysHtml = days.map(day => {
            const classes = [
                'calendar-day',
                day.isCurrentMonth ? 'current-month' : 'other-month',
                day.isToday ? 'today' : '',
                day.hasEvents ? 'has-events' : ''
            ].filter(Boolean).join(' ');
            
            return `
                <div class="${classes}" data-date="${day.dateString}">
                    <div class="calendar-day-number">${day.dayNumber}</div>
                    ${day.hasEvents ? '<div class="calendar-events"><div class="event-dot"></div></div>' : ''}
                </div>
            `;
        }).join('');
        
        calendarGrid.innerHTML = daysHtml;
        
        // Add click handlers
        calendarGrid.querySelectorAll('.calendar-day').forEach(dayElement => {
            dayElement.addEventListener('click', (e) => {
                const date = e.currentTarget.dataset.date;
                if (date) {
                    this.setCurrentDate(date);
                    this.switchView('day');
                }
            });
        });
    },
    
    // Load settings view data
    async loadSettingsViewData() {
        console.log('Loading settings view data');
        
        // Load system information
        try {
            const systemInfo = await API.settings.getSystemInfo();
            const systemInfoContainer = document.getElementById('system-info');
            
            if (systemInfoContainer && systemInfo) {
                systemInfoContainer.innerHTML = `
                    <div class="info-item">
                        <span class="info-label">Version</span>
                        <span class="info-value">${systemInfo.version || '1.0.0'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Interface</span>
                        <span class="info-value">Simple HTML</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Status</span>
                        <span class="info-value">${systemInfo.status || 'Running'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Uptime</span>
                        <span class="info-value">${systemInfo.uptime || 'N/A'}</span>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load system info:', error);
        }
        
        // Load data sources information
        try {
            const syncStatus = await API.sync.getStatus();
            const dataSourcesContainer = document.getElementById('data-sources-info');
            
            if (dataSourcesContainer && syncStatus && syncStatus.sources) {
                const sourcesHtml = Object.entries(syncStatus.sources).map(([name, data]) => `
                    <div class="info-item">
                        <span class="info-label">${name}</span>
                        <span class="info-value ${data.is_active ? 'text-green-600' : 'text-red-600'}">
                            ${data.is_active ? 'Active' : 'Inactive'} (${data.item_count || 0} items)
                        </span>
                    </div>
                `).join('');
                
                dataSourcesContainer.innerHTML = sourcesHtml;
            }
        } catch (error) {
            console.error('Failed to load data sources info:', error);
            Utils.showError('data-sources-info', 'Failed to load data sources');
        }
    },
    
    // Navigate date by days
    navigateDate(days) {
        const currentDate = new Date(this.currentDate);
        currentDate.setDate(currentDate.getDate() + days);
        this.setCurrentDate(Utils.formatDateYYYYMMDD(currentDate));
    },
    
    // Navigate month for calendar
    navigateMonth(months) {
        const currentDate = new Date(this.currentDate);
        currentDate.setMonth(currentDate.getMonth() + months);
        this.setCurrentDate(Utils.formatDateYYYYMMDD(currentDate));
        
        if (this.currentView === 'calendar') {
            this.loadCalendarViewData();
        }
    },
    
    // Set current date
    setCurrentDate(dateString) {
        this.currentDate = dateString;
        
        // Update date picker
        const datePicker = document.getElementById('date-picker');
        if (datePicker) {
            datePicker.value = dateString;
        }
        
        // Update day view header with formatted date
        this.updateDayViewHeader();
        
        // Reload day view data if currently viewing
        if (this.currentView === 'day') {
            this.loadDayViewData();
        }
        
        console.log(`Current date set to: ${dateString}`);
    },

    // Update day view header with current date
    updateDayViewHeader() {
        const header = document.getElementById('day-view-header');
        if (header && this.currentDate) {
            const date = new Date(this.currentDate + 'T00:00:00');
            
            // Always show day of week and full date for all dates
            const dayOfWeek = date.toLocaleDateString('en-US', { weekday: 'long' });
            const formattedDate = Utils.formatDateDisplay(date);
            header.textContent = `${dayOfWeek}, ${formattedDate}`;
        }
    },
    
    // Load initial data
    async loadInitialData() {
        console.log('Loading initial data...');
        
        // Load data for current view
        await this.loadViewData(this.currentView);
    },
    
    // Sync data sources
    async syncData() {
        const syncButton = document.getElementById('sync-data');
        if (!syncButton) return;
        
        const originalText = syncButton.textContent;
        syncButton.textContent = 'Syncing...';
        syncButton.disabled = true;
        
        try {
            await API.sync.triggerSync();
            alert('Data sync completed successfully!');
            
            // Reload current view data
            await this.loadViewData(this.currentView);
            
        } catch (error) {
            console.error('Failed to sync data:', error);
            alert(`Failed to sync data: ${error.message}`);
        } finally {
            syncButton.textContent = originalText;
            syncButton.disabled = false;
        }
    },
    
    // Clear cache
    clearCache() {
        if (confirm('Are you sure you want to clear the local cache?')) {
            // Clear localStorage
            try {
                localStorage.clear();
                alert('Cache cleared successfully!');
            } catch (error) {
                console.error('Failed to clear cache:', error);
                alert('Failed to clear cache.');
            }
        }
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});