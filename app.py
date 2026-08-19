from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pickle, os, re, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = os.path.dirname(os.path.abspath(__file__))
chunks = pickle.load(open(os.path.join(BASE, "chunks.pkl"), "rb"))
vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1,2))
chunk_vectors = vectorizer.fit_transform(chunks)
print(f"PolicyPilot loaded: {len(chunks)} chunks")

class Q(BaseModel):
    question: str

# CLEAN KNOWLEDGE - No broken text
KNOWLEDGE = {
    "leave": """### 🏖️ Leave Policy

For **confirmed full-time employees**:

**Annual Entitlement:**
• **Earned / Privilege Leave (EL/PL): 18 days** - for planned long leaves
• **Casual Leave (CL): 7 days** - for short personal work
• **Sick Leave (SL): 10 days** - for health issues

**How to apply:**
1. Apply at least 1 working day in advance on HR portal
2. Emergency leaves = inform ASAP
3. Manager approval mandatory for personal reasons
4. Check balance before applying""",

    "wfh": """### 🏠 WFH Policy

• WFH needs **prior manager approval**
• Must be active on Teams/Slack during work hours
• Deliverables must be on time
• Good internet + quiet workspace expected

**Note:** 3+ unexplained late arrivals in a month may trigger attendance review.""",

    "hours": """### ⏰ Working Hours

• **Monday to Friday: 9:30 AM - 6:30 PM**
• Includes 60-min lunch/rest break
• Project teams may have different shifts per client needs
• Be punctual - inform manager if late""",

    "reimbursement": """### 💰 Reimbursement

**How to claim:**
1. Submit within **15 days of expense** (late = rejected)
2. Attach original bills/receipts
3. Submit on portal → Manager approval → Finance processes

**Limit:**
• Entry-level meal/travel: **Rs. 2,500 per claim** (project policy may vary)""",

    "performance": """### 🎯 Performance & Growth

• You get clear role objectives from your manager
• Regular 1:1s and periodic performance discussions
• Mandatory trainings must be completed by deadline
• Need learning/certification? Request via manager/HR""",

    "notice": """### 📋 Notice Period

• **After confirmation: 60 calendar days**
• Early release = as per appointment letter + manager/HR approval
• Ensure proper handover""",

    "attendance": """### ⏱️ Attendance

• Login by 9:30 AM expected
• 3+ unexplained late arrivals/month → attendance review
• Inform manager in advance for deviation"""
}

def get_answer(user_q: str, best_chunk: str, max_sim: float):
    q = user_q.lower().strip()

    # === GUARDRAIL 1: Prompt Injection / Jailbreak ===
    blocked = ["ignore previous", "ignore your", "system prompt", "jailbreak", "reveal prompt", "show your chunks", "hack"]
    if any(b in q for b in blocked):
        return "I'm PolicyPilot, I can only answer from your company HR docs (leave, WFH, hours, reimbursement etc.). I can't reveal internal system details."

    # === GUARDRAIL 2: Greetings & Small Talk - LIKE CHATGPT ===
    greetings = ["hi", "hello", "hey", "hii", "helo", "hi there", "hello there"]
    if q in greetings or q.startswith(("hi ", "hello ", "hey ")):
        return "Hey there! 👋 I'm **PolicyPilot** - your company policy buddy.\n\nI know everything from your 2 HR docs. Ask me about leave, WFH, working hours, reimbursement, performance, notice period - anything!\n\nWhat's up?"

    if "how are you" in q:
        return "I'm doing great and fully online! 🟢 Ready to help you with any policy question. What do you need?"

    if "good to chat" in q or "feeling good" in q or "feeling happy" in q or "i'm good" in q:
        return "That's awesome to hear! 😊 I'm good too and happy to help!\n\nWhat policy can I help you with today - leave, WFH, working hours?"

    if "who are you" in q or "what can you do" in q or "what is your domain" in q or "what do you know" in q:
        return """I'm **PolicyPilot Enterprise v2.0** built by Suvajit! 🤖

**I can answer everything about:**
• 🏖️ Leave (18 EL, 7 CL, 10 SL)
• 🏠 WFH & Hybrid
• ⏰ Working Hours (9:30-6:30)
• 💰 Reimbursement (Rs.2500, 15-day rule)
• 🎯 Performance & Training
• 📋 Notice Period (60 days)
• ⏱️ Attendance & Punctuality

Ask naturally - like you chat with ChatGPT!"""

    if "thank" in q:
        return "You're welcome! 😊 Ask anytime you have a policy doubt."

    # === GUARDRAIL 3: Low Relevance / Out of Domain ===
    if max_sim < 0.12:
        # If it's very short small talk, treat as chat
        if len(q.split()) < 7:
            return "Got it! 👍 I'm here for your policy queries. Try asking: 'What is the leave policy?' or 'How to claim reimbursement?'"
        return "Hmm, that seems outside our HR documents. I specialize in your company policies - leave, WFH, working hours, reimbursement, performance, notice period.\n\nCould you rephrase with those topics?"

    # === INTENT DETECTION ===
    text = q + " " + best_chunk.lower()
    scores = {}
    for key, val in KNOWLEDGE.items():
        scores[key] = sum(1 for kw in [key] + val.lower().split()[:20] if kw in text and len(kw) > 3)
        # keyword boost
        if key == "reimbursement" and "reimbursement" in text: scores[key] += 5
        if key == "leave" and "leave" in text: scores[key] += 5
        if key == "wfh" and ("wfh" in text or "work from home" in text): scores[key] += 5
        if key == "hours" and "working hour" in text: scores[key] += 5
        if key == "performance" and "performance" in text: scores[key] += 5
        if key == "notice" and "notice" in text: scores[key] += 5

    best_intent = max(scores, key=scores.get)
    if scores[best_intent] > 0:
        return KNOWLEDGE[best_intent]

    # Fallback - clean summary of best chunk (no broken words)
    clean = best_chunk.replace('■','Rs.').replace('□','')
    clean = re.sub(r'\s+', ' ', clean).strip()
    sents = [s.strip() for s in clean.split('.') if len(s.strip()) > 25][:2]
    if sents:
        return f"**For your question: '{user_q}'**\n\n" + "\n\n".join([f"• {s}." for s in sents])

    return KNOWLEDGE["leave"]

@app.post("/ask")
def ask(q: Q):
    q_vec = vectorizer.transform([q.question])
    sims = cosine_similarity(q_vec, chunk_vectors)[0]
    max_sim = float(np.max(sims))
    best_idx = int(np.argmax(sims))
    best_chunk = chunks[best_idx]

    answer = get_answer(q.question, best_chunk, max_sim)
    return {"answer": answer} # No source leakage!

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(chunks)}
