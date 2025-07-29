import httpx
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime, timezone

from .base import BaseSource, DataItem
from config.models import WeatherConfig
from core.database import DatabaseService
from core.retry_utils import RetryExecutor, create_enhanced_api_retry_condition, RetryConfig, BackoffStrategy

logger = logging.getLogger(__name__)

class WeatherSource(BaseSource):
    """RapidAPI Weather source"""

    def __init__(self, config: WeatherConfig, db_service: DatabaseService):
        super().__init__("weather")
        self.config = config
        self.db_service = db_service
        self.client = None
        self._api_key_configured = config.is_api_key_configured()

    def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=f"https://{self.config.endpoint}",
                headers={
                    "x-rapidapi-key": self.config.api_key,
                    "x-rapidapi-host": self.config.endpoint
                },
                timeout=self.config.request_timeout
            )
        return self.client

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_source_type(self) -> str:
        return "weather_api"

    async def test_connection(self) -> bool:
        if not self._api_key_configured:
            logger.warning("RAPID_API_KEY is not configured for weather. Connection test skipped.")
            return False
        try:
            client = self._get_client()
            params = {
                "latitude": self.config.latitude,
                "longitude": self.config.longitude,
                "units": self.config.units
            }
            response = await client.get("", params=params)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Weather API connection test failed: {e}")
            return False

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 1) -> AsyncIterator[DataItem]:
        if not self._api_key_configured:
            logger.warning("RAPID_API_KEY is not configured for weather. Skipping data fetch.")
            return

        client = self._get_client()
        params = {
            "latitude": self.config.latitude,
            "longitude": self.config.longitude,
            "units": self.config.units
        }

        logger.info(f"Fetching weather data from API")

        response = await self._make_request_with_retry(client, "", params)

        if not response:
            logger.error("Failed to fetch weather data from API")
            return

        try:
            data = response.json()
            await self._store_weather_data(data)
            # This source does not yield DataItems directly, it stores in its own table.
            # We will yield a single dummy item to satisfy the sync manager.
            yield DataItem(namespace=self.namespace, source_id="weather_sync", content="Weather data synced")

        except Exception as e:
            logger.error(f"Error processing weather response: {e}")

    async def _store_weather_data(self, data: Dict[str, Any]):
        if not data or 'forecastDaily' not in data:
            logger.warning("Weather data is missing 'forecastDaily'")
            return

        days_date = data['forecastDaily'].get('readTime')
        if not days_date:
            logger.warning("Weather data is missing 'readTime'")
            return

        with self.db_service.get_connection() as conn:
            conn.execute("""
                INSERT INTO weather (days_date, response_json)
                VALUES (?, ?)
            """, (days_date, json.dumps(data)))
            conn.commit()

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        logger.warning("Individual item fetching not supported by WeatherSource")
        return None

    async def _make_request_with_retry(
        self, 
        client: httpx.AsyncClient, 
        endpoint: str, 
        params: Dict[str, Any]
    ) -> Optional[httpx.Response]:
        retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_delay,
            max_delay=60.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            rate_limit_base_delay=30.0,
            rate_limit_max_delay=self.config.rate_limit_max_delay,
            respect_retry_after=self.config.respect_retry_after,
            jitter=True
        )
        retry_condition = create_enhanced_api_retry_condition()
        retry_executor = RetryExecutor(retry_config, retry_condition)

        async def make_request():
            response = await client.get(endpoint, params=params)
            if response.status_code == 200:
                return response
            elif response.status_code in [429, 500, 502, 503, 504]:
                response.raise_for_status()
            else:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return None

        try:
            result = await retry_executor.execute_async(make_request)
            return result.result if result.success else None
        except Exception as e:
            logger.error(f"Request failed after all retries: {e}")
            return None

    async def get_sync_metadata(self) -> Dict[str, Any]:
        return {
            "source_type": self.get_source_type(),
            "namespace": self.namespace,
            "api_endpoint": self.config.endpoint,
            "latitude": self.config.latitude,
            "longitude": self.config.longitude,
            "units": self.config.units,
            "last_sync": datetime.now(timezone.utc).isoformat()
        }
