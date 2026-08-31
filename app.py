from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, json, datetime
from collections import Counter, defaultdict

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
BASE = os.path.dirname(os.path.abspath(__file__))

# --- ANALYTICS STORAGE ---
STATS_FILE = os.path.join(BASE, "traction_stats.json")
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            return json.load(open(STATS_FILE))
        except:
            pass
    return {
        "total_questions": 0,
        "unique_users": [],
        "questions_log": [],
        "topic_counts": {"leave":0, "wfh":0, "working hours":0, "reimbursement":0, "performance":0, "other":0},
        "feedback": [],
        "daily_active": defaultdict(int),
        "start_time": datetime.datetime.now().isoformat()
    }

def save_stats(s):
    # convert defaultdict
    s_copy = dict(s)
    s_copy["daily_active"] = dict(s["daily_active"])
    with open(STATS_FILE, "w") as f:
        json.dump(s_copy, f, indent=2)

stats = load_stats()
if isinstance(stats["daily_active"], dict):
    stats["daily_active"] = defaultdict(int, stats["daily_active"])

# --- CURATED PRECISE ANSWERS ---
CURATED = {
 "reimbursement": "✅ Answer for: How to claim reimbursement?\n\nTo claim reimbursement, submit original bills in HR/ESS portal -> Finance -> Reimbursements. Add expense type, date, amount and upload bills. Manager approves, Finance processes in 7-10 days.\n\nDetails:\n• Submit within 30 days\n• Flow: Employee → Manager → Finance\n• Paid to salary account\n\nSource: HR Policy Handbook",
 "leave": "✅ Answer for: leave policy\n\n12 Casual Leaves, 12 Sick Leaves, 15 Earned Leaves per year (pro-rata). Apply via HR/ESS -> Leave -> Apply.\n\nDetails:\n• CL: 12/year, 1 day notice\n• SL: 12/year, medical if >2 days\n• EL: 15/year, 1 week notice\n\nSource: HR Policy Handbook",
 "wfh": "✅ Answer for: WFH policy\n\nWFH up to 2 days/week with manager approval. Request via HR portal -> WFH Request. Core hours 10am-4pm online.\n\nDetails:\n• Max 2 days/week\n• Hybrid roster based\n• Not counted as leave\n\nSource: HR Policy Handbook",
 "working hours": "✅ Answer for: working hours\n\n9:30 AM to 6:30 PM, Mon-Fri. 1 hour lunch. Punch-in/out required.\n\nDetails:\n• Core hours 10am-4pm\n• Late >10:30am = half-day\n• Office attendance tracked\n\nSource: HR Policy Handbook",
 "performance": "✅ Answer for: performance review\n\nReviews half-yearly in June & Dec. Goals in Jan, mid check in June, final in Dec. Rating impacts appraisal.\n\nDetails:\n• Self-review + Manager review\n• Skip-level discussion\n• Bonus linked to rating\n\nSource: HR Policy Handbook",
 "onboarding": "✅ Answer for: onboarding\n\nOn Day 1, HR shares joining confirmation, reporting location, contact person, and ESS credentials. Complete docs and laptop setup in first week.\n\nSource: HR Policy Handbook"
}

def detect_topic(q_lower):
    if "reimb" in q_lower or "claim" in q_lower: return "reimbursement"
    if "leave" in q_lower: return "leave"
    if "wfh" in q_lower or "work from home" in q_lower or "remote" in q_lower: return "wfh"
    if "working hour" in q_lower or "office hour" in q_lower or "timing" in q_lower or "work hour" in q_lower: return "working hours"
    if "performance" in q_lower or "review" in q_lower or "appraisal" in q_lower: return "performance"
    if "onboard" in q_lower or "joining" in q_lower: return "other"
    return "other"

class Q(BaseModel):
    question: str
class Feedback(BaseModel):
    rating: int
    comment: str
    question: str = ""

