# Lifeboard Project Overview

## Purpose
Lifeboard is an interactive reflection space and AI-powered planning assistant that transforms daily digital history into a personal newspaper. It seamlessly pulls from digital history (conversations, activities, moods, experiences) to create meaning from everyday life while providing AI assistance for future planning.

## Core Features
- Interactive reflection space with infinite discovery opportunities
- AI assistant for natural conversation and planning
- Digital history integration (conversations, activities, moods, experiences)
- Random resurfacing of forgotten moments and AI-guided discovery journeys
- Personal assistant functionality (to-dos, meeting insights, medical appointments)

## Architecture Pattern
**KISS multi-source memory chat application** with unified data flow:
- All sources → DataItem objects → processor pipeline → data_items table → embeddings → FAISS
- Search: embed query → search FAISS → retrieve vector IDs → fetch data_items → pass to LLM
- Updates: update data_items row → re-embed → update FAISS vector

## Tech Stack
- **Backend**: Python 3.9+, FastAPI, SQLite, FAISS, sentence-transformers
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui components
- **LLM Integration**: OpenAI, Anthropic
- **Data Sources**: Limitless API, News API, Weather API, Twitter API
- **Testing**: pytest (Python), vitest (Frontend)
- **Development**: uvicorn (Python), Vite dev server (Frontend)

## External Integrations
- **Limitless API**: Primary lifelog data source
- **RapidAPI News**: Real-time news headlines
- **RapidAPI Weather**: 5-day weather forecasts  
- **Twitter API**: Tweet history and social data

## Key Directories
- `/api`: FastAPI server and route definitions
- `/services`: Core business logic services
- `/sources`: Data source implementations
- `/core`: Database, embeddings, utilities
- `/config`: Pydantic configuration models
- `/frontend`: React/TypeScript frontend
- `/tests`: Test suites (pytest configuration)