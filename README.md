# Lifeboard

An interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. Lifeboard seamlessly integrates conversations, activities, moods, and experiences with AI assistance for discovery and planning.

## Quick Start

### Installation
```bash
# Clone the repository
git clone THE REPO URL GIVEN WHEN YOU WERE NOTIFIED THE APP IS AVAILABLE
cd new_lifeboard
```

#### Install options
##### Option 1 - Auto install script
This will create a python virtual environment, install python libraries and build node frontend
```bash
chmod 777 install_project.sh
./install_project.sh
```
##### Option 2 - Install dependencies
- Create python virtual environment
```bash
python3 -m venv venv
```
- Activate
```bash
source venv/bin/activate
```

- Install libraries
```bash
pip3 install -r requirements.txt
```

### Configuration
Copy .env.example to .env
Ignore the majority of the settings, they are not functional ATM

1. Update 
USERS_LANGUAGE=en
TIME_ZONE=America/New_York

2. Add your key
LIMITLESS__API_KEY=your key here

3. To get News, add a Rapid API key, it's free
Get key: https://rapidapi.com/

Enable this API: https://rapidapi.com/letscrape-6bRBa3QguO5/api/real-time-news-data

RAPID_API_KEY=your key here

## Running the app
```bash
chmod 777 start_full_stack.sh
./start_full_stack.sh
```

## Wait
It may take up to 5 minutes to get all your data and store it.  If you see a lot of "No data", just wait.

## File bugs!!!
Use the git issues system.  Document your bugs clearly.  Or fork the repo and fix the bug :) then make a pull request.  Always write a test for your fix so it can be integrated into the test system (/tests)

## Notes
- The app agresively manages port conflicts and may kill running processes that are on ports it needs (although it shouldn't, it is not out of the realm of the possible)
- Only tested on MacOS
- Only tested with latest version of Python3
- OPENAI env variables are not functional
- Chat is hidden and therefore Ollama settings will do nothing
- Twitter import is for tweet history, must be requested from twitter. See https://www.businessinsider.com/guides/tech/twitter-archive