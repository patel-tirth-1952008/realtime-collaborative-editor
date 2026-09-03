# Real-time Collaborative Document Editor

## Overview
A production-grade, Google Docs-style collaborative editor. This project demonstrates real-time synchronization using WebSockets, conflict resolution via Operational Transformation (OT) or CRDTs, and robust state management. It is designed to handle high-concurrency editing sessions with low latency.

## Tech Stack
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python 3.11), WebSockets
- **Database**: PostgreSQL 15 (Primary data), Redis 7 (Session cache & Pub/Sub)
- **Infrastructure**: Docker, Docker Compose

## Architecture
- **Next.js**: Handles SSR/CSR for the editor UI and initial document load.
- **FastAPI**: Manages WebSocket connections, document CRUD, and user authentication.
- **Redis**: Acts as a message broker for real-time updates and stores ephemeral session state.
- **PostgreSQL**: Persists document versions, user data, and final document state.

## Quick Start

### Prerequisites
- Docker
- Docker Compose

### Setup
1. Clone the repository.
2. Create a `.env` file in the root directory:
   ```env
   POSTGRES_USER=editor_user
   POSTGRES_PASSWORD=secure_password
   POSTGRES_DB=editor_db
   REDIS_URL=redis://redis:6379
   SECRET_KEY=your_secret_key_here
   ```
3. Start the services:
   ```bash
   docker-compose up --build
   ```

### Access
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs
- **WebSocket Endpoint**: ws://localhost:8000/ws/{document_id}

## Project Structure