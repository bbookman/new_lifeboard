"""
Realistic test data generators for comprehensive testing.

This module provides factories for generating realistic test data
across all data types and sources used in the Lifeboard application.
"""

import pytest
import json
import random
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from faker import Faker
from dataclasses import dataclass

from sources.base import DataItem


# Initialize Faker for realistic data generation
fake = Faker()
Faker.seed(42)  # Consistent seed for reproducible tests


@dataclass
class TestDataConfig:
    """Configuration for test data generation"""
    start_date: datetime = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date: datetime = datetime(2025, 1, 31, tzinfo=timezone.utc)
    include_weekends: bool = True
    time_zones: List[str] = None
    languages: List[str] = None
    
    def __post_init__(self):
        if self.time_zones is None:
            self.time_zones = ["UTC", "America/Los_Angeles", "America/New_York", "Europe/London"]
        if self.languages is None:
            self.languages = ["en", "es", "fr", "de"]


class LimitlessDataFactory:
    """Factory for generating realistic Limitless lifelog data"""
    
    @staticmethod
    def create_meeting_content():
        """Generate realistic meeting content"""
        topics = [
            "project planning", "quarterly review", "team standup", "client presentation",
            "budget discussion", "product roadmap", "technical architecture", "user feedback",
            "marketing strategy", "team building", "performance review", "sprint planning"
        ]
        
        speakers = ["User", "Alice", "Bob", "Sarah", "Mike", "Emma", "David", "Lisa"]
        
        content_blocks = []
        start_time = fake.date_time_this_month(tzinfo=timezone.utc)
        
        for i in range(random.randint(3, 12)):
            speaker = random.choice(speakers)
            topic = random.choice(topics)
            
            block_start = start_time + timedelta(seconds=i * random.randint(5, 30))
            block_end = block_start + timedelta(seconds=random.randint(3, 15))
            
            content_blocks.append({
                "type": "blockquote",
                "content": f"Let's discuss the {topic}. {fake.sentence()}",
                "startTime": block_start.isoformat(),
                "endTime": block_end.isoformat(),
                "startOffsetMs": i * 1000,
                "endOffsetMs": (i + 1) * 1000,
                "children": [],
                "speakerName": speaker,
                "speakerIdentifier": speaker.lower() if speaker != "User" else "user"
            })
        
        return {
            "type": "doc",
            "content": content_blocks
        }
    
    @staticmethod
    def create_conversation_content():
        """Generate realistic conversation content"""
        conversation_types = [
            "brainstorming session", "technical discussion", "feedback session",
            "problem solving", "idea sharing", "decision making", "planning session"
        ]
        
        conv_type = random.choice(conversation_types)
        participants = fake.random_int(min=2, max=5)
        
        content_blocks = []
        for i in range(random.randint(5, 20)):
            speaker = f"Participant {random.randint(1, participants)}"
            content_blocks.append({
                "type": "paragraph",
                "content": fake.sentence() + " " + fake.sentence(),
                "speaker": speaker,
                "timestamp": fake.date_time_this_month(tzinfo=timezone.utc).isoformat()
            })
        
        return {
            "type": "conversation",
            "conversation_type": conv_type,
            "content": content_blocks
        }
    
    @staticmethod
    def create_lifelog_item(
        item_id: str = None,
        title: str = None,
        content_type: str = "meeting",
        days_date: str = None
    ) -> DataItem:
        """Create a realistic Limitless lifelog DataItem"""
        
        if item_id is None:
            item_id = f"limitless:{fake.uuid4()[:8]}"
        
        if title is None:
            title_types = {
                "meeting": lambda: f"{fake.company()} {random.choice(['Meeting', 'Standup', 'Review', 'Discussion'])}",
                "conversation": lambda: f"{random.choice(['Chat', 'Discussion', 'Call'])} with {fake.first_name()}",
                "note": lambda: f"Note: {fake.catch_phrase()}",
                "interview": lambda: f"Interview with {fake.name()}"
            }
            title = title_types.get(content_type, title_types["meeting"])()
        
        if days_date is None:
            days_date = fake.date_between(
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2025, 1, 31).date()
            ).strftime("%Y-%m-%d")
        
        start_time = fake.date_time_this_month(tzinfo=timezone.utc)
        end_time = start_time + timedelta(minutes=random.randint(15, 120))
        
        # Generate content based on type
        if content_type == "meeting":
            content_data = LimitlessDataFactory.create_meeting_content()
        else:
            content_data = LimitlessDataFactory.create_conversation_content()
        
        metadata = {
            "title": title,
            "lifelog_id": f"lifelog_{fake.uuid4()[:12]}",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "is_starred": fake.boolean(chance_of_getting_true=10),
            "updated_at_api": fake.date_time_recent(days=7, tzinfo=timezone.utc).isoformat(),
            "duration": int((end_time - start_time).total_seconds()),
            "participant_count": random.randint(1, 8),
            "content_type": content_type
        }
        
        # Extract text content for the content field
        if isinstance(content_data, dict) and "content" in content_data:
            text_content = " ".join([
                block.get("content", "") for block in content_data["content"]
                if isinstance(block, dict) and "content" in block
            ])
        else:
            text_content = f"Lifelog content for {title}"
        
        return DataItem(
            id=item_id,
            namespace="limitless",
            source_id=item_id.split(":")[-1],
            content=text_content,
            metadata=metadata,
            days_date=days_date
        )


