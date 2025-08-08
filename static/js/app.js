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
        
        // Initialize chat
        Chat.init();
        
        // Load initial view and data
        this.loadInitialView();
        
        console.log('Lifeboard Simple UI initialized successfully');
    },
    
    // Initialize navigation
    initNavigation() {
        const navButtons = document.querySelectorAll('.nav-button');
        
        navButtons.forEach(button => {
            button.addEventListener('click', async (e) => {
                const view = button.dataset.view;
                if (view) {
                    await this.switchView(view);
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
        
        // Note: Initial view loading is now handled by loadInitialView()
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
    async switchView(viewName) {
        console.log(`Switching to view: ${viewName}`);
        
        // Update navigation first
        const navButtons = document.querySelectorAll('.nav-button');
        navButtons.forEach(button => {
            button.classList.remove('active');
            if (button.dataset.view === viewName) {
                button.classList.add('active');
            }
        });
        
        // Update current view
        this.currentView = viewName;
        
        try {
            // Load the template for the view
            await TemplateLoader.loadTemplateIntoContainer(viewName);
            
            // After template is loaded, load view-specific data
            await this.loadViewData(viewName);
            
        } catch (error) {
            console.error(`Failed to switch to view ${viewName}:`, error);
            
            // Show error state in main content
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                mainContent.innerHTML = `
                    <div class="error-state">
                        <p class="text-muted" style="color: #dc2626;">❌ Failed to load ${viewName} view</p>
                        <p class="text-sm text-muted">${error.message}</p>
                    </div>
                `;
            }
        }
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
        
        // Re-initialize date picker functionality after template load
        this.initDatePicker();
        
        // Update the header with current date
        this.updateDayViewHeader();
        
        // Update navigation button visibility
        this.updateNavigationButtonVisibility();
        
        // Load weather data - COMMENTED OUT TO PRESERVE MOCK DATA
        // this.loadWeatherData();
        
        // Load news data
        this.loadNewsData();
        
        // Load activity data
        this.loadActivityData();
    },
    
    // Load weather data - COMMENTED OUT TO PRESERVE MOCK DATA
    /* async loadWeatherData() {
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
    }, */
    
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
            
            // Check if we have Limitless raw items data
            if (calendarData && calendarData.limitless && calendarData.limitless.has_data && calendarData.limitless.raw_items) {
                const rawItems = calendarData.limitless.raw_items;
                
                if (rawItems && rawItems.length > 0) {
                    // Process and render lifelogs like a markdown document
                    const lifelogsHtml = rawItems.map((item, index) => {
                        let metadata = {};
                        let sourceId = item.source_id || 'Unknown';
                        let lifelogTitle = 'Untitled Lifelog';
                        
                        // Parse metadata to get lifelog data
                        if (item.metadata) {
                            try {
                                metadata = typeof item.metadata === 'string' 
                                    ? JSON.parse(item.metadata) 
                                    : item.metadata;
                                
                                lifelogTitle = metadata.title || metadata.lifelog_title || lifelogTitle;
                            } catch (e) {
                                console.error('Error parsing metadata:', e);
                            }
                        }
                        
                        // Get the start and end times
                        const startTime = metadata.start_time ? new Date(metadata.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
                        const endTime = metadata.end_time ? new Date(metadata.end_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
                        
                        // Process markdown content to look like a markdown file
                        let markdownContent = metadata.cleaned_markdown || metadata.markdown || item.content || '';
                        
                        // Render as structured markdown document
                        const renderedContent = this.renderLifelogAsMarkdown(markdownContent);
                        
                        return `
                            <div class="lifelog-document mb-8 bg-white border border-gray-200 rounded-lg shadow-sm">
                                <div class="lifelog-header p-4 border-b border-gray-200 bg-gray-50">
                                    <div class="flex justify-between items-start">
                                        <div>
                                            <h3 class="lifelog-title text-lg font-semibold text-gray-900">${Utils.escapeHtml(lifelogTitle)}</h3>
                                            <p class="lifelog-meta text-sm text-gray-600 mt-1">
                                                ${startTime && endTime ? `${startTime} - ${endTime}` : ''}
                                                ${sourceId ? ` • ID: ${Utils.escapeHtml(sourceId)}` : ''}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                                <div class="lifelog-content p-6">
                                    <div class="markdown-document">
                                        ${renderedContent}
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('');
                    
                    activityContent.innerHTML = `
                        <div class="lifelogs-container">
                            <p class="text-sm text-gray-600 mb-6">Showing ${rawItems.length} lifelog${rawItems.length === 1 ? '' : 's'}:</p>
                            ${lifelogsHtml}
                        </div>
                    `;
                } else {
                    Utils.showEmpty('activity-content', 'No lifelogs available for this date');
                }
            } else {
                Utils.showEmpty('activity-content', 'No activities recorded for this date');
            }
        } catch (error) {
            console.error('Failed to load activity data:', error);
            Utils.showError('activity-content', 'Failed to load activity data');
        }
    },
    
    // Render lifelog content as markdown using Marked.js with custom speaker pattern handling
    renderLifelogAsMarkdown(content) {
        if (!content) return '<p class="text-gray-500 italic">No content available</p>';
        
        // First, handle speaker patterns before passing to marked
        // Speaker patterns: "Speaker Name [time]: content"
        const lines = content.split('\n');
        const processedLines = lines.map(line => {
            const trimmedLine = line.trim();
            
            // Check for speaker patterns (Speaker Name [time]: content)
            const speakerMatch = trimmedLine.match(/^([^[]+)\s*\[([^\]]+)\]:\s*(.+)$/);
            if (speakerMatch) {
                const speaker = speakerMatch[1].trim();
                const time = speakerMatch[2].trim();
                const words = speakerMatch[3].trim();
                
                // Convert to custom HTML that won't be processed by marked
                return `<div class="speaker-line mb-3 pl-4 border-l-2 border-blue-300">
                    <div class="speaker-info mb-1">
                        <span class="speaker-name font-medium text-blue-700">${Utils.escapeHtml(speaker)}</span>
                        <span class="speaker-time text-xs text-gray-500 ml-2">[${Utils.escapeHtml(time)}]</span>
                    </div>
                    <div class="speaker-content text-gray-800">${Utils.escapeHtml(words)}</div>
                </div>`;
            }
            
            return line;
        });
        
        // Rejoin and render with marked
        const processedContent = processedLines.join('\n');
        
        try {
            // Use Marked.js to render markdown
            const html = marked.parse(processedContent, {
                breaks: true,  // Convert single line breaks to <br>
                gfm: true      // Enable GitHub Flavored Markdown
            });
            
            return html;
        } catch (error) {
            console.error('Error rendering markdown with Marked.js:', error);
            // Fallback to simple text display if marked fails
            return `<pre class="whitespace-pre-wrap text-gray-800">${Utils.escapeHtml(content)}</pre>`;
        }
    },
    
    // Load calendar view data
    async loadCalendarViewData() {
        console.log('Loading calendar view data');
        
        // Re-initialize calendar navigation after template load
        this.initCalendarView();
        
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
        
        // Re-initialize settings functionality after template load
        this.initSettingsView();
        
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
        
        // Update navigation button visibility
        this.updateNavigationButtonVisibility();
        
        // Update day view header with formatted date
        this.updateDayViewHeader();
        
        // Reload day view data if currently viewing
        if (this.currentView === 'day') {
            this.loadDayViewData();
        }
        
        console.log(`Current date set to: ${dateString}`);
    },

    // Update navigation button visibility
    updateNavigationButtonVisibility() {
        const prevButton = document.getElementById('prev-date');
        const nextButton = document.getElementById('next-date');
        
        if (prevButton && nextButton) {
            const today = Utils.getTodayYYYYMMDD();
            
            // Always show both buttons by default
            prevButton.style.display = '';
            nextButton.style.display = '';
            
            // Hide next button only when current date is today
            if (this.currentDate === today) {
                nextButton.style.display = 'none';
            }
        }
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
    
    // Load initial view and data
    async loadInitialView() {
        console.log('Loading initial view...');
        
        try {
            // Load the initial view template
            await this.switchView(this.currentView);
        } catch (error) {
            console.error('Failed to load initial view:', error);
        }
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