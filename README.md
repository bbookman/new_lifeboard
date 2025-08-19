# Lifeboard Vision Statement

Lifeboard is an interactive reflection space where there is infinite opportunity for discovery. Seamlessly pulling from your digital history—conversations, activities, moods, and experiences —it transforms each day into a personal newspaper. With AI assistance that you can engage through natural conversation, you'll rediscover meaning in the everyday and take control of your future journey.
  
But you don't always have to know where to look. Lifeboard invites serendipity through random resurfacing of forgotten moments and AI-guided discovery journeys—because some of life's richest memories are the ones you didn't expect to find.  

Beyond reflection, Lifeboard empowers the present and the future. Your personal assistant will help you keep up with to-dos, pull out insights from business meetings, keep track of important medical appointments, and beyond
  
It's about seeing anew—with clarity, gratitude, proactive power and wonder.

## Requirements

- Python 3.9 or higher
- macOS (currently only tested platform)


## Configuration

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env file with your settings:**

### Required Settings

Basic user configuration
```
USERS_LANGUAGE=en
TIME_ZONE=America/New_York

Limitless API (Primary data source)
LIMITLESS__API_KEY=your_limitless_api_key_here
```
### Optional
#### RapidAPI
**News**
1. Sign up for free at [RapidAPI](https://rapidapi.com/)
2. Subscribe to these APIs free:
   - [Real-Time News Data](https://rapidapi.com/letscrape-6bRBa3QguO5/api/real-time-news-data) - For news headlines

```
RAPID_API_KEY=your_rapidapi_key_here
News configuration
NEWS_COUNTRY=US
UNIQUE_NEWS_ITEMS_PER_DAY=5
```

**TWITTER**
[Follow these instructions for establishing an api key](https://developer.x.com/en/docs/tutorials/step-by-step-guide-to-making-your-first-request-to-the-twitter-api-v2)


```
TWITTER_BEARER_TOKEN=your token / api key here
TWITTER_USER_NAME=your user name
```

*Note: Most other settings in .env.example are not currently functional and can be ignored.*

## Installation

### Option 1: Auto Install (Recommended)
```bash
# Clone the repository
git clone [REPO_URL]
cd new_lifeboard

# Run auto install script
chmod +x install_project.sh
./install_project.sh
```
This script will:
- Create a Python virtual environment
- Install Python dependencies
- Build the front end 
- Set up the project structure
- Run the entire application

The application will be available at:
- **Frontend**: `http://localhost:5173` (main application interface)
- **Backend API**: `http://localhost:8000` (API endpoints)

### Option 2: Manual Installation
```bash
# Clone the repository
git clone [REPO_URL]
cd new_lifeboard

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies and build the frontend
cd frontend
npm install
npm run build
cd ..
```


## First Run Setup
- **Initial data sync**: The first run may take up to 5 minutes to fetch and process all your data
- **"No data" messages**: This is normal during initial setup - just wait for the sync to complete
- **Automatic updates**: The app will automatically sync new data based on your configured intervals

## File bugs!!!
Use the git issues system.  Document your bugs clearly.  Or fork the repo and fix the bug :) then make a pull request.  Always write a test for your fix so it can be integrated into the test system (/tests)

## Notes
- The app agresively manages port conflicts and may kill running processes that are on ports it needs (although it shouldn't, it is not out of the realm of the possible)
- Twitter import can be done in SETTING for tweet history and must be requested from twitter. See https://www.businessinsider.com/guides/tech/twitter-archive