class NewsDataFactory:
    """Factory for generating realistic news data"""
    
    @staticmethod
    def create_news_article(
        item_id: str = None,
        category: str = None,
        days_date: str = None
    ) -> DataItem:
        """Create a realistic news article DataItem"""
        
        if item_id is None:
            item_id = f"news:{fake.uuid4()[:8]}"
        
        categories = [
            "Technology", "Business", "Politics", "Science", "Health", 
            "Sports", "Entertainment", "World", "Environment", "Finance"
        ]
        
        if category is None:
            category = random.choice(categories)
        
        if days_date is None:
            days_date = fake.date_between(
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2025, 1, 31).date()
            ).strftime("%Y-%m-%d")
        
        title = fake.sentence(nb_words=random.randint(6, 12)).rstrip('.')
        snippet = fake.text(max_nb_chars=200)
        
        metadata = {
            "title": title,
            "link": fake.url(),
            "snippet": snippet,
            "published_datetime_utc": fake.date_time_this_month(tzinfo=timezone.utc).isoformat(),
            "thumbnail_url": fake.image_url(width=300, height=200),
            "category": category,
            "source": fake.company(),
            "author": fake.name(),
            "language": "en",
            "country": "US"
        }
        
        return DataItem(
            id=item_id,
            namespace="news",
            source_id=item_id.split(":")[-1],
            content=f"{title}. {snippet}",
            metadata=metadata,
            days_date=days_date
        )


class WeatherDataFactory:
    """Factory for generating realistic weather data"""
    
    @staticmethod
    def create_weather_forecast(
        item_id: str = None,
        location: str = None,
        days_date: str = None
    ) -> DataItem:
        """Create a realistic weather forecast DataItem"""
        
        if item_id is None:
            item_id = f"weather:{fake.uuid4()[:8]}"
        
        if location is None:
            location = f"{fake.city()}, {fake.state_abbr()}"
        
        if days_date is None:
            days_date = fake.date_between(
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2025, 1, 31).date()
            ).strftime("%Y-%m-%d")
        
        conditions = [
            "Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Thunderstorms",
            "Light Rain", "Heavy Rain", "Snow", "Fog", "Clear"
        ]
        
        condition = random.choice(conditions)
        temp_max = random.uniform(40, 85)
        temp_min = temp_max - random.uniform(10, 25)
        
        content = f"Weather forecast for {location}: {condition}, high {temp_max:.1f}°F, low {temp_min:.1f}°F"
        
        metadata = {
            "location": location,
            "forecast_date": days_date,
            "condition": condition,
            "temperature_max": temp_max,
            "temperature_min": temp_min,
            "humidity": random.uniform(30, 90),
            "wind_speed": random.uniform(0, 25),
            "precipitation_chance": random.uniform(0, 100),
            "uv_index": random.randint(1, 10),
            "visibility": random.uniform(5, 15),
            "reported_time": fake.date_time_this_month(tzinfo=timezone.utc).isoformat()
        }
        
        return DataItem(
            id=item_id,
            namespace="weather",
            source_id=item_id.split(":")[-1],
            content=content,
            metadata=metadata,
            days_date=days_date
        )


