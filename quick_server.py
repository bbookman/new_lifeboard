#!/usr/bin/env python3
"""
Quick server startup without heavy initialization
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Create minimal FastAPI app
app = FastAPI(title="Lifeboard Quick Server")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health endpoint
@app.get("/health")
async def health():
    return {"healthy": True, "message": "Quick server running"}

# Calendar endpoint for frontend
@app.get("/calendar/api/data_items/{date}")
async def get_calendar_data(date: str, namespaces: str = None):
    return {
        "data": [],
        "date": date, 
        "namespaces": namespaces,
        "message": "Quick server - limited functionality"
    }

# WebSocket stats endpoint
@app.get("/ws/stats")
async def websocket_stats():
    return {
        "is_running": False,
        "total_connections": 0,
        "message": "WebSocket not available in quick server"
    }

if __name__ == "__main__":
    print("🚀 Starting quick server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)