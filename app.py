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

class Q(BaseModel):
    question: str

# Complete Domain Knowledge - Cleaned from your 2 PDFs
KNOWLEDGE = {
    "leave": {
        "keywords": ["leave", "cl", "sl", "el", "pl", "sick", "casual", "earned", "privilege"],
        "answer": """**🏖️ Leave Policy**

For confirmed full-time employees:

**Annual Entitlement:**
• **Earned Leave / Privilege Leave (EL/PL): 18 days** - for long planned leaves
• **Casual Leave (CL): 7 days** - for short personal work
• **Sick Leave (SL): 10 days** - for health issues

**How to apply:**
1. Apply at least 1 working day in advance on HR portal
2. Emergency leaves are exception - inform ASAP
3. Manager approval is mandatory for personal reasons
4. Check balance before applying

Leave is subject to applicable law and company rules. Need to know about leave encashment? Just ask!"""
    },
    "wfh": {
        "keywords": ["wfh", "work from home", "remote", "hybrid"],
        "answer": """**🏠 Work From Home Policy**

**Guidelines:**
• WFH needs prior manager approval
• You must be active on Teams/Slack during work hours
• Deliverables must be on time - WFH is not a day off
• Good internet + quiet workspace expected

**Attendance:**
3 or more unexplained late arrivals in a calendar month may result in an attendance review.

WFH is a flexibility, use it responsibly!"""
    },
    "hours": {
        "keywords": ["working hour", "work hour", "timing", "9:30", "6:30", "punctual", "shift", "office time"],
        "answer": """**⏰ Working Hours**

**Standard Schedule:**
• **Monday to Friday: 9:30 AM - 6:30 PM**
• Includes 60-min break for lunch/rest
• Project teams may have different shifts as per client needs

**Be on time!** Inform your manager if you're going to be late. Punctuality is part of performance review."""
    },
    "reimbursement": {
        "keywords": ["reimbursement", "reimburse", "expense", "bill", "claim", "meal", "travel", "2500"],
        "answer": """**💰 Reimbursement Policy**

**Process to claim:**
1. Raise claim within **15 days of expense** - late claims are rejected
2. Attach original bills/receipts
3. Submit on HR/Finance portal
4. Get manager approval → Finance processes it

**Limits (Sample):**
• Entry-level meal/travel: **Rs. 2,500 per claim**
• Project-specific policies may override this

Keep bills safe and submit early!"""
    },
    "performance": {
        "keywords": ["performance", "review", "appraisal", "training", "growth", "objectives", "learning"],
        "answer": """**🎯 Performance, Training & Growth**

**How it works:**
• You get clear role objectives from your manager at start
• Regular 1:1s and periodic performance discussions
• Mandatory trainings must be completed by deadline - don't miss it
• Want to learn something new? Request learning resources or certification support through your manager/HR

We invest in your growth, you own your performance!"""
    },
    "notice": {
        "keywords": ["notice", "resign", "resignation", "relieving", "60 days"],
        "answer": """**📋 Notice Period & Exit**

• **After confirmation: 60 calendar days** notice required
• Refer your appointment letter for exact terms
• Early release depends on manager + HR approval + project handover
• FNF settlement as per applicable law"""
    },
    "attendance": {
        "keywords": ["attendance", "late", "arrival", "punctuality"],
        "answer": """**⏱️ Attendance Policy**

• Be punctual - 9:30 AM login expected
• 3+ unexplained late arrivals in a calendar month → attendance review
• Inform manager in advance for any deviation
• Personal reasons require approval unless emergency"""
    }
}

def chatgpt_style_answer(user_q, best_chunk_raw):
    q = user_q.lower()

    # 1. Greetings & small talk - like ChatGPT
    if q.strip() in ["hi", "hello", "hey", "hii", "helo"] or q.startswith("hi "):
        return "Hey there! 👋 I'm **PolicyPilot** - your company policy buddy.\n\nI know everything from your 2 HR documents (32 chunks). Ask me about leave, WFH, working hours, reimbursement, performance, notice period - anything!\n\nWhat's up?"
    if "how are you" in q:
        return "I'm doing great and fully online! 🟢 Ready to help you with any policy question. What do you need?"
    if "who are you" in q or "what can you do" in q or "what's in domain" in q or "what do you know" in q:
        return """I'm **PolicyPilot Enterprise v2.0** built by Suvajit! 🤖

**My Domain - I can answer everything about:**
• 🏖️ Leave Policy (18 EL, 7 CL, 10 SL)
• 🏠 WFH & Hybrid
• ⏰ Working Hours (9:30-6:30) & Attendance
• 💰 Reimbursement (Rs.2500 limit, 15-day rule)
• 🎯 Performance & Training
• 📋 Notice Period (60 days)
• And anything from your 2 company documents!

Just ask naturally like you chat with ChatGPT - I get it!"""
    if "thank" in q:
        return "You're welcome! 😊 Ask anytime you have a policy doubt. Happy to help!"

    # 2. Find best matching policy
    scores = {}
    for key, data in KNOWLEDGE.items():
        s = 0
        for kw in data["keywords"]:
            if kw in q: s += 2
            if kw in best_chunk_raw.lower(): s += 0.5
        scores[key] = s

    best_intent = max(scores, key=scores.get)

    if scores[best_intent] >= 1:
        return KNOWLEDGE[best_intent]["answer"]

    # 3. Fallback - if question is related but we don't have exact template, summarize best chunk CLEANLY
    cleaned = best_chunk_raw.replace('■','Rs.').replace(' ',' ').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Take first 2 good sentences, not broken ones
    sentences = [s.strip() for s in cleaned.split('.') if len(s.strip()) > 20][:3]
    if sentences:
        return f"**Here's what I found for: '{user_q}'**\n\n" + "\n\n".join([f"• {s}." for s in sentences]) + "\n\n*This is from your company policy docs. Want me to explain it simpler?*"

    return """I'm your policy assistant for this company! I can help with leave, WFH, working hours, reimbursement, performance, notice period etc.

Your question seems outside those docs. Try asking like:
- What is the leave policy?
- How to claim reimbursement?
- What are working hours?"""

@app.post("/ask")
def ask(q: Q):
    q_vec = vectorizer.transform([q.question])
    sims = cosine_similarity(q_vec, chunk_vectors)[0]
    best_idx = int(np.argmax(sims))
    best_chunk = chunks[best_idx]
    answer = chatgpt_style_answer(q.question, best_chunk)
    return {"answer": answer, "sources": [best_idx]}

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))
