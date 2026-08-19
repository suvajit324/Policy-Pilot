from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pickle, os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()

# CORS allow all
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = os.path.dirname(os.path.abspath(__file__))
chunks = pickle.load(open(os.path.join(BASE, "chunks.pkl"), "rb"))

# Build smart search index once at startup
vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1,2))
chunk_vectors = vectorizer.fit_transform(chunks)
print(f"Loaded {len(chunks)} chunks")

class Q(BaseModel):
    question: str

@app.post("/ask")
def ask(q: Q):
    try:
        q_vec = vectorizer.transform([q.question])
        sims = cosine_similarity(q_vec, chunk_vectors)[0]
        top_idx = np.argsort(sims)[::-1][:3]
        # filter low scores
        relevant = [i for i in top_idx if sims[i] > 0.08]
        if not relevant:
            relevant = top_idx[:2].tolist()
        ctx = "\n\n---\n\n".join([chunks[i] for i in relevant])
        return {"answer": ctx, "sources": list(map(int, relevant))}
    except Exception as e:
        print("ERROR in /ask:", e)
        return {"answer": f"Error: {str(e)}", "sources": []}

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(chunks)}