class TwitterDataFactory:
    """Factory for generating realistic Twitter/social media data"""
    
    @staticmethod
    def create_tweet(
        item_id: str = None,
        days_date: str = None
    ) -> DataItem:
        """Create a realistic tweet DataItem"""
        
        if item_id is None:
            item_id = f"twitter:{fake.uuid4()[:8]}"
        
        if days_date is None:
            days_date = fake.date_between(
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2025, 1, 31).date()
            ).strftime("%Y-%m-%d")
        
        tweet_types = [
            lambda: fake.sentence(nb_words=random.randint(8, 20)),
            lambda: f"Just finished {fake.bs()}. Great experience!",
            lambda: f"Thinking about {fake.catch_phrase()}... {fake.sentence()}",
            lambda: f"Excited to share: {fake.sentence()}",
            lambda: f"#{fake.word()} #{fake.word()} {fake.sentence()}"
        ]
        
        content = random.choice(tweet_types)()
        
        metadata = {
            "tweet_id": fake.uuid4(),
            "username": fake.user_name(),
            "timestamp": fake.date_time_this_month(tzinfo=timezone.utc).isoformat(),
            "retweets": random.randint(0, 100),
            "likes": random.randint(0, 500),
            "replies": random.randint(0, 50),
            "is_retweet": fake.boolean(chance_of_getting_true=20),
            "hashtags": [f"#{fake.word()}" for _ in range(random.randint(0, 3))],
            "mentions": [f"@{fake.user_name()}" for _ in range(random.randint(0, 2))]
        }
        
        return DataItem(
            id=item_id,
            namespace="twitter",
            source_id=item_id.split(":")[-1],
            content=content,
            metadata=metadata,
            days_date=days_date
        )


class TestDataGenerator:
    """Main test data generator with batch creation capabilities"""
    
    def __init__(self, config: TestDataConfig = None):
        self.config = config or TestDataConfig()
    
    def generate_mixed_dataset(
        self,
        total_items: int = 50,
        limitless_ratio: float = 0.4,
        news_ratio: float = 0.3,
        weather_ratio: float = 0.2,
        twitter_ratio: float = 0.1
    ) -> List[DataItem]:
        """Generate a mixed dataset with specified ratios"""
        
        items = []
        
        # Calculate counts
        limitless_count = int(total_items * limitless_ratio)
        news_count = int(total_items * news_ratio)
        weather_count = int(total_items * weather_ratio)
        twitter_count = total_items - limitless_count - news_count - weather_count
        
        # Generate date range
        date_range = []
        current_date = self.config.start_date.date()
        while current_date <= self.config.end_date.date():
            if self.config.include_weekends or current_date.weekday() < 5:
                date_range.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
        
        # Generate Limitless items
        for i in range(limitless_count):
            days_date = random.choice(date_range) if date_range else None
            items.append(LimitlessDataFactory.create_lifelog_item(days_date=days_date))
        
        # Generate News items
        for i in range(news_count):
            days_date = random.choice(date_range) if date_range else None
            items.append(NewsDataFactory.create_news_article(days_date=days_date))
        
        # Generate Weather items
        for i in range(weather_count):
            days_date = random.choice(date_range) if date_range else None
            items.append(WeatherDataFactory.create_weather_forecast(days_date=days_date))
        
        # Generate Twitter items
        for i in range(twitter_count):
            days_date = random.choice(date_range) if date_range else None
            items.append(TwitterDataFactory.create_tweet(days_date=days_date))
        
        return items
    
    def generate_daily_dataset(self, date: str) -> List[DataItem]:
        """Generate a realistic dataset for a specific day"""
        items = []
        
        # Typical daily distribution
        items.extend([
            LimitlessDataFactory.create_lifelog_item(days_date=date)
            for _ in range(random.randint(2, 5))
        ])
        
        items.extend([
            NewsDataFactory.create_news_article(days_date=date)
            for _ in range(random.randint(3, 8))
        ])
        
        items.append(WeatherDataFactory.create_weather_forecast(days_date=date))
        
        items.extend([
            TwitterDataFactory.create_tweet(days_date=date)
            for _ in range(random.randint(1, 4))
        ])
        
        return items
    
    def generate_performance_dataset(self, size: int = 1000) -> List[DataItem]:
        """Generate a large dataset for performance testing"""
        return self.generate_mixed_dataset(total_items=size)


# Pytest Fixtures

@pytest.fixture
def test_data_config():
    """Default test data configuration"""
    return TestDataConfig()


@pytest.fixture
def test_data_generator(test_data_config):
    """Test data generator with default configuration"""
    return TestDataGenerator(test_data_config)


