# Lifeboard Simple UI

A lightweight HTML/CSS/JavaScript alternative to the React frontend for Lifeboard.

## Overview

This simple UI provides the same functionality as the React frontend but with:
- No build process required
- Faster loading times
- Works without JavaScript frameworks
- Better compatibility with older browsers
- Easier customization

## Features

- **Navigation**: Switch between Day View, Calendar, Chat, and Settings
- **Day View**: Weather, news, and activity summaries for any date
- **Calendar View**: Interactive calendar with data visualization
- **Chat Interface**: Real-time chat with your personal data
- **Settings**: System information and data source management
- **Responsive Design**: Mobile-friendly interface

## Access

The simple UI is available at: `http://localhost:8000/simple` when the Lifeboard backend is running.

## Files Structure

```
static/
├── simple.html          # Main HTML page
├── css/
│   ├── main.css         # Core styles
│   ├── newspaper.css    # Newspaper theme styles
│   └── responsive.css   # Mobile/responsive styles
├── js/
│   ├── app.js          # Main application logic
│   ├── api.js          # API communication
│   ├── chat.js         # Chat functionality
│   └── utils.js        # Utility functions
└── assets/             # Static assets (currently empty)
```

## Technology

- Pure HTML5, CSS3, and vanilla JavaScript
- No external dependencies except Google Fonts
- Uses the same API endpoints as the React frontend
- Responsive design with mobile-first approach
- Newspaper-style theme matching the main UI

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers
- Works without JavaScript (graceful degradation)

## Customization

The simple UI can be easily customized by editing:
- `css/main.css` - Core styles and layout
- `css/newspaper.css` - Theme colors and newspaper styling
- `css/responsive.css` - Mobile and responsive behavior
- `js/app.js` - Application behavior and functionality