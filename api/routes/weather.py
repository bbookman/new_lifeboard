from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any

from services.weather_service import WeatherService
from core.database import DatabaseService
from config.factory import get_config

router = APIRouter()

def get_db_service():
    config = get_config()
    return DatabaseService(db_path=config.database.path)

def get_weather_service(db_service: DatabaseService = Depends(get_db_service)):
    return WeatherService(db_service)

@router.get("/weather", response_model=Optional[Dict[str, Any]])
def get_weather(weather_service: WeatherService = Depends(get_weather_service)):
    """Get the latest 5-day weather forecast."""
    weather_data = weather_service.get_latest_weather()
    if not weather_data:
        raise HTTPException(status_code=404, detail="Weather data not found")
    return weather_data
