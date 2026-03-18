"""
WhatsApp AI Assistant - 100% FREE
Gemini AI + WhatsApp
Automatically replies to WhatsApp messages, understands purpose, forwards summary to you
"""

from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
import os
import json
from datetime import datetime

app = Flask(__name__)

# ── CONFIG (सिर्फ यह बदलो) ────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
OWNER_NAME     = os.environ.get("OWNER_NAME", "Rahul")
ASSISTANT_NAME = os.environ.get("ASSISTANT_NAME", "Priya")
OWNER_NUMBER   = os.environ.get("OWNER_NUMBER", "919999999999")  # WhatsApp number with country code

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # Free model

# ── In-memory storage ─────────────────────────────────────────────────────────
messages_log = []
sessions     = {}

# ── AI BRAIN ──────────────────────────────────────────────────────────────────
def get_ai_reply(sender: str, user_message: str, history: list) -> dict:
    session_history = "\n".join([f"{h['role']}: {h['text']}" for h in history[-6:]])

    prompt = f"""You are {ASSISTANT_NAME}, a smart WhatsApp assistant for {OWNER_NAME}.
Reply in Hindi or English (match the sender's language).

Conversation so far:
{session_history}

Sender: {user_message}

Your job:
1. Greet warmly on first message
2. Understand WHY they are messaging
3. Decide: needs_owner = true/false

Respond ONLY in this JSON format (no extra text):
{{
  "reply": "your reply to sender in their language",
  "needs_owner": true or false,
  "summary": "one line summary of what they want (in Hindi)",
  "urgent": true or false
}}

Rules:
- If personal/important/urgent → needs_owner: true
- If sales/spam/general info → needs_owner: false, handle yourself
- Keep replies friendly and short
- Always be helpful"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        return json.loads(raw[start:end])
    except Exception as e:
        return {
            "reply": f"Namaste! Main {ASSISTANT_NAME} hoon, {OWNER_NAME} ka assistant. Aap kaise help kar sakta/sakti hoon?",
            "needs_owner": False,
            "summary": user_message[:80],
            "urgent": False
        }

# ── WHATSAPP WEBHOOK ──────────────────────────────────────────────────────────

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta webhook verification"""
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    verify_token = os.environ.get("WEBHOOK_VERIFY_TOKEN", "mytoken123")
    
    if mode == "subscribe" and token == verify_token:
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive_message():
    """WhatsApp से message आया"""
    data = request.get_json()
    
    try:
        entry   = data["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]
        
        if "messages" not in value:
            return jsonify({"status": "ok"})
        
        msg        = value["messages"][0]
        sender     = msg["from"]
        msg_type   = msg["type"]
        phone_id   = value["metadata"]["phone_number_id"]
        
        # सिर्फ text messages handle करो
        if msg_type != "text":
            send_whatsapp_message(phone_id, sender,
                f"Main sirf text messages samajh sakta/sakti hoon abhi. Kripya text mein likhein. 🙏")
            return jsonify({"status": "ok"})
        
        user_text = msg["text"]["body"]
        
        # Session get/create
        if sender not in sessions:
            sessions[sender] = {"history": [], "turns": 0, "start": datetime.now().isoformat()}
        
        session = sessions[sender]
        session["history"].append({"role": "User", "text": user_text})
        session["turns"] += 1
        
        # AI response
        ai = get_ai_reply(sender, user_text, session["history"])
        session["history"].append({"role": "Assistant", "text": ai["reply"]})
        
        # Sender को reply भेजो
        send_whatsapp_message(phone_id, sender, ai["reply"])
        
        # Log save करो
        log_entry = {
            "time":        datetime.now().strftime("%d/%m %H:%M"),
            "sender":      sender,
            "message":     user_text,
            "ai_reply":    ai["reply"],
            "summary":     ai.get("summary", ""),
            "needs_owner": ai.get("needs_owner", False),
            "urgent":      ai.get("urgent", False)
        }
        messages_log.append(log_entry)
        
        # अगर owner को forward करना है
        if ai.get("needs_owner") and sender != OWNER_NUMBER:
            urgent_tag = "🔴 URGENT" if ai.get("urgent") else "🔵 Message"
            owner_msg  = f"""{urgent_tag} — नया message!

👤 From: +{sender}
💬 Message: {user_text}
📝 Summary: {ai.get('summary', '')}

Dashboard: https://your-app.onrender.com"""
            send_whatsapp_message(phone_id, OWNER_NUMBER, owner_msg)
        
        sessions[sender] = session
        
    except Exception as e:
        print(f"Error: {e}")
    
    return jsonify({"status": "ok"})


def send_whatsapp_message(phone_id: str, to: str, text: str):
    """WhatsApp Cloud API से message भेजो"""
    import urllib.request
    
    token = os.environ.get("WHATSAPP_TOKEN", "")
    if not token:
        print(f"[DEMO MODE] To: {to} | Message: {text}")
        return
    
    url     = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }).encode()
    
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Send error: {e}")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

