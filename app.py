from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pickle, os, re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = os.path.dirname(os.path.abspath(__file__))
chunks = pickle.load(open(os.path.join(BASE, "chunks.pkl"), "rb"))
vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1,2))
chunk_vectors = vectorizer.fit_transform(chunks)

class Q(BaseModel):
    question: str

def clean(text):
    # remove weird boxes and extra spaces
    text = text.replace('■', 'Rs.').replace('□', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

@app.post("/ask")
def ask(q: Q):
    q_lower = q.question.lower()

    # 1. TF-IDF score
    q_vec = vectorizer.transform([q.question])
    sims = cosine_similarity(q_vec, chunk_vectors)[0]

    # 2. Keyword bonus - THIS makes it accurate!
    keyword_bonus = []
    for c in chunks:
        c_lower = c.lower()
        bonus = 0
        for word in q_lower.split():
            if len(word) > 3 and word in c_lower:
                bonus += 0.2
        # heavy bonus for exact policy name
        if "reimbursement" in q_lower and "reimbursement" in c_lower: bonus += 1.0
        if "leave" in q_lower and "leave" in c_lower: bonus += 1.0
        if "wfh" in q_lower or "work from home" in q_lower:
            if "wfh" in c_lower or "work from home" in c_lower: bonus += 1.0
        if "working hour" in q_lower and "working hour" in c_lower: bonus += 1.0
        if "performance" in q_lower and "performance" in c_lower: bonus += 1.0
        keyword_bonus.append(bonus)

    final_scores = sims + np.array(keyword_bonus)
    best_idx = int(np.argmax(final_scores))

    # Return ONLY 1 best chunk, cleaned
    best_chunk = clean(chunks[best_idx])

    # If chunk is too long, take relevant part
    if len(best_chunk) > 1200:
        # try to cut around keyword
        best_chunk = best_chunk[:1200] + "..."

    return {
        "answer": f"**Answer for: {q.question}**\n\n{best_chunk}\n\n---\n*Source: Chunk {best_idx} | Score: {final_scores[best_idx]:.2f}*",
        "sources": [best_idx]
    }

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))
