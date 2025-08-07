# UI Debugging Guide: Activity Summary Card Empty

**Issue**: Activity Summary card shows no content despite expected data availability  
**Last Modified**: January 7, 2025  
**Context**: Recent implementation of Marked.js for markdown rendering

---

## 🎯 Quick Diagnostic Questions

Before diving into detailed debugging, answer these:

1. **What date is currently selected?** (Check the day view header)
2. **Any red errors in browser console?** 
3. **Does `typeof marked` return `"function"` in console?**
4. **Is the loading spinner appearing and disappearing?**
5. **What message appears in Activity Summary card?**

---

## 🔍 Phase 1: Browser Console & Network Inspection

### Step 1.1: Check JavaScript Errors
1. **Open Developer Tools** (F12 or right-click → Inspect)
2. **Go to Console tab**
3. **Refresh the page** 
4. **Look for any red error messages**

**Common errors to watch for:**
- `marked is not defined`
- `Cannot read property 'raw_items' of undefined`
- `Failed to fetch` network errors
- Any parsing or rendering errors

### Step 1.2: Verify Marked.js Library
**In browser console, type:**
```javascript
typeof marked
```
**Expected result:** `"function"`  
**If "undefined":** Marked.js CDN failed to load

### Step 1.3: Network Tab Inspection
1. **Go to Network tab** in dev tools
2. **Refresh the page**
3. **Look for these requests:**
   - `marked.umd.js` (should be 200 OK)
   - `calendar/api/day/[DATE]/enhanced` (should be 200 OK)
4. **Click on the calendar API request** and check **Response tab**

---

## 🌐 Phase 2: API Endpoint Verification

### Step 2.1: Manual API Test
**Open this URL in new browser tab:**
```
http://localhost:8000/calendar/api/day/2025-01-07/enhanced
```
*(Replace date with your current selected date)*

**Expected response structure:**
```json
{
  "date": "2025-01-07",
  "limitless": {
    "has_data": true,
    "raw_items": [
      {
        "id": "limitless:some-id",
        "source_id": "some-id", 
        "metadata": "{ ... }",
        "content": "..."
      }
    ],
    "item_count": 1
  }
}
```

### Step 2.2: Check Current Date Format
**In browser console:**
```javascript
// Check what date the app is using
console.log('Current date:', App.currentDate);

// Check date format
console.log('Today formatted:', Utils.getTodayYYYYMMDD());
```

---

## 📊 Phase 3: Enhanced Debug Logging

### Step 3.1: Replace loadActivityData with Debug Version

**Temporarily edit `/static/js/app.js`** - replace the `loadActivityData` function with this enhanced debug version:

