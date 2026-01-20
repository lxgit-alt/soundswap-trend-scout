import os
import json
import requests
import time
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
from google import genai
from serpapi import GoogleSearch

app = FastAPI()

# --- CONFIG ---
PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
APP_ID = os.getenv("DISCORD_APP_ID")

# Initialize Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def verify_discord_signature(body: str, signature: str, timestamp: str):
    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid request signature")

def generate_and_edit(interaction_token, context_text):
    """
    Unified function to generate the blog and edit the original 'Thinking' message.
    We use a Session and explicit timeout to prevent SSL drops.
    """
    session = requests.Session()
    edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{interaction_token}/messages/@original"
    
    try:
        # 1. Generate Content (Gemini 1.5 Flash is fast enough to usually hit < 10s)
        prompt = f"As a SoundSwap strategist, write a 600-word blog post based on: {context_text}. Include H1, H2s, and a CTA."
        
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        draft = response.text[:1950] # Stay under Discord's 2000 char limit

        # 2. Patch the message (The 'Deferred' response)
        # We add a 15s timeout here to ensure the connection doesn't hang
        session.patch(edit_url, json={"content": f"✍️ **SoundSwap AI Draft:**\n\n{draft}"}, timeout=15)
        
    except Exception as e:
        # Fallback if Gemini or the Webhook fails
        session.patch(edit_url, json={"content": f"⚠️ **SoundSwap AI Error:** {str(e)}"})

@app.post("/api/interactions")
async def interactions(request: Request):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()
    body_str = body.decode("utf-8")

    verify_discord_signature(body_str, signature, timestamp)
    data = json.loads(body_str)

    # 1. Handshake (Pings)
    if data.get("type") == 1:
        return {"type": 1}

    # 2. Handle 'Generate Draft' Message Command
    if data.get("type") == 2:
        # Extract the message that was right-clicked
        resolved_messages = data.get("data", {}).get("resolved", {}).get("messages", {})
        if not resolved_messages:
            return {"type": 4, "data": {"content": "❌ Could not read message context."}}

        msg_id = list(resolved_messages.keys())[0]
        context_text = resolved_messages[msg_id].get("content", "")
        token = data.get("token")

        # Instead of threading.Thread (unstable on Vercel), we call our logic.
        # NOTE: On Vercel's Free tier, this must finish within 10 seconds.
        # If it takes longer, Vercel will kill it. Gemini Flash is usually ~4-6 seconds.
        import threading
        threading.Thread(target=generate_and_edit, args=(token, context_text)).start()

        # Send 'Thinking...' state immediately
        return {"type": 5}

    return {"type": 4, "data": {"content": "Unknown Interaction"}}

@app.get("/api/scout")
async def daily_scout():
    """Triggered by Vercel Cron to post daily reports."""
    search = GoogleSearch({
        "q": "latest music production gear 2026 AI audio tools",
        "tbs": "qdr:d",
        "api_key": SERPAPI_KEY
    })
    results = search.get_dict()
    organic = results.get("organic_results", [])
    
    if organic:
        top = organic[0]
        report = f"🎸 **SoundSwap Daily Intel**\n🔥 {top.get('title')}\n🔗 {top.get('link')}\n\n*Right-click > Apps > Generate Draft*"
    else:
        report = "📡 **SoundSwap Scout:** No new major gear trends found in the last 24h."

    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    requests.post(url, headers={"Authorization": f"Bot {DISCORD_TOKEN}"}, json={"content": report})
    return {"status": "sent"}