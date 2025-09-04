#!/bin/bash
# get_twitter_user_id.sh
# Fetch Twitter user ID using Twitter API v2, curl, and jq
# Usage: ./get_twitter_user_id.sh [BEARER_TOKEN] [USERNAME]
# If arguments are not provided, reads from TWITTER_BEARER_TOKEN and TWITTER_USER_NAME env vars

# Check for required dependencies
if ! command -v curl &> /dev/null; then
  echo "Error: curl is not installed." >&2
  exit 1
fi
if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed." >&2
  exit 1
fi


# Parse flags and positional arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -USERNAME)
      USERNAME="$2"
      shift 2
      ;;
    -BEARER_TOKEN)
      BEARER_TOKEN="$2"
      shift 2
      ;;
    *)
      # Fallback to positional args if not set by flags
      if [[ -z "$BEARER_TOKEN" ]]; then
        BEARER_TOKEN="$1"
      elif [[ -z "$USERNAME" ]]; then
        USERNAME="$1"
      fi
      shift
      ;;
  esac
done

# Fallback to env vars if not set by flags or positional args
BEARER_TOKEN="${BEARER_TOKEN:-$TWITTER_BEARER_TOKEN}"
USERNAME="${USERNAME:-$TWITTER_USER_NAME}"

# Usage instructions
if [[ -z "$BEARER_TOKEN" || -z "$USERNAME" ]]; then
  echo "Usage: $0 [BEARER_TOKEN] [USERNAME]"
  echo "   or: $0 -BEARER_TOKEN <token> -USERNAME <username>"
  echo "   or set TWITTER_BEARER_TOKEN and TWITTER_USER_NAME environment variables."
  exit 1
fi

# Twitter API endpoint
URL="https://api.twitter.com/2/users/by/username/$USERNAME"

# Make API request and capture response and HTTP status code safely
RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" -H "Authorization: Bearer $BEARER_TOKEN" "$URL")
BODY=$(echo "$RESPONSE" | sed -e 's/HTTPSTATUS:.*//g')
STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')

# Handle response
case "$STATUS" in
  200)
    USER_ID=$(echo "$BODY" | jq -r '.data.id' 2>/dev/null)
    if [[ "$USER_ID" == "null" || -z "$USER_ID" ]]; then
      echo "Error: Could not extract user ID from response."
      echo "Raw response: $BODY"
      exit 1
    fi
    echo "Success! Twitter user ID for '$USERNAME': $USER_ID"
    echo "Add this to your .env file:"
    echo "TWITTER_USER_ID=$USER_ID"
    exit 0
    ;;
  401)
    echo "Error: Authentication failed. Invalid bearer token."
    exit 1
    ;;
  403)
    echo "Error: Permission denied. Bearer token does not have access to user lookup."
    exit 1
    ;;
  404)
    echo "Error: User '$USERNAME' not found."
    exit 1
    ;;
  429)
    echo "Error: Rate limit exceeded. Please try again later."
    exit 1
    ;;
  *)
    echo "Error: Unexpected HTTP status $STATUS. Response:"
    echo "$BODY"
    exit 1
    ;;
esac
