/**
 * API module for communicating with the Lifeboard backend
 */

const API = {
    baseURL: window.location.origin,
    
    // Default request configuration
    defaultOptions: {
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    },

    // Generic request method
    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;
        
        const config = {
            ...this.defaultOptions,
            ...options,
            headers: {
                ...this.defaultOptions.headers,
                ...options.headers
            }
        };

        try {
            console.log(`API Request: ${config.method || 'GET'} ${url}`);
            const response = await fetch(url, config);
            
            // Check if response is ok
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`API Response:`, data);
            return data;
            
        } catch (error) {
            console.error(`API Error: ${url}`, error);
            throw error;
        }
    },

    // GET request
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    // POST request
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // PUT request
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    // DELETE request
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    // Health check
    async healthCheck() {
        return this.get('/health');
    },

    // Chat API methods
    chat: {
        // Send a chat message
        async send(message) {
            return API.post('/api/chat/send', { message });
        },

        // Get chat history
        async getHistory() {
            return API.get('/api/chat/history');
        },

        // Clear chat history
        async clearHistory() {
            return API.delete('/api/chat/history');
        }
    },

    // Calendar API methods
    calendar: {
        // Get calendar data for a specific date
        async getDateData(date) {
            const formattedDate = typeof date === 'string' ? date : Utils.formatDateYYYYMMDD(date);
            return API.get(`/calendar/api/day/${formattedDate}/enhanced`);
        },

        // Get calendar data for a month
        async getMonthData(year, month) {
            return API.get(`/calendar/api/month/${year}/${month}`);
        },

        // Get days with data for calendar
        async getDaysWithData(year, month) {
            return API.get(`/calendar/api/days-with-data?year=${year}&month=${month}`);
        }
    },

    // Weather API methods
    weather: {
        // Get weather data for a specific date
        async getDateWeather(date) {
            const formattedDate = typeof date === 'string' ? date : Utils.formatDateYYYYMMDD(date);
            return API.get(`/weather/day/${formattedDate}`);
        }
    },

    // Sync API methods
    sync: {
        // Get sync status
        async getStatus() {
            return API.get('/api/sync/status');
        },

        // Trigger manual sync
        async triggerSync(source = null) {
            const endpoint = source ? `/api/sync/${source}` : '/api/sync/all';
            return API.post(endpoint);
        }
    },

    // Settings API methods
    settings: {
        // Get all settings
        async getAll() {
            return API.get('/api/settings');
        },

        // Update settings
        async update(settings) {
            return API.put('/api/settings', settings);
        },

        // Get system information
        async getSystemInfo() {
            return API.get('/api/system/info');
        }
    },

    // Embedding API methods
    embeddings: {
        // Get embedding status
        async getStatus() {
            return API.get('/api/embeddings/status');
        },

        // Trigger embedding processing
        async process() {
            return API.post('/api/embeddings/process');
        }
    }
};

// Add error handling wrapper
const originalRequest = API.request;
API.request = async function(endpoint, options = {}) {
    try {
        return await originalRequest.call(this, endpoint, options);
    } catch (error) {
        // Check if it's a network error
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            throw new Error('Network error: Please check your connection and try again.');
        }
        
        // Check if it's a server error
        if (error.message.includes('HTTP 5')) {
            throw new Error('Server error: The service is temporarily unavailable.');
        }
        
        // Check if it's an authentication error
        if (error.message.includes('HTTP 401') || error.message.includes('HTTP 403')) {
            throw new Error('Authentication error: Please refresh the page and try again.');
        }
        
        // For other errors, use the original message
        throw error;
    }
};

// Export for use in other modules
window.API = API;