```javascript
// TEMPORARY DEBUG VERSION - Enhanced logging
async loadActivityData() {
    const activityContent = document.getElementById('activity-content');
    if (!activityContent) {
        console.error('🚨 DEBUG: activity-content element not found');
        return;
    }
    
    console.log('🔍 DEBUG: Starting activity data load for date:', this.currentDate);
    Utils.showLoading('activity-content', 'Loading activities...');
    
    try {
        console.log('📡 DEBUG: Making API call...');
        const calendarData = await API.calendar.getDateData(this.currentDate);
        console.log('📦 DEBUG: Raw API response:', calendarData);
        
        // Step-by-step data structure verification
        if (!calendarData) {
            console.error('❌ DEBUG: No calendar data received');
            Utils.showEmpty('activity-content', 'DEBUG: No calendar data');
            return;
        }
        console.log('✅ DEBUG: Calendar data exists');
        
        if (!calendarData.limitless) {
            console.error('❌ DEBUG: No limitless property found');
            console.log('🔎 DEBUG: Available properties:', Object.keys(calendarData));
            Utils.showEmpty('activity-content', 'DEBUG: No limitless property');
            return;
        }
        console.log('✅ DEBUG: Limitless property exists');
        console.log('🔎 DEBUG: Limitless data:', calendarData.limitless);
        
        if (!calendarData.limitless.has_data) {
            console.log('ℹ️ DEBUG: limitless.has_data is false');
            Utils.showEmpty('activity-content', 'DEBUG: has_data is false');
            return;
        }
        console.log('✅ DEBUG: has_data is true');
        
        if (!calendarData.limitless.raw_items) {
            console.error('❌ DEBUG: No raw_items property');
            console.log('🔎 DEBUG: Limitless properties:', Object.keys(calendarData.limitless));
            Utils.showEmpty('activity-content', 'DEBUG: No raw_items');
            return;
        }
        console.log('✅ DEBUG: raw_items property exists');
        
        const rawItems = calendarData.limitless.raw_items;
        console.log('📊 DEBUG: Raw items count:', rawItems.length);
        if (rawItems.length > 0) {
            console.log('🔎 DEBUG: First item sample:', rawItems[0]);
        }
        
        if (rawItems && rawItems.length > 0) {
            // Test Marked.js availability
            if (typeof marked === 'undefined') {
                console.error('🚨 DEBUG: marked.parse not available!');
                Utils.showError('activity-content', 'DEBUG: Marked.js library missing');
                return;
            }
            console.log('✅ DEBUG: Marked.js is available');
            
            // Process items with detailed logging
            console.log('⚙️ DEBUG: Processing items...');
            const lifelogsHtml = rawItems.map((item, index) => {
                console.log(`📝 DEBUG: Processing item ${index + 1}/${rawItems.length}`);
                
                let metadata = {};
                let sourceId = item.source_id || 'Unknown';
                let lifelogTitle = 'Untitled Lifelog';
                
                if (item.metadata) {
                    try {
                        metadata = typeof item.metadata === 'string' 
                            ? JSON.parse(item.metadata) 
                            : item.metadata;
                        lifelogTitle = metadata.title || metadata.lifelog_title || lifelogTitle;
                        console.log(`✅ DEBUG: Item ${index + 1} metadata parsed, title: "${lifelogTitle}"`);
                    } catch (e) {
                        console.error(`❌ DEBUG: Item ${index + 1} metadata parse error:`, e);
                    }
                }
                
                let markdownContent = metadata.cleaned_markdown || metadata.markdown || item.content || '';
                console.log(`📄 DEBUG: Item ${index + 1} content length: ${markdownContent.length} chars`);
                
                let renderedContent = '';
                try {
                    renderedContent = this.renderLifelogAsMarkdown(markdownContent);
                    console.log(`✅ DEBUG: Item ${index + 1} rendered successfully`);
                } catch (e) {
                    console.error(`❌ DEBUG: Item ${index + 1} render error:`, e);
                    renderedContent = `<p class="text-red-600">Render Error: ${e.message}</p>`;
                }
                
                return `
                    <div class="lifelog-document mb-8 bg-white border border-gray-200 rounded-lg shadow-sm">
                        <div class="lifelog-header p-4 border-b border-gray-200 bg-gray-50">
                            <h3 class="lifelog-title text-lg font-semibold text-gray-900">${Utils.escapeHtml(lifelogTitle)}</h3>
                            <p class="lifelog-meta text-sm text-gray-600 mt-1">
                                ${sourceId ? `ID: ${Utils.escapeHtml(sourceId)}` : ''} • Item ${index + 1}
                            </p>
                        </div>
                        <div class="lifelog-content p-6">
                            <div class="markdown-document">
                                ${renderedContent}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            
            console.log('🎨 DEBUG: Generated HTML length:', lifelogsHtml.length);
            
            const finalHtml = `
                <div class="lifelogs-container">
                    <p class="text-sm text-gray-600 mb-6">🐛 DEBUG: Showing ${rawItems.length} lifelog${rawItems.length === 1 ? '' : 's'}:</p>
                    ${lifelogsHtml}
                </div>
            `;
            
            activityContent.innerHTML = finalHtml;
            console.log('🎯 DEBUG: Activity content updated successfully!');
            
        } else {
            console.log('ℹ️ DEBUG: Raw items array is empty');
            Utils.showEmpty('activity-content', 'DEBUG: Empty raw_items array');
        }
        
    } catch (error) {
        console.error('🚨 DEBUG: Exception in loadActivityData:', error);
        console.error('📍 DEBUG: Error stack:', error.stack);
        Utils.showError('activity-content', `DEBUG Error: ${error.message}`);
    }
}
```

### Step 3.2: Test the Debug Version
1. **Save the file** after replacing the function
2. **Refresh the browser**
3. **Open console** and watch the debug messages
4. **Navigate to different dates** to see data availability

---

## 🔧 Phase 4: Backend Data Verification

### Step 4.1: Check Database for Actual Data
**SSH/terminal into your server and check:**
```sql
-- Check if there's any limitless data
SELECT days_date, COUNT(*) as count 
FROM data_items 
WHERE namespace = 'limitless' 
GROUP BY days_date 
ORDER BY days_date DESC 
LIMIT 10;

