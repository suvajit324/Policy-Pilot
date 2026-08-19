from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pickle, os, re, math
from collections import Counter
import numpy as np

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = os.path.dirname(os.path.abspath(__file__))
chunks = pickle.load(open(os.path.join(BASE, "chunks.pkl"), "rb"))

def tokenize(t):
    words = re.findall(r'\b[a-z]{3,}\b', t.lower())
    bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words)-1)]
    return words + bigrams

vocab = {}
doc_freq = Counter()
tokenized_chunks = []
for ch in chunks:
    toks = set(tokenize(ch))
    tokenized_chunks.append(tokenize(ch))
    for tok in toks:
        doc_freq[tok] += 1
for i, tok in enumerate(doc_freq):
    vocab[tok] = i

V = len(vocab)
N = len(chunks)
idf = {tok: math.log(N/(1+freq)) for tok, freq in doc_freq.items()}

chunk_vectors = []
for toks in tokenized_chunks:
    vec = np.zeros(V)
    cnt = Counter(toks)
    for tok, c in cnt.items():
        if tok in vocab:
            vec[vocab[tok]] = c * idf[tok]
    norm = np.linalg.norm(vec)
    if norm > 0: vec = vec / norm
    chunk_vectors.append(vec)
chunk_vectors = np.array(chunk_vectors)

class Q(BaseModel):
    question: str

KNOWLEDGE = {
    "leave": "### 🏖️ Leave Policy\nFor **confirmed full-time employees**:\n**Annual Entitlement:**\n- **Earned / Privilege Leave (EL/PL): 18 days**\n- **Casual Leave (CL): 7 days**\n- **Sick Leave (SL): 10 days**\n\n**How to apply:** Apply 1 day in advance on HR portal. Emergency = inform ASAP. Manager approval mandatory.",
    "wfh": "### 🏠 WFH Policy\n- WFH needs **prior manager approval**\n- Must be active on Teams/Slack during work hours\n- Deliverables must be on time\n- Good internet + quiet workspace expected",
    "hours": "### ⏰ Working Hours\n- **Monday to Friday: 9:30 AM - 6:30 PM**\n- 60-min lunch break included",
    "reimbursement": "### 💰 Reimbursement Policy\n**How to claim:**\n1. Submit within **15 days**\n2. Original bills required\n3. Upload on HR portal\n**Limit:** Rs. 2,500 per claim\n**Timeline:** Processed in next payroll",
    "performance": "### 🎯 Performance & Growth\n- You get clear role objectives from your manager\n- Regular 1:1s and periodic performance discussions\n- Mandatory trainings must be completed by deadline",
    "notice": "### 📋 Notice Period\n- **After confirmation: 60 calendar days**\n- During probation: 15-30 days",
}

INTENTS = {
    "leave": ["leave", "el", "pl", "cl", "sl", "vacation", "time off", "earned leave", "casual leave", "sick leave"],
    "wfh": ["wfh", "work from home", "remote", "hybrid", "work from house"],
    "hours": ["working hours", "work hours", "office hours", "office timing", "9:30", "6:30"],
    "reimbursement": ["reimbursement", "reimburse", "claim", "expense", "bill", "2500", "medical claim", "travel claim"],
    "performance": ["performance", "appraisal", "review", "growth", "feedback", "increment", "promotion"],
    "notice": ["notice", "resign", "resignation", "notice period", "serving period"],
}

def detect_intent(q):
    q = q.lower()
    scores = {k:0 for k in INTENTS}
    for intent, kws in INTENTS.items():
        for kw in kws:
            if kw in q:
                scores[intent] += 10 if " " in kw else 3
    if "reimbursement" in q or "reimburs" in q: scores["reimbursement"] += 25
    if "leave" in q: scores["leave"] += 25
    if "wfh" in q or "work from home" in q: scores["wfh"] += 25
    if "hour" in q and "working" in q: scores["hours"] += 25
    if "performance" in q or "appraisal" in q: scores["performance"] += 25
    if "notice" in q or "resign" in q: scores["notice"] += 25
    best = max(scores, key=scores.get)
    return best, scores[best]

def get_answer(user_q, max_sim):
    q = user_q.lower().strip()

    if q in ["hi","hello","hey","hii","hello!","hi there"]:
        return "Hey! 👋 I'm **PolicyPilot** - your HR policy assistant. Ask me about leave, WFH, working hours, reimbursement, performance, or notice period!"

    # Natural handling for company name - friendly, not weird
    if "company name" in q or q in ["company", "what is company", "company?", "which company", "company name?"]:
        return "I’m focused on internal HR policies, so I don’t have company profile details like the official registered name. You can find that on the company website or intranet. If you want, I can help you with **leave, WFH, working hours, reimbursement, performance, or notice period** - just let me know!"

    # Detect intent
    intent, score = detect_intent(q)

    # Out of domain - natural reply
    if score == 0 or max_sim < 0.06:
        if len(q.split()) <= 2:
            return "Could you tell me a bit more? Try asking like 'What is the leave policy?' or 'How to claim reimbursement?'"
        # This is the natural out-of-domain message you wanted
        return "That’s a bit outside what I can help with - I’m specifically trained on our internal HR policies (leave, WFH, working hours, reimbursement, performance, and notice period). For other topics, it’s best to check with the HR or admin team. Is there anything related to HR policies I can help you with?"

    # Return matched policy - ensures different questions get different answers
    return KNOWLEDGE[intent]

@app.post("/ask")
def ask(q: Q):
    toks = tokenize(q.question)
    vec = np.zeros(V)
    cnt = Counter(toks)
    for tok, c in cnt.items():
        if tok in vocab:
            vec[vocab[tok]] = c * idf.get(tok, 0)
    norm = np.linalg.norm(vec)
    if norm > 0: vec = vec / norm
    sims = chunk_vectors @ vec if V>0 else np.array([0])
    max_sim = float(np.max(sims)) if len(sims) else 0
    answer = get_answer(q.question, max_sim)
    return {"answer": answer}

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/health")
def health():
    return {"status": "ok"}
