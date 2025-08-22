import json
from unittest.mock import MagicMock

import pytest

from config.models import TwitterConfig
from core.database import DatabaseService


@pytest.fixture
def twitter_config_api_enabled():
    """Twitter configuration with API enabled"""
    return TwitterConfig(
        enabled=True,
        bearer_token="REMOVED",
        username="testuser123",
        max_retries=3,
        retry_delay=1.0,
        request_timeout=30.0,
        sync_interval_hours=24,
        delete_after_import=False,
    )

@pytest.fixture
def twitter_config_api_disabled():
    """Twitter configuration with API disabled"""
    return TwitterConfig(
        enabled=True,
        bearer_token=None,
        username=None,
        sync_interval_hours=24,
        delete_after_import=False,
    )

@pytest.fixture
def twitter_config_disabled():
    """Completely disabled Twitter configuration"""
    return TwitterConfig(
        enabled=False,
        bearer_token="valid_token",
        username="testuser",
        sync_interval_hours=24,
        delete_after_import=False,
    )

@pytest.fixture
def sample_twitter_api_user_response():
    """Sample Twitter API user lookup response"""
    return {
        "data": {
            "id": "123456789012345678",
            "name": "Test User",
            "username": "testuser123",
            "verified": False,
            "public_metrics": {
                "followers_count": 100,
                "following_count": 50,
                "tweet_count": 200,
                "listed_count": 5,
            },
        },
    }

@pytest.fixture
def sample_twitter_api_tweets_response():
    """Sample Twitter API tweets response with comprehensive data"""
    return {
        "data": [
            {
                "id": "1750123456789012345",
                "text": "Just deployed a new feature to production! 🚀 #coding #tech",
                "created_at": "2024-01-15T10:30:00.000Z",
                "public_metrics": {
                    "retweet_count": 5,
                    "like_count": 25,
                    "reply_count": 3,
                    "quote_count": 2,
                },
                "context_annotations": [
                    {
                        "domain": {
                            "id": "66",
                            "name": "Twitter Platform",
                            "description": "A prominent social media platform",
                        },
                        "entity": {
                            "id": "781974596752842752",
                            "name": "Services",
                            "description": "Entity representing a commercial service",
                        },
                    },
                ],
                "entities": {
                    "hashtags": [
                        {"start": 50, "end": 57, "tag": "coding"},
                        {"start": 58, "end": 63, "tag": "tech"},
                    ],
                },
            },
            {
                "id": "1750123456789012346",
                "text": "Working on some interesting AI/ML projects. The future is exciting! 🤖",
                "created_at": "2024-01-15T14:45:30.000Z",
                "public_metrics": {
                    "retweet_count": 12,
                    "like_count": 48,
                    "reply_count": 7,
                    "quote_count": 4,
                },
                "context_annotations": [
                    {
                        "domain": {
                            "id": "65",
                            "name": "Interests and Hobbies Vertical",
                            "description": "A vertical for interests and hobbies",
                        },
                        "entity": {
                            "id": "1255885797584535552",
                            "name": "Machine learning",
                            "description": "Machine learning and artificial intelligence",
                        },
                    },
                ],
            },
            {
                "id": "1750123456789012347",
                "text": "Beautiful sunset today 🌅",
                "created_at": "2024-01-15T19:20:15.000Z",
                "public_metrics": {
                    "retweet_count": 2,
                    "like_count": 15,
                    "reply_count": 1,
                    "quote_count": 0,
                },
            },
        ],
        "meta": {
            "result_count": 3,
            "newest_id": "1750123456789012347",
            "oldest_id": "1750123456789012345",
        },
    }

@pytest.fixture
def sample_twitter_api_empty_response():
    """Sample empty Twitter API response"""
    return {
        "meta": {
            "result_count": 0,
        },
    }

@pytest.fixture
def sample_transformed_api_tweets():
    """Sample tweets transformed from API format to internal format"""
    return [
        {
            "tweet_id": "1750123456789012345",
            "created_at": "2024-01-15T10:30:00+00:00",
            "days_date": "2024-01-15",
            "text": "Just deployed a new feature to production! 🚀 #coding #tech",
            "media_urls": "[]",
            "public_metrics": {
                "retweet_count": 5,
                "like_count": 25,
                "reply_count": 3,
                "quote_count": 2,
            },
            "context_annotations": [
                {
                    "domain": {
                        "id": "66",
                        "name": "Twitter Platform",
                        "description": "A prominent social media platform",
                    },
                    "entity": {
                        "id": "781974596752842752",
                        "name": "Services",
                        "description": "Entity representing a commercial service",
                    },
                },
            ],
        },
        {
            "tweet_id": "1750123456789012346",
            "created_at": "2024-01-15T14:45:30+00:00",
            "days_date": "2024-01-15",
            "text": "Working on some interesting AI/ML projects. The future is exciting! 🤖",
            "media_urls": "[]",
            "public_metrics": {
                "retweet_count": 12,
                "like_count": 48,
                "reply_count": 7,
                "quote_count": 4,
            },
            "context_annotations": [
                {
                    "domain": {
                        "id": "65",
                        "name": "Interests and Hobbies Vertical",
                        "description": "A vertical for interests and hobbies",
                    },
                    "entity": {
                        "id": "1255885797584535552",
                        "name": "Machine learning",
                        "description": "Machine learning and artificial intelligence",
                    },
                },
            ],
        },
        {
            "tweet_id": "1750123456789012347",
            "created_at": "2024-01-15T19:20:15+00:00",
            "days_date": "2024-01-15",
            "text": "Beautiful sunset today 🌅",
            "media_urls": "[]",
            "public_metrics": {
                "retweet_count": 2,
                "like_count": 15,
                "reply_count": 1,
                "quote_count": 0,
            },
            "context_annotations": [],
        },
    ]

