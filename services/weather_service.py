import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.database import DatabaseService

class WeatherService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
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
