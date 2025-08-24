import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from core.database import DatabaseService
from config.models import AppConfig
from services.debug_mixin import ServiceDebugMixin
from core.database_debug import DebugDatabaseConnection

class WeatherService(ServiceDebugMixin):
    def __init__(self, db_service: DatabaseService, config: AppConfig):
        super().__init__("weather_service")
        self.db_service = db_service
        self.config = config
        
        # Set up database debug monitoring if path is available
        if hasattr(db_service, 'db_path'):
            self.debug_db = DebugDatabaseConnection(db_service.db_path)
        else:
            self.debug_db = None
        
        self.log_service_call("__init__", {
            "has_db_service": db_service is not None,
            "weather_units": config.weather.units if config.weather else "default",
            "debug_db_available": self.debug_db is not None
        })

    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weather data"""
        self.log_service_call("get_latest_weather")
        
        db_start = time.time()
        try:
            connection_context = self.debug_db.get_connection() if self.debug_db else self.db_service.get_connection()
            
            with connection_context as conn:
                cursor = conn.execute("""
                    SELECT response_json 
                    FROM weather 
                    ORDER BY days_date DESC 
                    LIMIT 1
                """)
                row = cursor.fetchone()
                
                db_duration = (time.time() - db_start) * 1000
                self.log_database_operation("SELECT", "weather", db_duration)
                
                if row:
                    parse_start = time.time()
                    parsed_data = self.parse_weather_data(json.loads(row['response_json']))
                    parse_duration = (time.time() - parse_start) * 1000
                    
                    self.log_service_performance_metric("weather_parse_duration", parse_duration, "ms")
                    self.log_service_performance_metric("weather_data_found", 1, "count")
                    
                    return parsed_data
                else:
                    self.log_service_performance_metric("weather_data_found", 0, "count")
                    return None
                    
        except Exception as e:
            self.log_service_error("get_latest_weather", e, {})
            raise

    def get_weather_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific date (YYYY-MM-DD format)"""
        self.log_service_call("get_weather_by_date", {"date": date})
        
        db_start = time.time()
        try:
            connection_context = self.debug_db.get_connection() if self.debug_db else self.db_service.get_connection()
            
            with connection_context as conn:
                # First try to find weather data for the exact date
                cursor = conn.execute("""
                    SELECT response_json 
                    FROM weather 
                    WHERE days_date = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (date,))
                
                row = cursor.fetchone()
                exact_match_duration = (time.time() - db_start) * 1000
                self.log_database_operation("SELECT", "weather", exact_match_duration)
                
                if row:
                    parse_start = time.time()
                    parsed_data = self.parse_weather_data(json.loads(row['response_json']))
                    parse_duration = (time.time() - parse_start) * 1000
                    
                    self.log_service_performance_metric("weather_parse_duration", parse_duration, "ms")
                    self.log_service_performance_metric("weather_exact_match", 1, "count")
                    
                    return parsed_data
                
                # If no exact match, get the most recent weather data as fallback
                fallback_start = time.time()
                cursor = conn.execute("""
                    SELECT response_json 
                    FROM weather 
                    ORDER BY days_date DESC, created_at DESC
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                fallback_duration = (time.time() - fallback_start) * 1000
                self.log_database_operation("SELECT", "weather", fallback_duration)
                
                if row:
                    parse_start = time.time()
                    parsed_data = self.parse_weather_data(json.loads(row['response_json']))
                    parse_duration = (time.time() - parse_start) * 1000
                    
                    self.log_service_performance_metric("weather_parse_duration", parse_duration, "ms")
                    self.log_service_performance_metric("weather_fallback_used", 1, "count")
                    
                    return parsed_data
                else:
                    self.log_service_performance_metric("weather_data_not_found", 1, "count")
                    return None
                    
        except Exception as e:
            self.log_service_error("get_weather_by_date", e, {"date": date})
            raise

    def get_weather_for_specific_date(self, target_date: str) -> Optional[Dict[str, Any]]:
        """Get weather data specifically for the target date only"""
        self.log_service_call("get_weather_for_specific_date", {"target_date": target_date})
        
        try:
            target_datetime = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError as e:
            self.log_service_error("get_weather_for_specific_date", e, {"target_date": target_date})
            raise
        
        db_start = time.time()
        rows_processed = 0
        forecast_days_checked = 0
        
        try:
            connection_context = self.debug_db.get_connection() if self.debug_db else self.db_service.get_connection()
            
            with connection_context as conn:
                cursor = conn.execute("""
                    SELECT response_json, days_date, created_at
                    FROM weather 
                    ORDER BY days_date DESC, created_at DESC
                """)
                
                db_duration = (time.time() - db_start) * 1000
                self.log_database_operation("SELECT", "weather", db_duration)
                
                processing_start = time.time()
                
                for row in cursor.fetchall():
                    rows_processed += 1
                    
                    try:
                        weather_data = self.parse_weather_data(json.loads(row['response_json']))
                        if not weather_data or 'days' not in weather_data:
                            continue
                        
                        # Check if any forecast day matches our target date
                        for day_forecast in weather_data['days']:
                            forecast_days_checked += 1
                            
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
                                        
                                        processing_duration = (time.time() - processing_start) * 1000
                                        
                                        self.log_service_performance_metric("weather_rows_processed", rows_processed, "count")
                                        self.log_service_performance_metric("weather_forecast_days_checked", forecast_days_checked, "count")
                                        self.log_service_performance_metric("weather_processing_duration", processing_duration, "ms")
                                        self.log_service_performance_metric("weather_specific_date_found", 1, "count")
                                        
                                        return day_forecast
                                        
                                except (ValueError, TypeError):
                                    continue
                                    
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            processing_duration = (time.time() - processing_start) * 1000
            
            self.log_service_performance_metric("weather_rows_processed", rows_processed, "count")
            self.log_service_performance_metric("weather_forecast_days_checked", forecast_days_checked, "count")
            self.log_service_performance_metric("weather_processing_duration", processing_duration, "ms")
            self.log_service_performance_metric("weather_specific_date_found", 0, "count")
            
            return None
            
        except Exception as e:
            self.log_service_error("get_weather_for_specific_date", e, {"target_date": target_date})
            raise

    def get_weather_for_date_range(self, start_date: str, days: int = 5) -> List[Dict[str, Any]]:
        """Get weather data for a date range - only returns data for dates that actually exist in forecasts"""
        self.log_service_call("get_weather_for_date_range", {
            "start_date": start_date,
            "days_requested": days
        })
        
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError as e:
            self.log_service_error("get_weather_for_date_range", e, {
                "start_date": start_date,
                "days_requested": days
            })
            raise
        
        range_start = time.time()
        forecast_days = []
        dates_found = 0
        dates_not_found = 0
        
        try:
            # Get weather data for each specific day in the range
            for i in range(days):
                current_date = start_datetime + timedelta(days=i)
                current_date_str = current_date.strftime("%Y-%m-%d")
                
                day_weather = self.get_weather_for_specific_date(current_date_str)
                if day_weather:
                    forecast_days.append(day_weather)
                    dates_found += 1
                else:
                    dates_not_found += 1
            
            range_duration = (time.time() - range_start) * 1000
            
            self.log_service_performance_metric("weather_range_duration", range_duration, "ms")
            self.log_service_performance_metric("weather_dates_found", dates_found, "count")
            self.log_service_performance_metric("weather_dates_not_found", dates_not_found, "count")
            self.log_service_performance_metric("weather_range_success_rate", 
                                               (dates_found / days * 100) if days > 0 else 0, "percent")
            
            return forecast_days
            
        except Exception as e:
            self.log_service_error("get_weather_for_date_range", e, {
                "start_date": start_date,
                "days_requested": days,
                "dates_processed": len(forecast_days)
            })
            raise

    def _celsius_to_fahrenheit(self, temp_c: float) -> float:
        return (temp_c * 9/5) + 32

    def parse_weather_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data or 'forecastDaily' not in data:
            self.log_service_performance_metric("weather_parse_invalid_data", 1, "count")
            return {}

        parse_start = time.time()
        forecast_days_parsed = 0
        temperature_conversions = 0

        try:
            parsed_data = {
                "reportedTime": data['forecastDaily'].get('reportedTime'),
                "readTime": data['forecastDaily'].get('readTime'),
                "days": []
            }

            for day_forecast in data['forecastDaily'].get('days', []):
                forecast_days_parsed += 1
                
                temp_max = day_forecast.get('temperatureMax')
                temp_min = day_forecast.get('temperatureMin')

                if self.config.weather.units == 'standard':
                    if temp_max is not None:
                        temp_max = self._celsius_to_fahrenheit(temp_max)
                        temperature_conversions += 1
                    if temp_min is not None:
                        temp_min = self._celsius_to_fahrenheit(temp_min)
                        temperature_conversions += 1

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

            parse_duration = (time.time() - parse_start) * 1000
            
            self.log_service_performance_metric("weather_parse_days_processed", forecast_days_parsed, "count")
            self.log_service_performance_metric("weather_temperature_conversions", temperature_conversions, "count")
            self.log_service_performance_metric("weather_parse_success", 1, "count")

            return parsed_data
            
        except Exception as e:
            self.log_service_error("parse_weather_data", e, {
                "data_keys": list(data.keys()) if data else [],
                "days_processed": forecast_days_parsed
            })
            raise
