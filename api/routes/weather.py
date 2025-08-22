from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from config.factory import get_config
from core.database import DatabaseService
from services.weather_service import WeatherService

router = APIRouter()

def get_db_service():
    config = get_config()
    return DatabaseService(db_path=config.database.path)

def get_weather_service(db_service: DatabaseService = Depends(get_db_service)):
    config = get_config()
    return WeatherService(db_service, config)

@router.get("/weather", response_model=Optional[Dict[str, Any]])
def get_weather(weather_service: WeatherService = Depends(get_weather_service)):
    """Get the latest 5-day weather forecast."""
    weather_data = weather_service.get_latest_weather()
    if not weather_data:
        raise HTTPException(status_code=404, detail="Weather data not found")
    return weather_data

@router.get("/weather/day/{date}", response_model=Dict[str, Any])
def get_weather_for_day(date: str, weather_service: WeatherService = Depends(get_weather_service)):
    """Get 5-day weather forecast starting from the specified date (YYYY-MM-DD format)."""
    try:
        # Validate date format
        from datetime import datetime
        datetime.strptime(date, "%Y-%m-%d")

        # Get 5 days of weather data starting from the requested date
        weather_data = weather_service.get_weather_for_date_range(date, 5)

        return {
            "date": date,
            "has_data": len(weather_data) > 0,
            "forecast_days": weather_data,
            "count": len(weather_data),
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD format.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving weather data: {e!s}")
