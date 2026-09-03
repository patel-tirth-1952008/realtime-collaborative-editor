from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime
from typing import Dict, List, Optional
import uuid

from .models import Document, User, DocumentVersion
from .schemas import DocumentCreate, DocumentUpdate, DocumentResponse, UserCreate, UserResponse, Token
from .auth import create_access_token, get_current_user
from .database import Base, engine

# Initialize Redis
redis_client = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, document_id: str):
        await websocket.accept()
        if document_id not in self.active_connections:
            self.active_connections[document_id] = []
        self.active_connections[document_id].append(websocket)

    def disconnect(self, websocket: WebSocket, document_id: str):
        if document_id in self.active_connections:
            self.active_connections[document_id].remove(websocket)
            if not self.active_connections[document_id]:
                del self.active_connections[document_id]

    async def broadcast(self, message: dict, document_id: str):
        if document_id in self.active_connections:
            for connection in self.active_connections[document_id]:
                await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Close redis connection
    await redis_client.close()

app = FastAPI(title='Real-time Collaborative Document Editor', lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get async session
async def get_db():
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

# --- REST API Endpoints ---

@app.get('/')
def root():
    return {'message': 'Welcome to Real-time Collaborative Document Editor API'}

@app.post('/auth/register', response_model=UserResponse)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(email=user.email, password=user.password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@app.post('/auth/login', response_model=Token)
async def login(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    db_user = result.scalar_one_or_none()
    if not db_user or db_user.password != user.password:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post('/documents', response_model=DocumentResponse)
async def create_document(doc: DocumentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_doc = Document(
        title=doc.title,
        content=doc.content,
        owner_id=current_user.id,
        version=1
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    # Create initial version
    version = DocumentVersion(
        document_id=new_doc.id,
        content=new_doc.content,
        version=1
    )
    db.add(version)
    await db.commit()
    
    return new_doc

@app.get('/documents/{document_id}', response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.put('/documents/{document_id}', response_model=DocumentResponse)
async def update_document(document_id: str, doc: DocumentUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this document")
    
    document.title = doc.title
    document.content = doc.content
    document.version += 1
    document.updated_at = datetime.utcnow()
    
    # Save version
    version = DocumentVersion(
        document_id=document.id,
        content=document.content,
        version=document.version
    )
    db.add(version)
    await db.commit()
    await db.refresh(document)
    
    # Broadcast update to WebSocket clients
    await manager.broadcast({
        "type": "document_update",
        "document_id": document.id,
        "content": document.content,
        "version": document.version
    }, document.id)
    
    return document

@app.get('/documents/{document_id}/versions')
async def get_document_versions(document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(DocumentVersion).where(DocumentVersion.document_id == document_id).order_by(DocumentVersion.version.desc()))
    versions = result.scalars().all()
    return versions

# --- WebSocket Endpoints ---

@app.websocket('/ws/documents/{document_id}')
async def websocket_endpoint(websocket: WebSocket, document_id: str):
    # In a real app, you'd verify the token here
    await manager.connect(websocket, document_id)
    try:
        # Send initial document state
        async with engine.begin() as conn:
            result = await conn.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
        
        if document:
            await websocket.send_text(json.dumps({
                "type": "initial_state",
                "document_id": document_id,
                "content": document.content,
                "version": document.version
            }))
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "cursor_update":
                # Broadcast cursor position to other users
                await manager.broadcast({
                    "type": "cursor_update",
                    "document_id": document_id,
                    "user_id": message.get("user_id"),
                    "position": message.get("position")
                }, document_id)
                
            elif message.get("type") == "content_update":
                # Handle real-time content updates (simplified)
                # In a production app, you'd use CRDTs or OT for conflict resolution
                new_content = message.get("content")
                async with engine.begin() as conn:
                    result = await conn.execute(select(Document).where(Document.id == document_id))
                    document = result.scalar_one_or_none()
                    if document:
                        document.content = new_content
                        document.version += 1
                        await conn.commit()
                        
                await manager.broadcast({
                    "type": "document_update",
                    "document_id": document_id,
                    "content": new_content,
                    "version": document.version
                }, document_id)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, document_id)