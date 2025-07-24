import pytest
import os
import json
from datetime import datetime
from sources.twitter import TwitterSource, _parse_twitter_export

@pytest.fixture
def sample_twitter_export(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    tweets_js_path = data_dir / "tweet.js"

    tweets_data = [
        {
            "tweet": {
                "id": "123",
                "created_at": "Mon May 06 12:00:00 +0000 2024",
                "full_text": "This is a test tweet.",
                "entities": {
                    "media": [
                        {
                            "media_url_https": "https://example.com/image.jpg"
                        }
                    ]
                }
            }
        },
        {
            "tweet": {
                "id": "456",
                "created_at": "Tue May 07 12:00:00 +0000 2024",
                "full_text": "Another test tweet.",
                "entities": {}
            }
        }
    ]

    with open(tweets_js_path, "w") as f:
        f.write(f"window.YTD.tweet.part0 = {json.dumps(tweets_data)}")

    return tmp_path

def test_parse_twitter_export(sample_twitter_export):
    tweets = _parse_twitter_export(str(sample_twitter_export))

    assert len(tweets) == 2

    assert tweets[0]['tweet_id'] == "123"
    assert tweets[0]['text'] == "This is a test tweet."
    assert tweets[0]['media_urls'] == ["https://example.com/image.jpg"]

    assert tweets[1]['tweet_id'] == "456"
    assert tweets[1]['text'] == "Another test tweet."
    assert tweets[1]['media_urls'] == []

@pytest.mark.asyncio
async def test_twitter_source_fetch_items(sample_twitter_export):
    source = TwitterSource(namespace="twitter_test", data_path=str(sample_twitter_export))

    items = []
    async for item in source.fetch_items():
        items.append(item)

    assert len(items) == 2

    assert items[0].source_id == "123"
    assert items[0].content == "This is a test tweet."
    assert items[0].metadata['media_urls'] == ["https://example.com/image.jpg"]

    assert items[1].source_id == "456"
    assert items[1].content == "Another test tweet."
    assert items[1].metadata['media_urls'] == []

@pytest.mark.asyncio
async def test_twitter_source_test_connection(sample_twitter_export):
    source = TwitterSource(namespace="twitter_test", data_path=str(sample_twitter_export))
    assert await source.test_connection()

@pytest.mark.asyncio
async def test_twitter_source_test_connection_fail(tmp_path):
    source = TwitterSource(namespace="twitter_test", data_path=str(tmp_path))
    assert not await source.test_connection()