DASHBOARD = """<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Assistant Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#fff;min-height:100vh}
.top{background:linear-gradient(135deg,#075e54,#128c7e);padding:1.5rem 1.25rem}
.top h1{font-size:1.3rem;font-weight:700}
.top p{font-size:0.8rem;opacity:0.8;margin-top:3px}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:0.75rem;padding:1rem 1.25rem}
.stat{background:#1a1a1a;border-radius:12px;padding:1rem;text-align:center;border:1px solid #2a2a2a}
.stat .n{font-size:1.8rem;font-weight:700;color:#25d366}
.stat .l{font-size:0.75rem;color:#888;margin-top:2px}
.section{padding:0 1.25rem 1.25rem}
.section h2{font-size:0.85rem;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.75rem}
.msg{background:#1a1a1a;border-radius:12px;padding:1rem;margin-bottom:0.6rem;border:1px solid #2a2a2a;border-left:3px solid #25d366}
.msg.urgent{border-left-color:#ff4444}
.msg.needs-owner{border-left-color:#ffd700}
.msg-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.sender{font-size:0.85rem;font-weight:600;color:#25d366}
.time{font-size:0.72rem;color:#555}
.msg-text{font-size:0.85rem;color:#ccc;margin-bottom:4px}
.summary{font-size:0.78rem;color:#888;font-style:italic}
.badge{font-size:0.65rem;padding:2px 7px;border-radius:20px;font-weight:600}
.badge.urgent{background:#3d1515;color:#ff6b6b}
.badge.forward{background:#3d3000;color:#ffd700}
.empty{text-align:center;padding:3rem 1rem;color:#444;font-size:0.9rem}
.status{background:#1a1a1a;border-radius:12px;padding:1rem;margin-bottom:1rem;border:1px solid #2a2a2a;font-size:0.82rem;color:#888;line-height:1.6}
.status .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#25d366;margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
</style>
</head>
<body>
<div class="top">
  <h1>🤖 {{ assistant }} — AI Assistant</h1>
  <p>{{ owner }} के सभी WhatsApp messages यहाँ दिखते हैं</p>
</div>
<div class="stats">
  <div class="stat"><div class="n">{{ total }}</div><div class="l">कुल Messages</div></div>
  <div class="stat"><div class="n">{{ forwarded }}</div><div class="l">Forward किए</div></div>
  <div class="stat"><div class="n">{{ urgent }}</div><div class="l">Urgent</div></div>
  <div class="stat"><div class="n">{{ handled }}</div><div class="l">AI ने Handle किए</div></div>
</div>
<div class="section">
  <div class="status"><span class="dot"></span>AI Assistant चालू है — Messages का जवाब दे रहा/रही है</div>
  <h2>Recent Messages</h2>
  {% if logs %}
    {% for m in logs|reverse %}
    <div class="msg {% if m.urgent %}urgent{% elif m.needs_owner %}needs-owner{% endif %}">
      <div class="msg-header">
        <span class="sender">+{{ m.sender }}</span>
        <div style="display:flex;gap:6px;align-items:center">
          {% if m.urgent %}<span class="badge urgent">URGENT</span>{% endif %}
          {% if m.needs_owner %}<span class="badge forward">FORWARD</span>{% endif %}
          <span class="time">{{ m.time }}</span>
        </div>
      </div>
      <div class="msg-text">💬 {{ m.message }}</div>
      <div class="summary">📝 {{ m.summary }}</div>
    </div>
    {% endfor %}
  {% else %}
    <div class="empty">अभी कोई message नहीं आया।<br><br>WhatsApp Business API setup होने के बाद<br>messages यहाँ दिखेंगे।</div>
  {% endif %}
</div>
</body>
</html>"""

@app.route("/")
def dashboard():
    return render_template_string(
        DASHBOARD,
        assistant = ASSISTANT_NAME,
        owner     = OWNER_NAME,
        logs      = messages_log,
        total     = len(messages_log),
        forwarded = sum(1 for m in messages_log if m["needs_owner"]),
        urgent    = sum(1 for m in messages_log if m["urgent"]),
        handled   = sum(1 for m in messages_log if not m["needs_owner"])
    )

if __name__ == "__main__":
    print(f"\n✅ WhatsApp AI Assistant चालू!")
    print(f"   Assistant: {ASSISTANT_NAME} | Owner: {OWNER_NAME}")
    print(f"   Dashboard: http://localhost:5000\n")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
