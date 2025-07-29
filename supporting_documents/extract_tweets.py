# THIS FILE IS AN EXAMPLE OF HOW TO PARSE TWEETS
# IT IS ONLY AN EXAMPLE AND SHOULD NOT BE CONSIDERED THE EXACT CODE TO CREATE FOR PARSING TWEETS
# THE PATH TO TWEET DATA WILL BE DERIVED FROM .env PATH_TO_TWITTER_DATA
# .env DELETE_AFTER_IMPORT means the twitter export will be removed from 
# PATH_TO_TWITTER_DATA after the app imports the data

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

def parse_tweet_headers(headers_file):
    try:
        with open(headers_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Remove JavaScript wrapper
            if 'window.YTD.tweet_headers.part0 = [' in content:
                content = content.split('window.YTD.tweet_headers.part0 = [', 1)[1]
                content = content.rsplit('];', 1)[0]
            
            # Use regex to find tweet objects
            tweet_pattern = re.compile(r'\{\s*"tweet"\s*:\s*\{.*?\}\s*\}', re.DOTALL)
            tweets = []
            for match in tweet_pattern.finditer(content):
                tweet_str = match.group(0)
                try:
                    # Clean up the tweet string
                    tweet_str = tweet_str.strip()
                    # Replace single quotes with double quotes
                    tweet_str = tweet_str.replace("'", '"')
                    # Fix any escaped quotes
                    tweet_str = tweet_str.replace('\\"', '"')
                    
                    tweet = json.loads(tweet_str)
                    tweets.append(tweet)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse tweet header: {str(e)}")
                    continue
            return tweets
    except Exception as e:
        print(f"Error parsing tweet headers: {str(e)}")
        return []

def get_tweet_text(tweet_id, tweets_file):
    try:
        with open(tweets_file, 'r', encoding='utf-8') as f:
            # Read the entire file
            content = f.read()
            
            # Create regex pattern to find tweet object
            tweet_pattern = re.compile(
                rf'"id_str"\s*:\s*"{tweet_id}".*?"full_text"\s*:\s*"([^"]*)"',
                re.DOTALL
            )
            # Look for media_url_https in the entire content after the tweet id
            media_pattern = re.compile(
                rf'"id_str"\s*:\s*"{tweet_id}".*?"media_url_https"\s*:\s*"([^"]*)',
                re.DOTALL
            )
            
            # Find the tweet text using regex
            text_match = tweet_pattern.search(content)
            if text_match:
                text = text_match.group(1)
                
                # Find media URLs in the entire content
                media_match = media_pattern.search(content)
                media_urls = [media_match.group(1)] if media_match else []
                
                # Also check for media in the entities structure
                entities_pattern = re.compile(
                    rf'"id_str"\s*:\s*"{tweet_id}".*?"entities"\s*:\s*\{{.*?"media"\s*:\s*\[(.*?)\]',
                    re.DOTALL
                )
                entities_match = entities_pattern.search(content)
                if entities_match:
                    media_entities = entities_match.group(1)
                    media_matches = re.finditer(r'"media_url_https"\s*:\s*"([^"]*)', media_entities)
                    media_urls.extend(match.group(1) for match in media_matches)
                
                # Remove duplicates while preserving order
                seen = set()
                unique_media_urls = []
                for url in media_urls:
                    if url not in seen:
                        seen.add(url)
                        unique_media_urls.append(url)
                
                return text, unique_media_urls
            
            return "", []
            
    except Exception as e:
        print(f"Error reading tweets file: {str(e)}")
        return "", []

def get_media_url(tweet_id, media_dir):
    media_urls = []
    if os.path.exists(media_dir):
        try:
            for filename in os.listdir(media_dir):
                if filename.startswith(tweet_id):
                    media_urls.append(os.path.join(media_dir, filename))
        except Exception as e:
            print(f"Error accessing media directory: {str(e)}")
    return media_urls

def main():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, 'twitter-x', 'data')
        headers_file = os.path.join(data_dir, 'tweet-headers.js')
        tweets_file = os.path.join(data_dir, 'tweets.js')
        media_dir = os.path.join(data_dir, 'tweets_media')
        
        # Parse tweet headers
        print("Parsing tweet headers...")
        tweets = parse_tweet_headers(headers_file)
        if not tweets:
            print("No tweets found to process.")
            return
            
        print(f"Found {len(tweets)} tweets to process...")
        
        # Process tweets
        tweet_data_list = []
        for i, tweet in enumerate(tweets, 1):
            if i % 100 == 0:
                print(f"Processing tweet {i}/{len(tweets)}...")
                
            tweet_data = tweet.get('tweet', {})
            tweet_id = tweet_data.get('tweet_id')
            if not tweet_id:
                print(f"Warning: No tweet_id found in tweet: {tweet}")
                continue
                
            try:
                text, media_urls = get_tweet_text(tweet_id, tweets_file)
                additional_media_urls = get_media_url(tweet_id, media_dir)
                all_media_urls = media_urls + additional_media_urls
                
                tweet_data_list.append({
                    'tweet_id': tweet_id,
                    'created_at': tweet_data.get('created_at'),
                    'text': text,
                    'media_urls': all_media_urls
                })
                
            except Exception as e:
                print(f"Error processing tweet {tweet_id}: {str(e)}")
                continue
        
        

if __name__ == "__main__":
    main()
