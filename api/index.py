from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os, pickle, faiss, re
from sentence_transformers import SentenceTransformer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

print("Loading model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
with open(os.path.join(BASE, "chunks.pkl"), "rb") as f:
    chunks = pickle.load(f)
index = faiss.read_index(os.path.join(BASE, "policy.index"))
print(f"READY {len(chunks)} chunks")

class Q(BaseModel):
    question: str

def clean(t): return re.sub(r'\s+', ' ', t).strip()

@app.post("/ask")
def ask_api(q: Q):
    question = q.question
    q_lower = question.lower()
    q_emb = model.encode([question])
    D, I = index.search(q_emb.astype('float32'), k=8)
    scored = []
    q_words = set(q_lower.split())
    for idx, dist in zip(I[0], D[0]):
        if idx >= len(chunks): continue
        chunk = chunks[idx]
        score = sum(1 for w in q_words if len(w)>3 and w in chunk.lower())
        if "working hour" in chunk.lower(): score+=10
        if "wfh" in chunk.lower() and "wfh" in q_lower: score+=10
        if "leave" in chunk.lower() and "leave" in q_lower: score+=10
        scored.append((score*10 - dist, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for s,c in scored[:3]]
    full = clean(" ".join(top))
    sens = re.split(r'(?<=[.!?])\s+', full)
    rel = [s.strip() for s in sens if len(s.strip())>20][:4]
    ans = f"✅ Answer for: {question}\n\n{rel[0]}\n\n"
    if len(rel)>1:
        ans+="Details:\n"
        for s in rel[1:]: ans+=f"• {s}\n"
    ans+=f"\n\nSource: 2 docs • {len(chunks)} chunks"
    return {"answer": ans}

@app.get("/")
def root(): return {"status": "PolicyPilot API running"}