@app.post("/ask")
def ask(q: Q, request: Request):
    global stats
    start = time.time()
    ql = q.question.lower()
    
    # --- TRACTION TRACKING ---
    client_ip = request.client.host if request.client else "unknown"
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    stats["total_questions"] += 1
    if client_ip not in stats["unique_users"]:
        stats["unique_users"].append(client_ip)
    topic = detect_topic(ql)
    if topic in stats["topic_counts"]:
        stats["topic_counts"][topic] += 1
    else:
        stats["topic_counts"]["other"] += 1
    
    stats["daily_active"][today] += 1
    stats["questions_log"].append({
        "time": datetime.datetime.now().isoformat(),
        "question": q.question[:100],
        "topic": topic,
        "ip": client_ip
    })
    # keep last 100
    stats["questions_log"] = stats["questions_log"][-100:]
    save_stats(stats)
    
    # --- ANSWER LOGIC ---
    if "reimb" in ql or "claim" in ql: ans = CURATED["reimbursement"]
    elif "leave" in ql: ans = CURATED["leave"]
    elif "wfh" in ql or "work from home" in ql: ans = CURATED["wfh"]
    elif "working hour" in ql or "office hour" in ql or "timing" in ql: ans = CURATED["working hours"]
    elif "performance" in ql: ans = CURATED["performance"]
    elif "onboard" in ql: ans = CURATED["onboarding"]
    else:
        # guardrail but still count
        ans = "🛡️ I can only answer Company Policy questions.\n\nTry:\n• What is leave policy?\n• What is WFH policy?\n• How to claim reimbursement?"
    
    elapsed = time.time() - start
    return {
        "answer": ans,
        "source": "HR Policy Handbook",
        "time_taken": f"{elapsed*1000:.0f}ms",
        "stats": {
            "total_questions": stats["total_questions"],
            "unique_users": len(stats["unique_users"])
        }
    }

@app.post("/feedback")
def submit_feedback(f: Feedback, request: Request):
    global stats
    stats["feedback"].append({
        "time": datetime.datetime.now().isoformat(),
        "rating": f.rating,
        "comment": f.comment,
        "question": f.question,
        "ip": request.client.host if request.client else "unknown"
    })
    save_stats(stats)
    return {"status": "thanks", "total_feedback": len(stats["feedback"])}

@app.get("/stats")
def get_stats():
    """Traction dashboard for deck screenshots"""
    total = stats["total_questions"]
    unique = len(stats["unique_users"])
    feedback_count = len(stats["feedback"])
    avg_rating = sum([f["rating"] for f in stats["feedback"]]) / feedback_count if feedback_count else 0
    
    # daily active list
    daily = dict(stats["daily_active"])
    
    return {
        "total_questions_asked": total,
        "unique_users": unique,
        "topics": stats["topic_counts"],
        "feedback_count": feedback_count,
        "avg_rating": round(avg_rating, 2),
        "daily_active_users": daily,
        "questions_log": stats["questions_log"][-20:],
        "feedback": stats["feedback"][-10:],
        "uptime_since": stats.get("start_time"),
        "traction_goal_progress": {
            "goal": "20 users, 50 questions",
            "current_users": unique,
            "current_questions": total,
            "users_pct": min(100, int(unique/20*100)),
            "questions_pct": min(100, int(total/50*100))
        }
    }

@app.get("/traction")
def traction_page():
    """Simple HTML dashboard to screenshot for assignment"""
    html = f"""
    <html><head><title>Traction Dashboard</title>
    <style>
    body{{background:#0a0a0f;color:#fff;font-family:Inter;padding:30px}}
    .card{{background:#1a1a27;border:1px solid #2a2a40;border-radius:16px;padding:20px;margin-bottom:16px}}
    .big{{font-size:32px;font-weight:700;color:#a78bfa}}
    .grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
    .topic{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222}}
    </style></head><body>
    <h1>📊 PolicyPilot Avatar - Traction Dashboard</h1>
    <p>Live metrics for assignment - Take screenshot for deck</p>
    <div class="grid">
      <div class="card"><div>Total Questions</div><div class="big">{stats['total_questions']}</div><div>Goal: 50</div></div>
      <div class="card"><div>Unique Users</div><div class="big">{len(stats['unique_users'])}</div><div>Goal: 20</div></div>
      <div class="card"><div>Feedback</div><div class="big">{len(stats['feedback'])} | {sum([f['rating'] for f in stats['feedback']])/len(stats['feedback']) if stats['feedback'] else 0:.1f}⭐</div><div>Avg rating</div></div>
    </div>
    <div class="card"><h3>Topics Asked</h3>
    {''.join([f'<div class="topic"><span>{k}</span><span>{v}</span></div>' for k,v in stats['topic_counts'].items()])}
    </div>
    <div class="card"><h3>Recent Questions (Last 10)</h3>
    {''.join([f"<div style='padding:6px 0;border-bottom:1px solid #222'>{l['time'][11:16]} - {l['question']} <small style='color:#888'>({l['topic']})</small></div>" for l in stats['questions_log'][-10:]])}
    </div>
    <div class="card"><h3>User Feedback</h3>
    {''.join([f"<div style='padding:8px 0'>⭐{f['rating']} - {f['comment']}</div>" for f in stats['feedback'][-10:]]) if stats['feedback'] else '<div>No feedback yet</div>'}
    </div>
    <div class="card"><small>Uptime since: {stats.get('start_time')} | Daily: {dict(stats['daily_active'])}</small></div>
    </body></html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)