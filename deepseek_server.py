# deepseek_server.py (Modified for Ollama)
from fastapi import FastAPI
import requests
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = FastAPI()

OLLAMA_URL = "http://localhost:11434"

@app.post("/generate")
async def generate_text(prompt: str):
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": "deepseek-r1:1.5b",
            "prompt": prompt,
            "stream": False
        }
    )
    return {"response": response.json()["response"]}