@pytest.fixture
def sample_limitless_items():
    """Sample Limitless lifelog items"""
    return [
        LimitlessDataFactory.create_lifelog_item(
            title="Project Planning Meeting",
            content_type="meeting",
            days_date="2025-01-15"
        ),
        LimitlessDataFactory.create_lifelog_item(
            title="Team Standup",
            content_type="meeting",
            days_date="2025-01-15"
        ),
        LimitlessDataFactory.create_lifelog_item(
            title="Client Discussion",
            content_type="conversation",
            days_date="2025-01-16"
        )
    ]


@pytest.fixture
def sample_news_items():
    """Sample news articles"""
    return [
        NewsDataFactory.create_news_article(
            category="Technology",
            days_date="2025-01-15"
        ),
        NewsDataFactory.create_news_article(
            category="Business",
            days_date="2025-01-15"
        ),
        NewsDataFactory.create_news_article(
            category="Science",
            days_date="2025-01-16"
        )
    ]


@pytest.fixture
def sample_weather_items():
    """Sample weather forecasts"""
    return [
        WeatherDataFactory.create_weather_forecast(
            location="San Francisco, CA",
            days_date="2025-01-15"
        ),
        WeatherDataFactory.create_weather_forecast(
            location="New York, NY",
            days_date="2025-01-16"
        )
    ]


@pytest.fixture
def sample_twitter_items():
    """Sample tweets"""
    return [
        TwitterDataFactory.create_tweet(days_date="2025-01-15"),
        TwitterDataFactory.create_tweet(days_date="2025-01-15"),
        TwitterDataFactory.create_tweet(days_date="2025-01-16")
    ]


@pytest.fixture
def mixed_sample_dataset(test_data_generator):
    """Mixed dataset with all data types"""
    return test_data_generator.generate_mixed_dataset(total_items=20)


@pytest.fixture
def daily_sample_dataset(test_data_generator):
    """Sample dataset for a single day"""
    return test_data_generator.generate_daily_dataset("2025-01-15")


@pytest.fixture
def large_sample_dataset(test_data_generator):
    """Large dataset for performance testing"""
    return test_data_generator.generate_performance_dataset(size=100)


# Data Validation Utilities

class DataValidator:
    """Utilities for validating generated test data"""
    
    @staticmethod
    def validate_data_item(item: DataItem) -> bool:
        """Validate that a DataItem has all required fields"""
        required_fields = ['id', 'namespace', 'source_id', 'content', 'days_date']
        
        for field in required_fields:
            if not hasattr(item, field) or getattr(item, field) is None:
                return False
        
        # Validate ID format
        if ':' not in item.id:
            return False
        
        namespace_from_id = item.id.split(':', 1)[0]
        if namespace_from_id != item.namespace:
            return False
        
        return True
    
    @staticmethod
    def validate_dataset(items: List[DataItem]) -> Dict[str, Any]:
        """Validate a dataset and return validation results"""
        results = {
            "total_items": len(items),
            "valid_items": 0,
            "invalid_items": 0,
            "namespaces": {},
            "date_range": {"earliest": None, "latest": None},
            "errors": []
        }
        
        for item in items:
            if DataValidator.validate_data_item(item):
                results["valid_items"] += 1
                
                # Count by namespace
                namespace = item.namespace
                results["namespaces"][namespace] = results["namespaces"].get(namespace, 0) + 1
                
                # Track date range
                if results["date_range"]["earliest"] is None or item.days_date < results["date_range"]["earliest"]:
                    results["date_range"]["earliest"] = item.days_date
                if results["date_range"]["latest"] is None or item.days_date > results["date_range"]["latest"]:
                    results["date_range"]["latest"] = item.days_date
            else:
                results["invalid_items"] += 1
                results["errors"].append(f"Invalid item: {getattr(item, 'id', 'unknown')}")
        
        return results


@pytest.fixture
def data_validator():
    """Data validation utilities"""
    return DataValidator


# Export all commonly used fixtures and classes
__all__ = [
    "TestDataConfig",
    "LimitlessDataFactory",
    "NewsDataFactory", 
    "WeatherDataFactory",
    "TwitterDataFactory",
    "TestDataGenerator",
    "DataValidator",
    "test_data_config",
    "test_data_generator",
    "sample_limitless_items",
    "sample_news_items",
    "sample_weather_items",
    "sample_twitter_items",
    "mixed_sample_dataset",
    "daily_sample_dataset",
    "large_sample_dataset",
    "data_validator"
]