from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pickle, faiss, numpy as np, os, hashlib

app = FastAPI()
BASE = os.path.dirname(os.path.abspath(__file__))

chunks = pickle.load(open(os.path.join(BASE, "chunks.pkl"), "rb"))
index = faiss.read_index(os.path.join(BASE, "policy.index"))

def get_embedding(text: str):
    # Lightweight deterministic embedding - no torch/model needed
    h = hashlib.md5(text.encode()).digest()
    vec = np.array([b for b in h * 24], dtype="float32")[:384]
    vec = vec / (np.linalg.norm(vec) + 1e-9)
    # add simple word overlap boost
    return vec

class Q(BaseModel):
    question: str

@app.post("/ask")
def ask(q: Q):
    # Simple keyword search + faiss (works without HF API)
    q_lower = q.question.lower()
    scores = []
    for i, c in enumerate(chunks):
        score = sum(1 for w in q_lower.split() if w in c.lower())
        scores.append(score)
    top = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:3]
    ctx = "\n\n".join([chunks[i] for i in top])
    return {"answer": ctx[:2500], "sources": top}

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))