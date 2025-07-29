import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from core.database import DatabaseService

class WeatherService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weather data"""
        with self.db_service.get_connection() as conn:
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

    def get_weather_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific date (YYYY-MM-DD format)"""
        with self.db_service.get_connection() as conn:
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
            # (weather forecasts are typically valid for several days)
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

    def get_weather_for_specific_date(self, target_date: str) -> Optional[Dict[str, Any]]:
        """Get weather data specifically for the target date only"""
        target_datetime = datetime.strptime(target_date, "%Y-%m-%d").date()
        
        # Look through all available weather data to find one that contains the target date
        with self.db_service.get_connection() as conn:
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

    def get_weather_for_date_range(self, start_date: str, days: int = 5) -> List[Dict[str, Any]]:
        """Get weather data for a date range - only returns data for dates that actually exist in forecasts"""
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d").date()
        forecast_days = []
        
        # Get weather data for each specific day in the range
        for i in range(days):
            current_date = start_datetime + timedelta(days=i)
            current_date_str = current_date.strftime("%Y-%m-%d")
            
            day_weather = self.get_weather_for_specific_date(current_date_str)
            if day_weather:
                forecast_days.append(day_weather)
        
        return forecast_days

    def parse_weather_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data or 'forecastDaily' not in data:
            return {}

        parsed_data = {
            "reportedTime": data['forecastDaily'].get('reportedTime'),
            "readTime": data['forecastDaily'].get('readTime'),
            "days": []
        }

        for day_forecast in data['forecastDaily'].get('days', []):
            parsed_day = {
                "forecastStart": day_forecast.get('forecastStart'),
                "conditionCode": day_forecast.get('conditionCode'),
                "temperatureMax": day_forecast.get('temperatureMax'),
                "temperatureMin": day_forecast.get('temperatureMin'),
                "daytimeForecast": {
                    "conditionCode": day_forecast.get('daytimeForecast', {}).get('conditionCode')
                }
            }
            parsed_data['days'].append(parsed_day)

        return parsed_data
