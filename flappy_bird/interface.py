from fastapi import FastAPI
from agent import generate_game

app = FastAPI()

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.post("/query")
async def create_game(query: str):
    await generate_game(query)
    return {"status": "game generated"}