import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.server import app
from services.weather_service import WeatherService
from core.database import DatabaseService


@pytest.fixture
def db_service():
    return MagicMock(spec=DatabaseService)

@pytest.fixture
def weather_service(db_service):
    return WeatherService(db_service, MagicMock())

@pytest.fixture
def client(weather_service):
    app.dependency_overrides[WeatherService] = lambda: weather_service
    return TestClient(app)


def test_get_weather_success(client, weather_service):
    mock_weather_data = {
        "reportedTime": "2023-04-04T16:00:00Z",
        "readTime": "2023-04-04T17:13:14Z",
        "days": [
            {
                "forecastStart": "2023-04-04T16:00:00Z",
                "conditionCode": "HeavyRain",
                "temperatureMax": 29.5,
                "temperatureMin": 25.84,
                "daytimeForecast": {
                    "conditionCode": "HeavyRain"
                }
            }
        ]
    }
    weather_service.get_latest_weather = MagicMock(return_value=mock_weather_data)

    response = client.get("/weather")
    assert response.status_code == 200
    assert response.json() == mock_weather_data

def test_get_weather_not_found(client, weather_service):
    weather_service.get_latest_weather = MagicMock(return_value=None)

    response = client.get("/weather")
    assert response.status_code == 404
    assert response.json() == {"detail": "Weather data not found"}
