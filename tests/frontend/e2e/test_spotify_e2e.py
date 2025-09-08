"""
End-to-End tests for Spotify integration.

This module tests the complete Spotify integration flow from backend sync
to frontend display, including date selection, player functionality, and
error scenarios.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

import httpx
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright.async_api import expect

# Test configuration
TEST_BASE_URL = "http://localhost:3000"  # React frontend
API_BASE_URL = "http://localhost:8000"   # FastAPI backend
TEST_TIMEOUT = 30000  # 30 seconds


class SpotifyE2ETestHelper:
    """Helper class for Spotify E2E test utilities."""
    
    @staticmethod
    def create_mock_spotify_track(
        track_id: str = "test_track_123",
        title: str = "Test Song",
        artist: str = "Test Artist",
        album: str = "Test Album",
        duration_ms: int = 180000,
        played_at: Optional[str] = None,
        preview_url: Optional[str] = "https://p.scdn.co/mp3-preview/test",
        audio_features: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Create a mock Spotify track for testing."""
        if played_at is None:
            played_at = datetime.now().isoformat()
        
        if audio_features is None:
            audio_features = {
                "valence": 0.8,
                "energy": 0.7,
                "danceability": 0.6
            }
        
        return {
            "id": track_id,
            "title": title,
            "artist": artist,
            "album": album,
            "duration_ms": duration_ms,
            "played_at": played_at,
            "preview_url": preview_url,
            "external_urls": {
                "spotify": f"https://open.spotify.com/track/{track_id}"
            },
            "audio_features": audio_features
        }
    
    @staticmethod
    def create_mock_spotify_response(tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a mock Spotify API response."""
        return {
            "items": tracks,
            "total": len(tracks),
            "limit": 50,
            "offset": 0
        }


@pytest.fixture(scope="session")
async def browser():
    """Create a browser instance for the test session."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # Set to False for debugging
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        yield browser
        await browser.close()


@pytest.fixture
async def context(browser: Browser):
    """Create a browser context for each test."""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    yield context
    await context.close()


@pytest.fixture
async def page(context: BrowserContext):
    """Create a page for each test."""
    page = await context.new_page()
    
    # Set up console logging for debugging
    page.on("console", lambda msg: print(f"Console: {msg.text}"))
    page.on("pageerror", lambda error: print(f"Page error: {error}"))
    
    yield page
    await page.close()


@pytest.fixture
def mock_spotify_data():
    """Create mock Spotify data for testing."""
    helper = SpotifyE2ETestHelper()
    
    # Create tracks for different dates
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    return {
        today: [
            helper.create_mock_spotify_track(
                track_id="track_1",
                title="Happy Song",
                artist="Upbeat Artist",
                album="Feel Good Album",
                audio_features={"valence": 0.9, "energy": 0.8, "danceability": 0.7}
            ),
            helper.create_mock_spotify_track(
                track_id="track_2",
                title="Chill Vibes",
                artist="Relaxed Artist",
                album="Peaceful Album",
                audio_features={"valence": 0.3, "energy": 0.2, "danceability": 0.4}
            )
        ],
        yesterday: [
            helper.create_mock_spotify_track(
                track_id="track_3",
                title="Yesterday's Hit",
                artist="Past Artist",
                album="Memory Lane",
                played_at=(datetime.now() - timedelta(days=1)).isoformat()
            )
        ]
    }


@pytest.fixture
async def mock_api_responses(mock_spotify_data):
    """Mock API responses for testing."""
    async def mock_spotify_tracks_endpoint(request):
        """Mock the /spotify/tracks endpoint."""
        url = str(request.url)
        
        # Extract date parameter
        if "date=" in url:
            date = url.split("date=")[1].split("&")[0]
        else:
            date = datetime.now().strftime("%Y-%m-%d")
        
        tracks = mock_spotify_data.get(date, [])
        
        return httpx.Response(
            status_code=200,
            json=tracks,
            headers={"content-type": "application/json"}
        )
    
    # Patch the API client
    with patch("httpx.AsyncClient.get", side_effect=mock_spotify_tracks_endpoint):
        yield


class TestSpotifyE2EIntegration:
    """Test complete Spotify integration end-to-end."""
    
    async def test_spotify_data_flow_backend_to_frontend(
        self, 
        page: Page, 
        mock_api_responses,
        mock_spotify_data
    ):
        """Test complete data flow from backend sync to frontend display."""
        # Navigate to the application
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for the Music Journal section to load
        music_section = page.locator('[data-testid="music-history"]').or_(
            page.get_by_text("Music Journal")
        )
        await expect(music_section).to_be_visible(timeout=TEST_TIMEOUT)
        
        # Check that Spotify tracks are displayed
        today = datetime.now().strftime("%Y-%m-%d")
        expected_tracks = mock_spotify_data[today]
        
        for track in expected_tracks:
            # Check track title is displayed
            track_element = page.get_by_text(track["title"])
            await expect(track_element).to_be_visible()
            
            # Check artist name is displayed
            artist_element = page.get_by_text(track["artist"])
            await expect(artist_element).to_be_visible()
            
            # Check album name is displayed
            album_element = page.get_by_text(track["album"])
            await expect(album_element).to_be_visible()
    
    async def test_date_selection_updates_spotify_tracks(
        self, 
        page: Page, 
        mock_api_responses,
        mock_spotify_data
    ):
        """Test that changing dates updates the displayed Spotify tracks."""
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for initial load
        await expect(page.get_by_text("Music Journal")).to_be_visible()
        
        # Check today's tracks are initially displayed
        today_track = mock_spotify_data[datetime.now().strftime("%Y-%m-%d")][0]
        await expect(page.get_by_text(today_track["title"])).to_be_visible()
        
        # Find and click date picker (assuming there's a date input or picker)
        date_picker = page.locator('input[type="date"]').or_(
            page.locator('[data-testid="date-picker"]')
        ).first()
        
        if await date_picker.count() > 0:
            # Set date to yesterday
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            await date_picker.fill(yesterday)
            await date_picker.press("Enter")
            
            # Wait for the tracks to update
            await page.wait_for_timeout(1000)
            
            # Check that yesterday's tracks are now displayed
            yesterday_track = mock_spotify_data[yesterday][0]
            await expect(page.get_by_text(yesterday_track["title"])).to_be_visible()
            
            # Check that today's tracks are no longer displayed
            await expect(page.get_by_text(today_track["title"])).not_to_be_visible()
    
    async def test_spotify_player_preview_mode(
        self, 
        page: Page, 
        mock_api_responses,
        mock_spotify_data
    ):
        """Test Spotify player functionality in preview mode."""
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for tracks to load
        await expect(page.get_by_text("Music Journal")).to_be_visible()
        
        # Find the first Spotify player component
        player = page.locator('[data-testid="spotify-player"]').or_(
            page.locator('.spotify-player')
        ).first()
        
        if await player.count() > 0:
            await expect(player).to_be_visible()
            
            # Look for play button
            play_button = player.locator('button').filter(has_text="▶️").or_(
                player.get_by_role("button", name="Play preview")
            )
            
            if await play_button.count() > 0:
                # Test play functionality
                await play_button.click()
                
                # Check if pause button appears (indicating playback started)
                pause_button = player.locator('button').filter(has_text="⏸️").or_(
                    player.get_by_role("button", name="Pause preview")
                )
                
                # Wait a moment for state change
                await page.wait_for_timeout(500)
                
                # Test pause functionality
                if await pause_button.count() > 0:
                    await pause_button.click()
                    
                    # Verify play button is back
                    await expect(play_button).to_be_visible()
    
    async def test_spotify_player_keyboard_accessibility(
        self, 
        page: Page, 
        mock_api_responses
    ):
        """Test keyboard accessibility of Spotify player controls."""
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for player to load
        player = page.locator('.spotify-player').first()
        
        if await player.count() > 0:
            # Focus on the player
            await player.focus()
            
            # Test keyboard navigation
            play_button = player.get_by_role("button", name="Play preview").or_(
                player.locator('button').filter(has_text="▶️")
            ).first()
            
            if await play_button.count() > 0:
                await play_button.focus()
                
                # Test Enter key activation
                await play_button.press("Enter")
                await page.wait_for_timeout(500)
                
                # Test Space key activation
                pause_button = player.get_by_role("button", name="Pause preview").or_(
                    player.locator('button').filter(has_text="⏸️")
                ).first()
                
                if await pause_button.count() > 0:
                    await pause_button.press(" ")
                    await page.wait_for_timeout(500)
    
    async def test_spotify_error_scenarios(
        self, 
        page: Page
    ):
        """Test error handling and recovery scenarios."""
        # Mock API error responses
        async def mock_error_response(request):
            return httpx.Response(
                status_code=500,
                json={"detail": "Internal server error"},
                headers={"content-type": "application/json"}
            )
        
        with patch("httpx.AsyncClient.get", side_effect=mock_error_response):
            await page.goto(TEST_BASE_URL)
            await page.wait_for_load_state("networkidle")
            
            # Check for error message display
            error_message = page.get_by_text("Failed to load music history").or_(
                page.get_by_text("⚠️")
            )
            
            # Wait for error state to appear
            await expect(error_message).to_be_visible(timeout=TEST_TIMEOUT)
    
    async def test_spotify_empty_state(
        self, 
        page: Page
    ):
        """Test empty state when no Spotify tracks are available."""
        # Mock empty response
        async def mock_empty_response(request):
            return httpx.Response(
                status_code=200,
                json=[],
                headers={"content-type": "application/json"}
            )
        
        with patch("httpx.AsyncClient.get", side_effect=mock_empty_response):
            await page.goto(TEST_BASE_URL)
            await page.wait_for_load_state("networkidle")
            
            # Check for empty state message
            empty_message = page.get_by_text("No music history found").or_(
                page.get_by_text("🎵")
            )
            
            await expect(empty_message).to_be_visible(timeout=TEST_TIMEOUT)
    
    async def test_spotify_loading_states(
        self, 
        page: Page
    ):
        """Test loading states during data fetching."""
        # Mock slow response
        async def mock_slow_response(request):
            await asyncio.sleep(2)  # Simulate slow API
            return httpx.Response(
                status_code=200,
                json=[],
                headers={"content-type": "application/json"}
            )
        
        with patch("httpx.AsyncClient.get", side_effect=mock_slow_response):
            await page.goto(TEST_BASE_URL)
            
            # Check for loading indicator
            loading_indicator = page.get_by_text("Loading your music history").or_(
                page.locator('.animate-spin')
            )
            
            await expect(loading_indicator).to_be_visible()
            
            # Wait for loading to complete
            await page.wait_for_load_state("networkidle", timeout=TEST_TIMEOUT)
    
    async def test_spotify_track_metadata_display(
        self, 
        page: Page, 
        mock_api_responses,
        mock_spotify_data
    ):
        """Test that all track metadata is properly displayed."""
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for tracks to load
        await expect(page.get_by_text("Music Journal")).to_be_visible()
        
        today = datetime.now().strftime("%Y-%m-%d")
        track = mock_spotify_data[today][0]
        
        # Check track title
        await expect(page.get_by_text(track["title"])).to_be_visible()
        
        # Check artist name
        await expect(page.get_by_text(track["artist"])).to_be_visible()
        
        # Check album name
        await expect(page.get_by_text(track["album"])).to_be_visible()
        
        # Check duration format (MM:SS)
        duration_minutes = track["duration_ms"] // 60000
        duration_seconds = (track["duration_ms"] % 60000) // 1000
        duration_text = f"{duration_minutes}:{duration_seconds:02d}"
        await expect(page.get_by_text(duration_text)).to_be_visible()
        
        # Check mood badge (derived from audio features)
        mood_badge = page.locator('.badge').or_(
            page.locator('[class*="bg-"]').filter(has_text="Energetic")
        )
        await expect(mood_badge.first()).to_be_visible()
    
    async def test_spotify_stats_calculation(
        self, 
        page: Page, 
        mock_api_responses,
        mock_spotify_data
    ):
        """Test that listening stats are correctly calculated and displayed."""
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for stats to load
        stats_section = page.get_by_text("Today's Listening Stats").or_(
            page.get_by_text("Listening Stats")
        )
        await expect(stats_section).to_be_visible()
        
        today = datetime.now().strftime("%Y-%m-%d")
        tracks = mock_spotify_data[today]
        
        # Calculate expected stats
        track_count = len(tracks)
        total_duration_ms = sum(track["duration_ms"] for track in tracks)
        total_minutes = total_duration_ms // 60000
        
        # Check track count
        await expect(page.get_by_text(f"{track_count} track")).to_be_visible()
        
        # Check total duration
        await expect(page.get_by_text(f"{total_minutes} minutes")).to_be_visible()
        
        # Check dominant mood
        await expect(page.get_by_text("vibes")).to_be_visible()


class TestSpotifyOAuthFlow:
    """Test OAuth authentication flow (if implemented)."""
    
    async def test_oauth_redirect_flow(self, page: Page):
        """Test OAuth redirect flow for Spotify authentication."""
        # This test would be implemented if OAuth flow is added
        # For now, we'll skip it
        pytest.skip("OAuth flow not yet implemented")
    
    async def test_oauth_token_refresh(self, page: Page):
        """Test OAuth token refresh functionality."""
        # This test would be implemented if OAuth flow is added
        pytest.skip("OAuth token refresh not yet implemented")


class TestSpotifyPerformance:
    """Test performance aspects of Spotify integration."""
    
    async def test_spotify_data_loading_performance(
        self, 
        page: Page, 
        mock_api_responses
    ):
        """Test that Spotify data loads within acceptable time limits."""
        start_time = time.time()
        
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for music section to be visible
        await expect(page.get_by_text("Music Journal")).to_be_visible()
        
        end_time = time.time()
        load_time = end_time - start_time
        
        # Assert that loading takes less than 5 seconds
        assert load_time < 5.0, f"Page loaded too slowly: {load_time:.2f}s"
    
    async def test_spotify_player_responsiveness(
        self, 
        page: Page, 
        mock_api_responses
    ):
        """Test that player controls respond quickly to user interactions."""
        await page.goto(TEST_BASE_URL)
        await page.wait_for_load_state("networkidle")
        
        player = page.locator('.spotify-player').first()
        
        if await player.count() > 0:
            play_button = player.locator('button').filter(has_text="▶️").first()
            
            if await play_button.count() > 0:
                start_time = time.time()
                await play_button.click()
                
                # Wait for state change
                pause_button = player.locator('button').filter(has_text="⏸️")
                await expect(pause_button).to_be_visible(timeout=2000)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # Assert that player responds within 1 second
                assert response_time < 1.0, f"Player responded too slowly: {response_time:.2f}s"


# Test configuration and utilities
@pytest.mark.e2e
class TestSpotifyE2EConfiguration:
    """Test configuration and setup for E2E tests."""
    
    def test_test_environment_setup(self):
        """Verify that test environment is properly configured."""
        # Check that required URLs are accessible
        assert TEST_BASE_URL, "Frontend URL not configured"
        assert API_BASE_URL, "Backend API URL not configured"
    
    async def test_frontend_backend_connectivity(self):
        """Test that frontend can communicate with backend."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{API_BASE_URL}/health")
                assert response.status_code == 200
            except httpx.RequestError:
                pytest.skip("Backend not available for E2E testing")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest for E2E tests."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add E2E marker."""
    for item in items:
        if "e2e" in item.nodeid:
            item.add_marker(pytest.mark.e2e)


# Test data fixtures
@pytest.fixture(scope="session")
def test_data():
    """Provide test data for E2E tests."""
    return {
        "spotify_client_id": "test_client_id",
        "spotify_client_secret": "test_client_secret",
        "test_user_token": "test_access_token",
        "test_refresh_token": "test_refresh_token"
    }


if __name__ == "__main__":
    # Run E2E tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "e2e"
    ])