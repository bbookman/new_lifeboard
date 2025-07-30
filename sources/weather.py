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
from core.http_client_mixin import HTTPClientMixin

logger = logging.getLogger(__name__)

class WeatherSource(BaseSource, HTTPClientMixin):
    """RapidAPI Weather source"""

    def __init__(self, config: WeatherConfig, db_service: DatabaseService):
        BaseSource.__init__(self, "weather")
        HTTPClientMixin.__init__(self)
        self.config = config
        self.db_service = db_service
        self._api_key_configured = config.is_api_key_configured()

    def _create_client_config(self) -> Dict[str, Any]:
        """Create HTTP client configuration for Weather API"""
        return {
            "base_url": f"https://{self.config.endpoint}",
            "headers": {
                "x-rapidapi-key": self.config.api_key,
                "x-rapidapi-host": self.config.endpoint
            },
            "timeout": self.config.request_timeout
        }

    def get_source_type(self) -> str:
        return "weather_api"

    async def _make_test_request(self, client: httpx.AsyncClient) -> httpx.Response:
        """Make a test request to verify Weather API connectivity"""
        params = {
            "latitude": self.config.latitude,
            "longitude": self.config.longitude,
            "units": self.config.units
        }
        return await client.get("", params=params)
    
    async def test_connection(self) -> bool:
        if not self._api_key_configured:
            logger.warning("RAPID_API_KEY is not configured for weather. Connection test skipped.")
            return False
        
        return await super().test_connection()

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 1) -> AsyncIterator[DataItem]:
        if not self._api_key_configured:
            logger.warning("RAPID_API_KEY is not configured for weather. Skipping data fetch.")
            return

        client = await self._ensure_client()
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
            yield DataItem(
                namespace=self.namespace, 
                source_id="weather_sync", 
                content="Weather data synced",
                metadata={"sync_time": data['forecastDaily'].get('readTime', '')}
            )

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
    
    def get_latest_weather(self, db_service) -> Optional[Dict[str, Any]]:
        """Get the most recent weather data"""
        with db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT response_json 
                FROM weather 
                ORDER BY days_date DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return self.parse_weather_data(json.loads(row['response_json']))
        return None

    def get_weather_by_date(self, db_service, date: str) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific date (YYYY-MM-DD format)"""
        with db_service.get_connection() as conn:
            # First try to find weather data for the exact date
            cursor = conn.execute("""
                SELECT response_json 
                FROM weather 
                WHERE days_date = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (date,))
            
            row = cursor.fetchone()
            if row:
                return self.parse_weather_data(json.loads(row['response_json']))
            
            # If no exact match, get the most recent weather data as fallback
            cursor = conn.execute("""
                SELECT response_json 
                FROM weather 
                ORDER BY days_date DESC, created_at DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                return self.parse_weather_data(json.loads(row['response_json']))
            
        return None

    def get_weather_for_specific_date(self, db_service, target_date: str) -> Optional[Dict[str, Any]]:
        """Get weather data specifically for the target date only"""
        from datetime import datetime, timedelta
        target_datetime = datetime.strptime(target_date, "%Y-%m-%d").date()
        
        # Look through all available weather data to find one that contains the target date
        with db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT response_json, days_date, created_at
                FROM weather 
                ORDER BY days_date DESC, created_at DESC
            """)
            
            for row in cursor.fetchall():
                try:
                    weather_data = self.parse_weather_data(json.loads(row['response_json']))
                    if not weather_data or 'days' not in weather_data:
                        continue
                    
                    # Check if any forecast day matches our target date
                    for day_forecast in weather_data['days']:
                        if 'forecastStart' in day_forecast:
                            try:
                                forecast_date_str = day_forecast['forecastStart']
                                forecast_date = datetime.fromisoformat(forecast_date_str.replace('Z', '+00:00'))
                                forecast_date_only = forecast_date.date()
                                
                                if forecast_date_only == target_datetime:
                                    # Found matching weather data, format for UI
                                    day_forecast['forecast_date'] = forecast_date_only.strftime("%Y-%m-%d")
                                    day_forecast['forecast_day_name'] = forecast_date_only.strftime("%A")
                                    day_forecast['forecast_month_day'] = forecast_date_only.strftime("%b %d")
                                    return day_forecast
                                    
                            except (ValueError, TypeError):
                                continue
                                
                except (json.JSONDecodeError, TypeError):
                    continue
        
        return None

    def get_weather_for_date_range(self, db_service, start_date: str, days: int = 5) -> List[Dict[str, Any]]:
        """Get weather data for a date range - only returns data for dates that actually exist in forecasts"""
        from datetime import datetime, timedelta
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d").date()
        forecast_days = []
        
        # Get weather data for each specific day in the range
        for i in range(days):
            current_date = start_datetime + timedelta(days=i)
            current_date_str = current_date.strftime("%Y-%m-%d")
            
            day_weather = self.get_weather_for_specific_date(db_service, current_date_str)
            if day_weather:
                forecast_days.append(day_weather)
        
        return forecast_days

    def _celsius_to_fahrenheit(self, temp_c: float) -> float:
        return (temp_c * 9/5) + 32

    def parse_weather_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data or 'forecastDaily' not in data:
            return {}

        parsed_data = {
            "reportedTime": data['forecastDaily'].get('reportedTime'),
            "readTime": data['forecastDaily'].get('readTime'),
            "days": []
        }

        for day_forecast in data['forecastDaily'].get('days', []):
            temp_max = day_forecast.get('temperatureMax')
            temp_min = day_forecast.get('temperatureMin')

            if self.config.units == 'standard':
                if temp_max is not None:
                    temp_max = self._celsius_to_fahrenheit(temp_max)
                if temp_min is not None:
                    temp_min = self._celsius_to_fahrenheit(temp_min)

            parsed_day = {
                "forecastStart": day_forecast.get('forecastStart'),
                "conditionCode": day_forecast.get('conditionCode'),
                "temperatureMax": temp_max,
                "temperatureMin": temp_min,
                "daytimeForecast": {
                    "conditionCode": day_forecast.get('daytimeForecast', {}).get('conditionCode')
                }
            }
            parsed_data['days'].append(parsed_day)

        return parsed_data
