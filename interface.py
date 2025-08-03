from fastapi import FastAPI
import query_engine_v2
import uuid

app = FastAPI()

prev_id, id = None, None

@app.get("/")
def read_root():
    return "Logfile Assistant"

@app.post("/query")
def search(query: str, conversation_id: str = id):
    global id, prev_id

    id = str(uuid.uuid4()) if conversation_id is None else conversation_id
    _conversation_id = conversation_id if conversation_id is not None else id

    if (prev_id != _conversation_id): 
        prev_id = _conversation_id
        query_engine_v2.set_conversation_id(_conversation_id)
    
    return {
        "Response": query_engine_v2.search(query),
        "Conversation ID": _conversation_id
    }