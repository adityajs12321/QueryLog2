from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agent_v2 import second_engine
import json
import asyncio

app = FastAPI()

@app.get("/")
def read_root():
    return "efe"

@app.get("/query")
async def ask_question(q: str):
    return await second_engine(q)

@app.get("/stream")
async def stream_query(q: str):
    """
    Stream responses using Server-Sent Events (SSE)
    """
    async def generate_stream():
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to stream'})}\n\n"
            
            # Here you would integrate with your streaming agent
            # For now, I'll show a basic example
            response = await second_engine(q)
            
            # If second_engine returns a complete response, you can chunk it
            # Or modify second_engine to yield streaming responses
            if isinstance(response, str):
                # Stream the response word by word as an example
                words = response.split()
                for i, word in enumerate(words):
                    chunk_data = {
                        'type': 'chunk',
                        'content': word + ' ',
                        'index': i
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    await asyncio.sleep(0.1)  # Small delay for demonstration
            
            # Send completion message
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Stream completed'})}\n\n"
            
        except Exception as e:
            # Send error message
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

@app.get("/stream-advanced")
async def stream_query_advanced(q: str):
    """
    Advanced streaming with proper SSE format and event types
    """
    async def generate_advanced_stream():
        try:
            # Send start event
            yield f"event: start\ndata: {json.dumps({'query': q, 'timestamp': 'now'})}\n\n"
            
            # Simulate processing steps
            processing_steps = [
                "Analyzing query...",
                "Retrieving relevant information...",
                "Processing with AI model...",
                "Generating response..."
            ]
            
            for step in processing_steps:
                yield f"event: progress\ndata: {json.dumps({'step': step})}\n\n"
                await asyncio.sleep(0.5)
            
            # Get the actual response
            response = await second_engine(q)
            
            # Stream the response
            yield f"event: response\ndata: {json.dumps({'content': response})}\n\n"
            
            # Send completion event
            yield f"event: complete\ndata: {json.dumps({'status': 'success'})}\n\n"
            
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_advanced_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.get("/stream-agent")
async def stream_agent_response(q: str):
    """
    Stream real-time responses from your ADK agent with live event updates
    """
    async def generate_agent_stream():
        try:
            from google.genai import types
            from agent_v2 import multi_agent_orchestrator, session_service, APP_NAME, USER_ID
            import uuid
            
            # Create a unique session for this stream
            stream_session_id = f"stream_{uuid.uuid4().hex[:8]}"
            
            # Send connection event
            yield f"event: connected\ndata: {json.dumps({'session_id': stream_session_id, 'query': q})}\n\n"
            
            # Create new session
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=stream_session_id
            )
            
            yield f"event: session_created\ndata: {json.dumps({'message': 'Session initialized'})}\n\n"
            
            # Create message content
            content = types.Content(role='user', parts=[types.Part(text=q)])
            
            yield f"event: processing\ndata: {json.dumps({'message': 'Routing query to appropriate agent'})}\n\n"
            
            response_parts = []
            
            # Stream events from the agent
            async for event in multi_agent_orchestrator.run_async(USER_ID, stream_session_id, content):
                # Send different types of events based on what's happening
                if event.is_final_response():
                    if event.content and event.content.parts:
                        text_parts = []
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text_parts.append(part.text)
                        
                        if text_parts:
                            final_response = ' '.join(text_parts)
                            response_parts.append(final_response)
                            
                            # Stream the final response in chunks
                            words = final_response.split()
                            for i, word in enumerate(words):
                                chunk_data = {
                                    'type': 'response_chunk',
                                    'content': word + ' ',
                                    'chunk_index': i,
                                    'total_words': len(words)
                                }
                                yield f"event: chunk\ndata: {json.dumps(chunk_data)}\n\n"
                                await asyncio.sleep(0.05)  # Small delay for streaming effect
                    break
                else:
                    # Send intermediate processing events
                    event_data = {
                        'type': 'intermediate',
                        'author': event.author if hasattr(event, 'author') else 'system',
                        'timestamp': str(event.timestamp) if hasattr(event, 'timestamp') else 'now'
                    }
                    yield f"event: intermediate\ndata: {json.dumps(event_data)}\n\n"
            
            # Send completion event
            yield f"event: complete\ndata: {json.dumps({'status': 'success', 'session_id': stream_session_id})}\n\n"
            
        except Exception as e:
            error_data = {
                'type': 'error',
                'message': str(e),
                'error_type': type(e).__name__
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_agent_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )