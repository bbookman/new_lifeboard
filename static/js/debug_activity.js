// Temporary debug version - replace loadActivityData in app.js
async loadActivityData() {
    const activityContent = document.getElementById('activity-content');
    if (!activityContent) {
        console.error('DEBUG: activity-content element not found');
        return;
    }
    
    console.log('DEBUG: Loading activity data for date:', this.currentDate);
    Utils.showLoading('activity-content', 'Loading activities...');
    
    try {
        console.log('DEBUG: Making API call to calendar endpoint...');
        const calendarData = await API.calendar.getDateData(this.currentDate);
        console.log('DEBUG: Received calendar data:', calendarData);
        
        // Check if we have limitless data
        if (!calendarData) {
            console.error('DEBUG: No calendar data received');
            Utils.showEmpty('activity-content', 'No calendar data available');
            return;
        }
        
        if (!calendarData.limitless) {
            console.error('DEBUG: No limitless property in calendar data');
            console.log('DEBUG: Available properties:', Object.keys(calendarData));
            Utils.showEmpty('activity-content', 'No limitless data property');
            return;
        }
        
        console.log('DEBUG: Limitless data:', calendarData.limitless);
        
        if (!calendarData.limitless.has_data) {
            console.log('DEBUG: limitless.has_data is false');
            Utils.showEmpty('activity-content', 'No limitless data available');
            return;
        }
        
        if (!calendarData.limitless.raw_items) {
            console.error('DEBUG: No raw_items in limitless data');
            console.log('DEBUG: Available limitless properties:', Object.keys(calendarData.limitless));
            Utils.showEmpty('activity-content', 'No raw items available');
            return;
        }
        
        const rawItems = calendarData.limitless.raw_items;
        console.log('DEBUG: Raw items count:', rawItems.length);
        console.log('DEBUG: First raw item:', rawItems[0]);
        
        if (rawItems && rawItems.length > 0) {
            console.log('DEBUG: Processing raw items...');
            
            // Test if marked.parse is available
            if (typeof marked === 'undefined') {
                console.error('DEBUG: marked.parse is not available! Marked.js library not loaded.');
                Utils.showError('activity-content', 'Markdown library not loaded');
                return;
            }
            console.log('DEBUG: Marked.js is available');
            
            // Process and render lifelogs
            const lifelogsHtml = rawItems.map((item, index) => {
                console.log(`DEBUG: Processing item ${index + 1}:`, item);
                
                let metadata = {};
                let sourceId = item.source_id || 'Unknown';
                let lifelogTitle = 'Untitled Lifelog';
                
                // Parse metadata
                if (item.metadata) {
                    try {
                        metadata = typeof item.metadata === 'string' 
                            ? JSON.parse(item.metadata) 
                            : item.metadata;
                        
                        lifelogTitle = metadata.title || metadata.lifelog_title || lifelogTitle;
                        console.log(`DEBUG: Item ${index + 1} metadata:`, metadata);
                    } catch (e) {
                        console.error(`DEBUG: Error parsing metadata for item ${index + 1}:`, e);
                    }
                }
                
                // Get markdown content
                let markdownContent = metadata.cleaned_markdown || metadata.markdown || item.content || '';
                console.log(`DEBUG: Item ${index + 1} markdown content length:`, markdownContent.length);
                console.log(`DEBUG: Item ${index + 1} markdown preview:`, markdownContent.substring(0, 200));
                
                // Test markdown rendering
                let renderedContent = '';
                try {
                    renderedContent = this.renderLifelogAsMarkdown(markdownContent);
                    console.log(`DEBUG: Item ${index + 1} rendered successfully`);
                } catch (e) {
                    console.error(`DEBUG: Error rendering item ${index + 1}:`, e);
                    renderedContent = `<p>Error rendering content: ${e.message}</p>`;
                }
                
                return `
                    <div class="lifelog-document mb-8 bg-white border border-gray-200 rounded-lg shadow-sm">
                        <div class="lifelog-header p-4 border-b border-gray-200 bg-gray-50">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h3 class="lifelog-title text-lg font-semibold text-gray-900">${Utils.escapeHtml(lifelogTitle)}</h3>
                                    <p class="lifelog-meta text-sm text-gray-600 mt-1">
                                        ${sourceId ? `ID: ${Utils.escapeHtml(sourceId)}` : ''}
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
            
            console.log('DEBUG: Generated HTML length:', lifelogsHtml.length);
            
            activityContent.innerHTML = `
                <div class="lifelogs-container">
                    <p class="text-sm text-gray-600 mb-6">Showing ${rawItems.length} lifelog${rawItems.length === 1 ? '' : 's'}:</p>
                    ${lifelogsHtml}
                </div>
            `;
            console.log('DEBUG: Activity content updated successfully');
            
        } else {
            console.log('DEBUG: No raw items found');
            Utils.showEmpty('activity-content', 'No lifelogs available for this date');
        }
        
    } catch (error) {
        console.error('DEBUG: Failed to load activity data:', error);
        console.error('DEBUG: Full error stack:', error.stack);
        Utils.showError('activity-content', `Failed to load activity data: ${error.message}`);
    }
}