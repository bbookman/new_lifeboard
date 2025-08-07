/**
 * Utility functions for the Lifeboard simple UI
 */

// Date utilities
const Utils = {
    // Format date as YYYY-MM-DD
    formatDateYYYYMMDD(date) {
        if (typeof date === 'string') {
            date = new Date(date);
        }
        return date.toISOString().split('T')[0];
    },

    // Get today's date as YYYY-MM-DD
    getTodayYYYYMMDD() {
        return this.formatDateYYYYMMDD(new Date());
    },

    // Parse YYYY-MM-DD string to Date
    parseDate(dateString) {
        return new Date(dateString + 'T00:00:00');
    },

    // Format date for display (e.g., "January 15, 2024")
    formatDateDisplay(date) {
        if (typeof date === 'string') {
            date = new Date(date);
        }
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    },

    // Format date for calendar header (e.g., "January 2024")
    formatMonthYear(date) {
        if (typeof date === 'string') {
            date = new Date(date);
        }
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long'
        });
    },

    // Get first day of month
    getFirstDayOfMonth(year, month) {
        return new Date(year, month, 1);
    },

    // Get last day of month
    getLastDayOfMonth(year, month) {
        return new Date(year, month + 1, 0);
    },

    // Get day of week (0 = Sunday, 6 = Saturday)
    getDayOfWeek(date) {
        if (typeof date === 'string') {
            date = new Date(date);
        }
        return date.getDay();
    },

    // Format timestamp for chat messages
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMinutes = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMinutes < 1) {
            return 'just now';
        } else if (diffMinutes < 60) {
            return `${diffMinutes}m ago`;
        } else if (diffHours < 24) {
            return `${diffHours}h ago`;
        } else if (diffDays < 7) {
            return `${diffDays}d ago`;
        } else {
            return date.toLocaleDateString();
        }
    },

    // Generate unique ID
    generateId() {
        return 'id-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    },

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // Debounce function calls
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Show loading state
    showLoading(containerId, message = 'Loading...') {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p class="text-muted">${message}</p>
                </div>
            `;
        }
    },

    // Show error state
    showError(containerId, message = 'An error occurred') {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="error-state">
                    <p class="text-muted" style="color: #dc2626;">❌ ${message}</p>
                </div>
            `;
        }
    },

    // Show empty state
    showEmpty(containerId, message = 'No data available') {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <p class="text-muted">${message}</p>
                </div>
            `;
        }
    },


    // Truncate text with ellipsis
    truncateText(text, maxLength = 100) {
        if (!text || text.length <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + '...';
    },

    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Check if device is mobile
    isMobile() {
        return window.innerWidth < 768;
    },

    // Check if device supports touch
    isTouchDevice() {
        return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    },

    // Smooth scroll to element
    scrollToElement(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'start' 
            });
        }
    },

    // Local storage helpers
    storage: {
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
            } catch (e) {
                console.warn('Failed to save to localStorage:', e);
            }
        },

        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (e) {
                console.warn('Failed to read from localStorage:', e);
                return defaultValue;
            }
        },

        remove(key) {
            try {
                localStorage.removeItem(key);
            } catch (e) {
                console.warn('Failed to remove from localStorage:', e);
            }
        }
    }
};

// Export for use in other modules
window.Utils = Utils;