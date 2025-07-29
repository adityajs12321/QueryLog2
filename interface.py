from fastapi import FastAPI
import query_engine

app = FastAPI()

@app.get("/")
def read_root():
    return "Logfile Assistant"

@app.post("/query")
def search(conversation_id: int, query: str):
    query_engine.set_conversation_id(conversation_id)
    return query_engine.search(query)