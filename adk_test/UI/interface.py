import os
from urllib.parse import quote_plus
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from agent_v2 import DatabaseSessionService, second_engine, Session
import json
import asyncio
from datetime import datetime
from typing import List
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SessionCreate(BaseModel):
    userId: str
    appName: str

class MessageCreate(BaseModel):
    content: str
    role: str

class Message(BaseModel):
    id: str
    sessionId: str
    content: str
    role: str
    timestamp: datetime

class Session(BaseModel):
    id: str
    userId: str
    appName: str
    lastMessage: str | None = None
    createdAt: datetime
    updatedAt: datetime

# In-memory storage for messages (replace with database in production)
postgre_password = os.environ["POSTGRE_PASS"]
        #   "postgresql+psycopg2://scott:tiger@localhost/test"
encoded_password = quote_plus(postgre_password)
db_url = f"postgresql+psycopg2://adityajs:{encoded_password}@localhost/querylogconv"
session_service = DatabaseSessionService(
    db_url=db_url,   # This will filter out function call events from context
)

APP_NAME = "new_app2"
USER_ID = "adijs"

@app.get("/sessions")
async def get_sessions():
    # Here you should fetch sessions from your database
    # For now, we'll return a mock response
    now = datetime.now()
    existing_sessions = await session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    sessions_list = []
    for session in existing_sessions.sessions:
        session_name = "Unknown"

        session_ = await session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session.id
        )
        
        if session_ and session_.events:
            for event in session_.events[::-1]:
                print(event.content.role, end=" ")
                if event.content.role == "user":
                    if event.content and event.content.parts:
                        print(event.content.parts)
                        part = event.content.parts[0]
                        if hasattr(part, "text") and part.text:
                            session_name = part.text
                        else: continue
                    break

        session_model = Session(
            id=session.id,
            userId=session.user_id,
            appName=session.app_name,
            lastMessage=session_name,
            createdAt=datetime.now(),
            updatedAt=datetime.fromtimestamp(session.last_update_time)
        )
        sessions_list.append(session_model)
        print()
    return jsonable_encoder(sessions_list)

@app.post("/sessions")
async def create_session(session_create: SessionCreate):
    try:
        # Create a new session
        now = datetime.now()
        session = Session(
            id=f"session_{int(now.timestamp())}",
            userId=session_create.userId,
            appName=session_create.appName,
            createdAt=now,
            updatedAt=now
        )
        return jsonable_encoder(session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

session_messages = {}

@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id
        )
    messages = []
    if session and session.events:
            # Concatenate the last few events as context
            for event in session.events:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            # conversation_history += event.content.role + ": " + part.text + "\n"
                            message = Message(
                                id=event.id,
                                sessionId=session_id,
                                content=part.text,
                                role=event.content.role,
                                timestamp=event.timestamp
                            )
                            messages.append(message)
    
    try:
        return jsonable_encoder(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/{session_id}/messages")
async def create_message(session_id: str, message: MessageCreate):
    try:
        # Process the message using your agent
        response = await second_engine(message.content)
        
        # Create messages
        timestamp = datetime.now()
        user_message = Message(
            id=f"msg_{int(timestamp.timestamp())}_user",
            sessionId=session_id,
            content=message.content,
            role="user",
            timestamp=timestamp
        )
        
        assistant_message = Message(
            id=f"msg_{int(timestamp.timestamp())}_assistant",
            sessionId=session_id,
            content=response,
            role="assistant",
            timestamp=timestamp
        )
        
        # Store messages in session_messages
        if session_id not in session_messages:
            session_messages[session_id] = []
        
        session_messages[session_id].extend([user_message, assistant_message])
        
        return jsonable_encoder([user_message, assistant_message])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream")
async def query_sse(session_id: str, q: str):
    """
    Send responses using Server-Sent Events (SSE)
    """
    async def generate_stream():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to stream'})}\n\n"

            response = await second_engine(session_id, q)

            if isinstance(response, str):
                words = response.split()
                yield f"data: {json.dumps({'type': 'response', 'content': response})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Stream completed'})}\n\n"
            
        except Exception as e:
            error_data = {
                'type': 'error',
                'message': str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )