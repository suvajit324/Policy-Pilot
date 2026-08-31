from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, datetime, random
from collections import defaultdict

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
BASE = os.path.dirname(os.path.abspath(__file__))

# Check if OpenAI API key is available
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
USE_OPENAI = bool(OPENAI_KEY)
print(f"OpenAI enabled: {USE_OPENAI}")

# --- PERSISTENT STORAGE ---
stats_memory = {
    "total_questions": 0,
    "unique_users": set(),
    "questions_log": [],
    "topic_counts": {"leave":0, "wfh":0, "working hours":0, "reimbursement":0, "performance":0, "onboarding":0, "general":0, "other":0},
    "feedback": [],
    "daily_active": defaultdict(int),
    "start_time": datetime.datetime.now().isoformat()
}

# --- GRANULAR ANSWERS - Different for each sub-question (ChatGPT style) ---
POLICY_KNOWLEDGE = {
    "leave": {
        "context": "Leave Policy: 12 CL, 12 SL, 15 EL per year. Apply via HR/ESS portal.",
        "sub_answers": {
            "how_many": """✅ **How many leaves do we get?**

You get total **39 leaves per year** (pro-rata if you joined mid-year):

• **Casual Leave (CL):** 12 per year - for personal work
• **Sick Leave (SL):** 12 per year - for illness
• **Earned Leave (EL):** 15 per year - for long vacations, can be carried forward

Your leave balance is visible in HR portal → Dashboard.

Source: HR Policy Handbook""",

            "sick": """✅ **Sick Leave Details**

**Sick Leave (SL): 12 days per year**

• Use when you are ill or medical emergency
• Apply via HR portal → Leave → SL
• No prior notice needed, inform manager on Slack
• Medical certificate required only if more than 2 consecutive days
• Can be taken as half-day also
• Unused SL cannot be encashed but adds to health record

Get well soon! 🤒

Source: HR Policy Handbook""",

            "casual": """✅ **Casual Leave Details**

**Casual Leave (CL): 12 days per year**

• For personal work, errands, family functions
• Need 1 day prior notice
• Max 3 consecutive CL allowed
• Apply via HR/ESS → Leave → CL
• Manager approval needed
• Sandwich rule: If you take CL on Friday and Monday, weekend counts? No, only office days count

Source: HR Policy Handbook""",

            "earned": """✅ **Earned Leave Details**

**Earned Leave (EL): 15 days per year**

• For long vacations, trips
• Need 1 week prior notice
• Can be carried forward up to 30 days
• Can be encashed at year-end (max 15 days)
• Apply via HR portal → EL → Need manager + HR approval
• Best for planned long breaks!

Source: HR Policy Handbook""",

            "apply": """✅ **How to apply for leave?**

**Step-by-step:**

1. Login to HR/ESS portal
2. Go to Leave → Apply Leave
3. Select leave type (CL/SL/EL)
4. Select dates (from - to)
5. Add reason (e.g., "Family function")
6. Submit → Goes to manager for approval
7. You get email + Slack notification on approval

**Tip:** Apply at least 1 day before for CL, 1 week for EL. For SL, inform immediately.

Source: HR Policy Handbook""",

            "default": """✅ **Leave Policy Overview**

We offer 12 Casual Leaves, 12 Sick Leaves, 15 Earned Leaves per year.

**Quick breakdown:**
• **CL:** 12/year - personal work, 1 day notice
• **SL:** 12/year - illness, no notice needed
• **EL:** 15/year - vacation, 1 week notice, carry forward allowed

Apply via HR/ESS portal → Leave. Balance visible on dashboard.

What specifically about leave do you want to know? - how many, how to apply, sick leave, casual leave?

Source: HR Policy Handbook"""
        }
    },
    "wfh": {
        "context": "WFH Policy: Up to 2 days/week WFH with manager approval. Core hours 10am-4pm.",
        "sub_answers": {
            "how_many": """✅ **How many WFH days allowed?**

You can take **up to 2 days per week** Work From Home.

• Max 2 days/week, not more than 2 consecutive days
• Hybrid model - team decides which days
• WFH not counted as leave (it's work!)
• Need manager approval via portal

Some teams have fixed WFH days (e.g., Monday & Friday). Check with your manager.

Source: HR Policy Handbook""",

            "how_to_apply": """✅ **How to apply for WFH?**

1. Login to HR portal
2. Go to WFH Request → New Request
3. Select dates
4. Add reason (optional)
5. Submit → Manager approves
6. Mark attendance as WFH in portal

**On WFH day:**
• Be online 10am-4pm on Slack/Teams
• Update standup status
• Laptop + internet required

Source: HR Policy Handbook""",

            "rules": """✅ **WFH Rules & Guidelines**

• Core hours 10am-4pm must be online
• Need good internet (reimbursement up to ₹1000/month for internet)
• Attend all meetings via video
• Office attendance tracked - WFH marked separately
• Laptop mandatory, no personal device for work
• If internet issue, inform manager and come to office or take leave

Source: HR Policy Handbook""",

            "default": """✅ **Work From Home Policy**

WFH up to 2 days/week with manager approval. Hybrid model.

**Key points:**
• Max 2 days/week
• Core hours 10am-4pm online on Slack
• Apply via HR portal → WFH Request
• WFH not counted as leave
• Internet reimbursement available

What about WFH? - how many days, how to apply, rules?

Source: HR Policy Handbook"""
        }
    },
    "working hours": {
        "context": "Working Hours: 9:30 AM to 6:30 PM Mon-Fri, core hours 10am-4pm.",
        "sub_answers": {
            "timing": """✅ **Office Timings**

**Standard:** 9:30 AM to 6:30 PM, Monday to Friday

• 1 hour lunch break (1pm-2pm flexible, you choose)
• Core hours: 10am-4pm must be available
• Flexible start: Can start 9:30-10:30am with manager info
• Weekend: Saturday-Sunday off

**Office location:** Check your joining confirmation email for reporting location and contact person.

Source: HR Policy Handbook""",

            "late": """✅ **Late Coming Policy**

• Punch-in required via HR portal or biometric
• Coming after 10:30am = half-day marked
• 3 lates in a month = 1 CL deduction
• Inform manager if late due to emergency
• Consistent late coming impacts performance review

**Tip:** Try to reach by 10am to be safe!

Source: HR Policy Handbook""",

            "punch": """✅ **Punch-in / Attendance**

• Punch-in/out via HR portal or biometric machine
• Required daily - even on WFH (mark WFH attendance)
• If you forget to punch, apply for regularization in portal within 3 days
• Attendance visible in dashboard
• Less than 8 hours = half-day unless manager approves

Source: HR Policy Handbook""",

            "default": """✅ **Working Hours & Office Timings**

9:30 AM to 6:30 PM, Mon-Fri. 1 hour lunch.

**Details:**
• Core hours 10am-4pm must be available
• Punch-in/out required
• Late after 10:30am = half-day
• Flexible start 9:30-10:30am
• Weekend off

What about working hours? - exact timing, late policy, punch?

Source: HR Policy Handbook"""
        }
    },
    "reimbursement": {
        "context": "Reimbursement: Submit bills via HR/ESS portal Finance → Reimbursements, 7-10 days processing.",
        "sub_answers": {
            "how_to": """✅ **How to claim reimbursement?**

**Step-by-step:**

1. Login to HR/ESS portal → Finance → Reimbursements
2. Click New Claim
3. Select expense type: Travel / Food / Internet / Medical
4. Enter date, amount, description
5. Upload original bills (PDF/JPG, not screenshot)
6. Submit → Manager approves → Finance processes
7. Amount credited to salary account in 7-10 days

**Eligible:** Travel, food during work, internet, medical, office supplies

Source: HR Policy Handbook""",

            "internet": """✅ **Internet Bill Reimbursement**

• Up to ₹1000 per month for WFH internet
• Submit internet bill via portal → Internet reimbursement
• Need bill with your name and month visible
• Paid with salary
• Original bill mandatory

**Tip:** Combine with other bills to claim monthly.

Source: HR Policy Handbook""",

            "travel": """✅ **Travel Reimbursement**

• Office travel, client visits eligible
• Auto: ₹10/km, Cab: actual with bill
• Submit via portal → Travel
• Need bills for cab, metro, auto
• Outstation travel needs prior manager approval

Source: HR Policy Handbook""",

            "default": """✅ **Reimbursement Policy**

Submit original bills via HR/ESS portal → Finance → Reimbursements.

• Submit within 30 days
• Flow: Employee → Manager → Finance
• Paid in 7-10 days to salary account
• Travel, food, internet, medical eligible

What reimbursement? - how to claim, internet bill, travel?

Source: HR Policy Handbook"""
        }
    },
    "performance": {
        "context": "Performance Review: Half-yearly in June & Dec, goals in Jan, rating 1-5 impacts bonus.",
        "sub_answers": {
            "when": """✅ **When is performance review?**

• **Goal setting:** January
• **Mid-year check-in:** June (self + manager review)
• **Final review:** December (rating + appraisal + hike discussion)
• **Skip-level:** Discussion with manager's manager in Dec

**Rating scale:** 1-5 (5=Exceptional, 4=Exceeds, 3=Meets, 2=Needs Improvement, 1=Poor)

Source: HR Policy Handbook""",

            "process": """✅ **Performance Review Process**

1. **Self-review:** You fill achievements in portal
2. **Manager review:** Manager rates and comments
3. **Peer feedback:** 2-3 peers give feedback (optional)
4. **Skip-level:** Discussion with senior manager
5. **Final rating:** Decided in Dec
6. **Bonus/Hike:** Linked to rating

**Tip:** Keep track of your wins monthly in a doc!

Source: HR Policy Handbook""",

            "default": """✅ **Performance Review Policy**

Reviews half-yearly in June & Dec. Goals in Jan.

**Cycle:**
• Jan: Goal setting
• June: Mid check-in
• Dec: Final review + rating
• Bonus/hike linked to rating

What about performance? - when, process, rating?

Source: HR Policy Handbook"""
        }
    }
}

def get_granular_answer(topic, question_lower):
    """Get different answer for same category based on sub-question - ChatGPT style"""
    if topic not in POLICY_KNOWLEDGE:
        return None
    
    knowledge = POLICY_KNOWLEDGE[topic]
    ql = question_lower.lower()
    
    # Check sub-topics
    if topic == "leave":
        if any(w in ql for w in ["how many", "kitne", "kitna", "total"]):
            return knowledge["sub_answers"]["how_many"]
        elif "sick" in ql or "bimari" in ql:
            return knowledge["sub_answers"]["sick"]
        elif "casual" in ql or "cl " in ql:
            return knowledge["sub_answers"]["casual"]
        elif "earned" in ql or "el " in ql or "carry" in ql or "encash" in ql:
            return knowledge["sub_answers"]["earned"]
        elif any(w in ql for w in ["how to apply", "apply", "kaise le", "kaise apply"]):
            return knowledge["sub_answers"]["apply"]
        else:
            return knowledge["sub_answers"]["default"]
    
    elif topic == "wfh":
        if any(w in ql for w in ["how many", "kitne din", "kitna", "days"]):
            return knowledge["sub_answers"]["how_many"]
        elif any(w in ql for w in ["how to apply", "apply", "kaise", "process"]):
            return knowledge["sub_answers"]["how_to_apply"]
        elif any(w in ql for w in ["rule", "guideline", "internet", "online"]):
            return knowledge["sub_answers"]["rules"]
        else:
            return knowledge["sub_answers"]["default"]
    
    elif topic == "working hours":
        if any(w in ql for w in ["late", "der se", "late aane"]):
            return knowledge["sub_answers"]["late"]
        elif any(w in ql for w in ["punch", "attendance", "regularization", "forget"]):
            return knowledge["sub_answers"]["punch"]
        elif any(w in ql for w in ["timing", "time", "hours", "kab se", "kab tak"]):
            return knowledge["sub_answers"]["timing"]
        else:
            return knowledge["sub_answers"]["default"]
    
    elif topic == "reimbursement":
        if any(w in ql for w in ["internet", "wifi", "net"]):
            return knowledge["sub_answers"]["internet"]
        elif any(w in ql for w in ["travel", "cab", "auto", "metro"]):
            return knowledge["sub_answers"]["travel"]
        elif any(w in ql for w in ["how to", "kaise", "process", "claim"]):
            return knowledge["sub_answers"]["how_to"]
        else:
            return knowledge["sub_answers"]["default"]
    
    elif topic == "performance":
        if any(w in ql for w in ["when", "kab", "date", "month"]):
            return knowledge["sub_answers"]["when"]
        elif any(w in ql for w in ["process", "kaise hota", "how"]):
            return knowledge["sub_answers"]["process"]
        else:
            return knowledge["sub_answers"]["default"]
    
    return knowledge["sub_answers"]["default"] if "default" in knowledge["sub_answers"] else None

def detect_topic_lenient(q_lower):
    ql = q_lower.lower()
    
    # Most lenient matching - handles typos, Hinglish, natural language
    if any(w in ql for w in ["working hour", "work hour", "office hour", "working time", "work timing", "office timing", "working hours", "work hours", "office hours", "hours of working", "hours of work", "work timings", "timing", "9:30", "6:30", "9 to 6", "office time", "shift", "punch", "late", "attendance", "kab se", "kab tak"]):
        # But check if it's specifically leave or wfh first
        if "leave" not in ql and "wfh" not in ql and "work from home" not in ql:
            return "working hours"
    if any(w in ql for w in ["wfh", "work from home", "work at home", "work from house", "remote work", "remote", "hybrid", "w f h", "work frm home", "ghar se kaam"]):
        return "wfh"
    if any(w in ql for w in ["reimb", "claim", "expense", "bill", "reimbursement", "paisa", "kharcha", "payment"]):
        return "reimbursement"
    if any(w in ql for w in ["leave", "leaves", "chutti", "casual leave", "sick leave", "earned leave", "vacation", "holiday", "time off", "cl ", " sl ", " el "]):
        return "leave"
    if any(w in ql for w in ["performance", "review", "appraisal", "rating", "hike", "bonus", "increment", "feedback", "pip", "promotion"]):
        return "performance"
    if any(w in ql for w in ["onboard", "joining", "day 1", "first day", "orientation", "laptop", "id card"]):
        return "onboarding"
    
    # Fallback: if contains hour/time/work
    if ("hour" in ql or "timing" in ql) and ("work" in ql or "office" in ql):
        return "working hours"
    
    # If question has policy/HR words, treat as general
    if any(w in ql for w in ["policy", "hr", "company", "office", "work", "employee"]):
        return "general"
    
    return "other"

async def get_openai_answer(question, context):
    """If OpenAI key present, get ChatGPT style answer"""
    if not USE_OPENAI:
        return None
    
    try:
        import openai
        openai.api_key = OPENAI_KEY
        
        prompt = f"""You are PolicyPilot, an HR Policy Assistant. Answer based on this context only. Be concise, friendly, structured like ChatGPT.

Context:
{context}

User question: {question}

Rules:
- Answer only from context, don't hallucinate
- Use bullet points, bold headings
- Keep it short (under 150 words)
- Add Source: HR Policy Handbook at end
- If not in context, say you can only answer policy questions and suggest topics

Answer:"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None

class Q(BaseModel):
    question: str

class Feedback(BaseModel):
    rating: int
    comment: str
    question: str = ""

@app.post("/ask")
async def ask(q: Q, request: Request):
    global stats_memory
    start = time.time()
    ql = q.question.lower()
    
    client_ip = request.client.host if request.client else "unknown"
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    stats_memory["total_questions"] += 1
    stats_memory["unique_users"].add(client_ip)
    topic = detect_topic_lenient(ql)
    stats_memory["topic_counts"][topic] = stats_memory["topic_counts"].get(topic,0) + 1
    stats_memory["daily_active"][today] += 1
    stats_memory["questions_log"].append({
        "time": datetime.datetime.now().isoformat(),
        "question": q.question[:100],
        "topic": topic,
        "ip": client_ip
    })
    stats_memory["questions_log"] = stats_memory["questions_log"][-100:]
    
    # Try OpenAI first if key present
    answer = None
    if USE_OPENAI and topic in POLICY_KNOWLEDGE:
        context = POLICY_KNOWLEDGE[topic]["context"]
        openai_ans = await get_openai_answer(q.question, context)
        if openai_ans:
            answer = openai_ans
    
    # Fallback to granular curated answers (ChatGPT style - different per sub-question)
    if not answer:
        granular = get_granular_answer(topic, ql)
        if granular:
            answer = granular
        elif topic == "general":
            answer = """✅ **Company Policy Assistant**

I can help you with company policies. Here are the topics I cover:

• 🏖️ **Leave policy** - CL, SL, EL, how many, how to apply
• 🏠 **WFH policy** - how many days, how to apply, rules
• ⏰ **Working hours** - office timings, late policy, punch
• 💰 **Reimbursement** - how to claim, internet bill, travel
• 🎯 **Performance review** - when, process, rating
• 🎓 **Onboarding** - Day 1 process

**Just ask naturally like ChatGPT:**
• "What are the office timings?"
• "How many sick leaves do we get?"
• "How to apply for WFH?"
• "Internet bill kaise claim karu?"
• "Late aane par kya hota hai?"

What would you like to know?

Source: HR Policy Handbook"""
        else:
            answer = f"""✅ **I can help with HR policies!**

You asked: "{q.question}"

I cover these topics with detailed answers:

• **Leave:** how many, sick leave, casual leave, how to apply
• **WFH:** how many days, how to apply, rules
• **Working hours:** timings, late policy, punch-in
• **Reimbursement:** how to claim, internet, travel bills
• **Performance:** when review happens, process

Could you rephrase with keywords like leave, WFH, working hours, reimbursement?

**Try:** "What are working hours?" or "How many sick leaves?"

Source: HR Policy Handbook"""
    
    elapsed = time.time() - start
    return {
        "answer": answer,
        "source": "HR Policy Handbook",
        "time_taken": f"{elapsed*1000:.0f}ms",
        "topic": topic,
        "used_openai": USE_OPENAI and answer and "openai" in str(answer).lower(),
        "stats": {"total_questions": stats_memory["total_questions"], "unique_users": len(stats_memory["unique_users"])}
    }

@app.post("/feedback")
def submit_feedback(f: Feedback, request: Request):
    global stats_memory
    stats_memory["feedback"].append({
        "time": datetime.datetime.now().isoformat(),
        "rating": f.rating,
        "comment": f.comment,
        "question": f.question,
        "ip": request.client.host if request.client else "unknown"
    })
    return {"status": "thanks", "total_feedback": len(stats_memory["feedback"])}

@app.get("/stats")
def get_stats():
    total = stats_memory["total_questions"]
    unique = len(stats_memory["unique_users"])
    feedback_count = len(stats_memory["feedback"])
    avg_rating = sum([f["rating"] for f in stats_memory["feedback"]]) / feedback_count if feedback_count else 0
    return {
        "total_questions_asked": total,
        "unique_users": unique,
        "topics": stats_memory["topic_counts"],
        "feedback_count": feedback_count,
        "avg_rating": round(avg_rating, 2),
        "daily_active_users": dict(stats_memory["daily_active"]),
        "questions_log": stats_memory["questions_log"][-20:],
        "feedback": stats_memory["feedback"][-10:],
        "uptime_since": stats_memory.get("start_time"),
        "openai_enabled": USE_OPENAI,
        "traction_goal_progress": {
            "goal": "20 users, 50 questions",
            "current_users": unique,
            "current_questions": total,
        }
    }

@app.get("/traction")
def traction_page():
    total = stats_memory["total_questions"]
    unique = len(stats_memory["unique_users"])
    fb = stats_memory["feedback"]
    avg = sum([f["rating"] for f in fb])/len(fb) if fb else 0
    html = f"""
    <html><head><title>Traction Dashboard</title>
    <style>
    body{{background:#0a0a0f;color:#fff;font-family:Inter;padding:30px}}
    .card{{background:#1a1a27;border:1px solid #2a2a40;border-radius:16px;padding:20px;margin-bottom:16px}}
    .big{{font-size:32px;font-weight:700;color:#a78bfa}}
    .grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
    .topic{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222}}
    </style></head><body>
    <h1>📊 PolicyPilot - ChatGPT Style Traction</h1>
    <p>Granular answers + Lenient matching + OpenAI optional | OpenAI: {USE_OPENAI}</p>
    <div class="grid">
      <div class="card"><div>Total Questions</div><div class="big">{total}</div><div>Goal: 50</div></div>
      <div class="card"><div>Unique Users</div><div class="big">{unique}</div><div>Goal: 20</div></div>
      <div class="card"><div>Feedback</div><div class="big">{len(fb)} | {avg:.1f}⭐</div><div>Avg rating</div></div>
    </div>
    <div class="card"><h3>Topics Asked</h3>
    {''.join([f'<div class="topic"><span>{k}</span><span>{v}</span></div>' for k,v in stats_memory["topic_counts"].items()])}
    </div>
    <div class="card"><h3>Recent Questions - Now with granular sub-topics</h3>
    {''.join([f"<div style='padding:6px 0;border-bottom:1px solid #222'>{l['time'][11:16]} - {l['question']} <small style='color:#888'>({l['topic']})</small></div>" for l in stats_memory["questions_log"][-15:]])}
    </div>
    <div class="card"><small>Uptime: {stats_memory.get('start_time')} | OpenAI: {USE_OPENAI} | Version: ChatGPT-style granular answers</small></div>
    </body></html>
    """
    return HTMLResponse(html)

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
