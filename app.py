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

def make_chatgpt_answer(question, raw_chunk):
    """Turn messy chunk into ChatGPT-like specific answer"""
    q = question.lower()
    # Clean the raw chunk
    text = raw_chunk.replace('■','Rs.').replace('□','').replace(' ',' ')
    text = re.sub(r'\s+', ' ', text).strip()

    # Build specific answer based on question type
    if "reimbursement" in q:
        # Extract reimbursement info
        return f"""### 💰 How to Claim Reimbursement

To claim reimbursement at our company, follow this process:

**Process:**
• Submit your claim **within 15 days** of the expense
• Attach valid bills/receipts
• Get manager approval
• HR/Finance will process it

**Limits:**
• Sample meal/travel limit: **Rs. 2,500 per claim** for entry-level (unless project policy says otherwise)
• Project-specific limits may apply

**Details from policy:**
> {text[:800]}

Need help with the reimbursement form? Just ask!"""

    elif "working hour" in q or "working hours" in q or "timing" in q:
        return f"""### ⏰ Working Hours & Punctuality

**Normal Schedule:**
• **Monday - Friday: 9:30 AM to 6:30 PM**
• Includes 60-minute meal/rest break
• Teams may have different shifts based on project needs

**From policy:**
> {text[:800]}

Be punctual and inform your manager for any deviations!"""

    elif "leave" in q:
        return f"""### 🏖 Leave Policy

Here's your leave structure:

**Key Points:**
{text[:1000]}

**How to apply:**
• Apply at least 1 working day in advance
• Get manager approval
• Check leave balance in HR portal

Want to know about specific leave type (sick, casual, earned)? Ask me!"""

    elif "wfh" in q or "work from home" in q:
        return f"""### 🏠 WFH Policy

**Work From Home Guidelines:**
{text[:1000]}

**Tips:**
• Keep your status active on Teams/Slack
• Ensure deliverables are on time
• Prior approval needed from manager"""

    elif "performance" in q or "review" in q:
        return f"""### 🎯 Performance Review

**How it works:**
• You receive role objectives from your manager
• Periodic performance discussions happen
• Mandatory training must be completed by deadline
• You can request learning/certification support via manager/HR

**Full context:**
> {text[:900]}"""

    else:
        # Generic nice formatting
        return f"""### ✅ Answer for: {question}

{text[:1200]}

---
*Let me know if you want this in simpler terms or need next steps!*"""

@app.post("/ask")
def ask(q: Q):
    q_lower = q.question.lower()
    q_vec = vectorizer.transform([q.question])
    sims = cosine_similarity(q_vec, chunk_vectors)[0]

    # Smart bonus scoring
    bonus = []
    for c in chunks:
        cl = c.lower()
        b = 0
        if "reimbursement" in q_lower and "reimbursement" in cl: b+=1.5
        if "leave" in q_lower and "leave" in cl: b+=1.5
        if "wfh" in q_lower and ("wfh" in cl or "work from home" in cl): b+=1.5
        if "working hour" in q_lower and "working hour" in cl: b+=1.5
        if "performance" in q_lower and "performance" in cl: b+=1.5
        bonus.append(b)

    final = sims + np.array(bonus)
    best_idx = int(np.argmax(final))

    nice_answer = make_chatgpt_answer(q.question, chunks[best_idx])

    return {"answer": nice_answer, "sources": [best_idx]}

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))
