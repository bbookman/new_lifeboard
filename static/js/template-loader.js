/**
 * Template Loader - Dynamic HTML template loading system
 * Loads view templates from /static/templates/ directory
 */

const TemplateLoader = {
    // Cache for loaded templates
    templateCache: {},
    
    // Base path for templates
    basePath: '/static/templates/',
    
    // Template configurations
    templates: {
        'day': {
            file: 'day-view.html',
            containerId: 'main-content'
        },
        'calendar': {
            file: 'calendar-view.html',
            containerId: 'main-content'
        },
        'chat': {
            file: 'chat-view.html',
            containerId: 'main-content'
        },
        'settings': {
            file: 'settings-view.html',
            containerId: 'main-content'
        }
    },
    
    /**
     * Load a template by name
     * @param {string} templateName - Name of the template to load
     * @param {boolean} useCache - Whether to use cached version (default: true)
     * @returns {Promise<string>} - Template HTML content
     */
    async loadTemplate(templateName, useCache = true) {
        // Check cache first
        if (useCache && this.templateCache[templateName]) {
            console.log(`Using cached template: ${templateName}`);
            return this.templateCache[templateName];
        }
        
        const templateConfig = this.templates[templateName];
        if (!templateConfig) {
            throw new Error(`Template not found: ${templateName}`);
        }
        
        const templatePath = this.basePath + templateConfig.file;
        
        try {
            console.log(`Loading template: ${templateName} from ${templatePath}`);
            const response = await fetch(templatePath);
            
            if (!response.ok) {
                throw new Error(`Failed to load template: ${response.status} ${response.statusText}`);
            }
            
            const templateContent = await response.text();
            
            // Cache the template
            this.templateCache[templateName] = templateContent;
            
            return templateContent;
        } catch (error) {
            console.error(`Error loading template ${templateName}:`, error);
            throw error;
        }
    },
    
    /**
     * Load and inject a template into a container
     * @param {string} templateName - Name of the template to load
     * @param {string} containerId - ID of the container element (optional, uses template config)
     * @returns {Promise<HTMLElement>} - The container element
     */
    async loadTemplateIntoContainer(templateName, containerId = null) {
        const templateConfig = this.templates[templateName];
        const targetContainerId = containerId || templateConfig.containerId;
        const container = document.getElementById(targetContainerId);
        
        if (!container) {
            throw new Error(`Container not found: ${targetContainerId}`);
        }
        
        try {
            // Show loading state
            const originalContent = container.innerHTML;
            container.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p class="text-muted">Loading ${templateName} view...</p>
                </div>
            `;
            
            const templateContent = await this.loadTemplate(templateName);
            
            // Replace container content with template
            container.innerHTML = templateContent;
            
            console.log(`Template ${templateName} loaded into ${targetContainerId}`);
            return container;
            
        } catch (error) {
            console.error(`Error loading template ${templateName} into container:`, error);
            // Restore original content on error
            container.innerHTML = `
                <div class="error-state">
                    <p class="text-muted" style="color: #dc2626;">❌ Failed to load ${templateName} view</p>
                    <p class="text-sm text-muted">${error.message}</p>
                </div>
            `;
            throw error;
        }
    },
    
    /**
     * Preload all templates for better performance
     * @returns {Promise<void>}
     */
    async preloadAllTemplates() {
        console.log('Preloading all templates...');
        const loadPromises = Object.keys(this.templates).map(templateName => 
            this.loadTemplate(templateName).catch(error => {
                console.warn(`Failed to preload template ${templateName}:`, error);
                return null;
            })
        );
        
        await Promise.all(loadPromises);
        console.log('Template preloading completed');
    },
    
    /**
     * Clear template cache
     */
    clearCache() {
        this.templateCache = {};
        console.log('Template cache cleared');
    },
    
    /**
     * Get cached template names
     * @returns {string[]} - Array of cached template names
     */
    getCachedTemplates() {
        return Object.keys(this.templateCache);
    },
    
    /**
     * Check if a template is cached
     * @param {string} templateName - Name of the template
     * @returns {boolean} - Whether the template is cached
     */
    isTemplateCached(templateName) {
        return templateName in this.templateCache;
    }
};

// Export for use in other modules
window.TemplateLoader = TemplateLoader;