-- Check a specific date
SELECT id, source_id, LENGTH(content) as content_len, LENGTH(metadata) as meta_len
FROM data_items 
WHERE namespace = 'limitless' 
AND days_date = '2025-01-07'  -- Replace with your date
LIMIT 5;
```

### Step 4.2: Test Backend API Directly
```bash
# Test the specific endpoint
curl -X GET "http://localhost:8000/calendar/api/day/2025-01-07/enhanced" \
  -H "Accept: application/json"
```

---

## 🚨 Common Issues & Quick Fixes

### Issue 1: Marked.js CDN Failed to Load
**Symptom:** `typeof marked` returns `"undefined"`

**Solutions:**
```html
<!-- Try alternative CDN in simple.html -->
<script src="https://cdn.jsdelivr.net/npm/marked@5.1.1/lib/marked.umd.js"></script>

<!-- Or use unpkg CDN -->
<script src="https://unpkg.com/marked/lib/marked.umd.js"></script>

<!-- Or local fallback -->
<script>
  if (typeof marked === 'undefined') {
    console.error('Marked.js failed to load from CDN');
    document.write('<script src="/static/js/marked.min.js"><\/script>');
  }
</script>
```

### Issue 2: API Returns Empty limitless Data
**Symptom:** API responds but `limitless.has_data` is false

**Check:**
- Is there actual data in database for the selected date?
- Are you checking the right date format (YYYY-MM-DD)?
- Is the Limitless sync service running?

### Issue 3: Metadata Parsing Errors  
**Symptom:** JSON parse errors in console

**Debug:** Check if `item.metadata` is already an object:
```javascript
console.log('Metadata type:', typeof item.metadata);
console.log('Metadata value:', item.metadata);
```

### Issue 4: Markdown Rendering Crashes
**Symptom:** `renderLifelogAsMarkdown` throws errors

**Temporary fix:** Add to `app.js`:
```javascript
renderLifelogAsMarkdown(content) {
    if (!content) return '<p class="text-gray-500 italic">No content available</p>';
    
    try {
        return marked.parse(content, { breaks: true, gfm: true });
    } catch (error) {
        console.error('Markdown render error:', error);
        return `<pre class="bg-gray-100 p-2 rounded">${Utils.escapeHtml(content)}</pre>`;
    }
}
```

### Issue 5: Wrong Date Selected
**Symptom:** API returns data but for wrong date

**Check current app state:**
```javascript
// In browser console
console.log('App current date:', App.currentDate);
console.log('Today:', Utils.getTodayYYYYMMDD());
console.log('Date picker value:', document.getElementById('date-picker').value);
```

---

## 🔄 Recovery Steps

### Step 1: Reset to Working State
If all else fails, revert to a simple version:

```javascript
// Minimal working loadActivityData
async loadActivityData() {
    const activityContent = document.getElementById('activity-content');
    activityContent.innerHTML = '<p>DEBUG: Function is running</p>';
    
    try {
        const data = await API.calendar.getDateData(this.currentDate);
        activityContent.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    } catch (error) {
        activityContent.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    }
}
```

### Step 2: Gradual Feature Re-addition
1. Get basic data display working
2. Add metadata parsing
3. Add basic HTML rendering  
4. Add Marked.js rendering
5. Add speaker pattern processing

---

## 📋 Debugging Checklist

**Before reporting issue resolved:**
- [ ] Console shows no JavaScript errors
- [ ] `typeof marked` returns `"function"`
- [ ] API endpoint returns data with `limitless.raw_items`
- [ ] Activity Summary shows actual content (not empty/loading)
- [ ] Multiple dates tested (not just today)
- [ ] Browser refresh clears any caching issues

---

## 📞 Need Help?

**If you're still stuck after following this guide:**

1. **Copy the debug console output** (all the 🔍 DEBUG messages)
2. **Take a screenshot** of the Network tab showing the API requests
3. **Note which Phase/Step** revealed the issue
4. **Include the exact error messages** from console

**Most common resolution:** 90% of issues are either Marked.js CDN not loading or no data available for the selected date.