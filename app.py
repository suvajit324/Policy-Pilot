from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pickle, os, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()
BASE = os.path.dirname(os.path.abspath(__file__))

chunks = pickle.load(open(os.path.join(BASE, "chunks.pkl"), "rb"))

# Build TF-IDF index - smart keyword search
vectorizer = TfidfVectorizer(stop_words='english')
chunk_vectors = vectorizer.fit_transform(chunks)

class Q(BaseModel):
    question: str

@app.post("/ask")
def ask(q: Q):
    q_vec = vectorizer.transform([q.question])
    sims = cosine_similarity(q_vec, chunk_vectors)[0]
    top_idx = np.argsort(sims)[::-1][:3]

    # Only keep relevant chunks (similarity > 0.1)
    relevant = [i for i in top_idx if sims[i] > 0.05]
    if not relevant:
        relevant = top_idx[:2]

    ctx = "\n\n---\n\n".join([chunks[i] for i in relevant])

    return {
        "answer": ctx,
        "sources": relevant.tolist() if hasattr(relevant, 'tolist') else list(relevant),
        "scores": [float(sims[i]) for i in relevant]
    }

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))
