import sys
import os
import json
from datetime import datetime
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI App
app = FastAPI(
    title="Real-time Collaborative Document Editor",
    description="Production-ready WebSocket & REST API for Document Collaboration",
    version="1.0.0"
)

# Enable CORS for Frontend (Next.js at http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Document Store
documents: Dict[str, str] = {
    "default": "# Welcome to Collaborative Editor\n\nStart typing here to collaborate in real-time!"
}

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, doc_id: str, websocket: WebSocket):
        await websocket.accept()
        if doc_id not in self.active_connections:
            self.active_connections[doc_id] = []
        self.active_connections[doc_id].append(websocket)

    def disconnect(self, doc_id: str, websocket: WebSocket):
        if doc_id in self.active_connections:
            if websocket in self.active_connections[doc_id]:
                self.active_connections[doc_id].remove(websocket)

    async def broadcast(self, doc_id: str, message: dict, sender: WebSocket = None):
        if doc_id in self.active_connections:
            for connection in self.active_connections[doc_id]:
                if connection != sender:
                    try:
                        await connection.send_json(message)
                    except Exception:
                        pass

manager = ConnectionManager()

# ─── REST ENDPOINTS ───

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Real-time Collaborative Document Editor API",
        "docs_url": "http://localhost:8000/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/documents")
def list_documents():
    return [{"id": k, "preview": v[:50]} for k, v in documents.items()]

@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    if doc_id not in documents:
        documents[doc_id] = f"# Document {doc_id}\n\nStart editing..."
    return {"id": doc_id, "content": documents[doc_id]}

@app.put("/api/documents/{doc_id}")
def update_document(doc_id: str, payload: dict):
    content = payload.get("content", "")
    documents[doc_id] = content
    return {"id": doc_id, "content": content, "status": "saved"}

# ─── WEBSOCKET ENDPOINT FOR REAL-TIME SYNC ───

@app.websocket("/ws/{doc_id}")
async def websocket_endpoint(websocket: WebSocket, doc_id: str):
    await manager.connect(doc_id, websocket)
    
    if doc_id not in documents:
        documents[doc_id] = f"# Document {doc_id}\n\nStart editing..."

    # Send current document state on connection
    await websocket.send_json({
        "type": "init",
        "doc_id": doc_id,
        "content": documents[doc_id]
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                msg = {"type": "update", "content": data}

            if msg.get("type") == "update":
                content = msg.get("content", "")
                documents[doc_id] = content
                await manager.broadcast(doc_id, {
                    "type": "update",
                    "doc_id": doc_id,
                    "content": content
                }, sender=websocket)
            else:
                await manager.broadcast(doc_id, msg, sender=websocket)

    except WebSocketDisconnect:
        manager.disconnect(doc_id, websocket)

if __name__ == "__main__":
    print("\n🚀 Starting Collaborative Editor Backend Server on http://localhost:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)