@pytest.fixture
def sample_existing_twitter_data():
    """Sample existing Twitter data in database format"""
    return [
        {
            "namespace": "twitter",
            "source_id": "1749000000000000001",
            "content": "This is an archived tweet from yesterday",
            "metadata": json.dumps({
                "media_urls": "[]",
                "original_created_at": "2024-01-14T15:30:00+00:00",
                "days_date": "2024-01-14",
                "source_type": "twitter_archive",
            }),
            "created_at": "2024-01-14T15:30:00+00:00",
            "updated_at": "2024-01-14T15:30:00+00:00",
        },
        {
            "namespace": "twitter",
            "source_id": "1749000000000000002",
            "content": "Another archived tweet",
            "metadata": json.dumps({
                "media_urls": '["https://pbs.twimg.com/media/example.jpg"]',
                "original_created_at": "2024-01-14T20:15:00+00:00",
                "days_date": "2024-01-14",
                "source_type": "twitter_archive",
            }),
            "created_at": "2024-01-14T20:15:00+00:00",
            "updated_at": "2024-01-14T20:15:00+00:00",
        },
    ]

@pytest.fixture
def mock_twitter_database_service(sample_existing_twitter_data):
    """Mock database service with pre-configured Twitter data"""
    db_service = MagicMock(spec=DatabaseService)
    db_service.get_data_items_by_namespace.return_value = sample_existing_twitter_data
    db_service.get_data_items_by_ids.return_value = []
    db_service.get_data_items_by_date.return_value = sample_existing_twitter_data
    return db_service

@pytest.fixture
def sample_twitter_api_errors():
    """Sample Twitter API error responses"""
    return {
        "unauthorized": {
            "status": 401,
            "response": {
                "errors": [
                    {
                        "message": "Unauthorized",
                        "code": 32,
                    },
                ],
            },
        },
        "rate_limited": {
            "status": 429,
            "response": {
                "errors": [
                    {
                        "message": "Rate limit exceeded",
                        "code": 88,
                    },
                ],
            },
            "headers": {
                "retry-after": "900",  # 15 minutes
            },
        },
        "user_not_found": {
            "status": 404,
            "response": {
                "errors": [
                    {
                        "value": "nonexistentuser",
                        "detail": "Could not find user with username: [nonexistentuser].",
                        "title": "Not Found Error",
                        "resource_type": "user",
                        "parameter": "username",
                        "resource_id": "nonexistentuser",
                        "type": "https://api.twitter.com/2/problems/resource-not-found",
                    },
                ],
            },
        },
        "server_error": {
            "status": 500,
            "response": {
                "errors": [
                    {
                        "message": "Internal Server Error",
                        "code": 131,
                    },
                ],
            },
        },
    }

@pytest.fixture
def twitter_archive_sample_data(tmp_path):
    """Sample Twitter archive data for import testing"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    tweets_js_path = data_dir / "tweets.js"  # Note: using "tweets.js" not "tweet.js"

    tweets_data = [
        {
            "tweet": {
                "id": "1234567890123456789",
                "id_str": "1234567890123456789",
                "created_at": "Mon Jan 15 10:30:00 +0000 2024",
                "full_text": "This is a sample archived tweet with media",
                "entities": {
                    "media": [
                        {
                            "media_url_https": "https://pbs.twimg.com/media/sample1.jpg",
                        },
                        {
                            "media_url_https": "https://pbs.twimg.com/media/sample2.jpg",
                        },
                    ],
                    "hashtags": [
                        {"text": "sample", "indices": [10, 17]},
                    ],
                },
            },
        },
        {
            "tweet": {
                "id": "9876543210987654321",
                "id_str": "9876543210987654321",
                "created_at": "Mon Jan 15 14:45:00 +0000 2024",
                "full_text": "Another archived tweet without media",
                "entities": {
                    "hashtags": [],
                    "urls": [],
                },
            },
        },
    ]

    with open(tweets_js_path, "w", encoding="utf-8") as f:
        f.write(f"window.YTD.tweets.part0 = {json.dumps(tweets_data)}")

    return tmp_path
