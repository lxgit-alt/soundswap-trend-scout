import os
import json
import requests
import threading
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from google import genai
from datetime import datetime
from serpapi import GoogleSearch

app = FastAPI()

# --- CONFIG ---
PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
APP_ID = os.getenv("DISCORD_APP_ID")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

def verify_discord_signature(body: str, signature: str, timestamp: str):
    if not PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="Missing Public Key")
    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except:
        raise HTTPException(status_code=401, detail="Invalid request signature")

def generate_and_edit(interaction_token, context_text):
    """Handles the long-form AI generation in the background."""
    try:
        # Specialized SoundSwap Prompt
        prompt = f"""
        You are the lead strategist for SoundSwap. Write a professional, punchy, 600-word blog post.
        Context: {context_text}
        
        Structure:
        1. Catchy H1 Headline
        2. 'The Trend' (H2) - Why this matters for producers.
        3. 'Strategic Takeaways' (H2) - Bullet points of action items.
        4. 'The Bottom Line' (H2) - CTA for the SoundSwap community.
        """
        
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        # Discord limits: ~2000 chars. We'll send the most important part.
        draft = response.text[:1950]

        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{interaction_token}/messages/@original"
        requests.patch(edit_url, json={"content": f"✍️ **SoundSwap AI Draft Complete:**\n\n{draft}"})
        
    except Exception as e:
        error_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{interaction_token}/messages/@original"
        requests.patch(error_url, json={"content": f"❌ **Drafting Error:** {str(e)}"})

@app.post("/api/interactions")
async def interactions(request: Request):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()
    body_str = body.decode("utf-8")

    verify_discord_signature(body_str, signature, timestamp)
    data = json.loads(body_str)

    if data.get("type") == 1:
        return {"type": 1}

    # Handle the "Generate Draft" Right-Click Command
    if data.get("type") == 2:
        resolved_messages = data["data"].get("resolved", {}).get("messages", {})
        if not resolved_messages:
            return {"type": 4, "data": {"content": "❌ Error: Could not find message context."}}
            
        message_id = list(resolved_messages.keys())[0]
        context_text = resolved_messages[message_id]["content"]
        interaction_token = data.get("token")

        # Execute AI generation in background thread
        threading.Thread(target=generate_and_edit, args=(interaction_token, context_text)).start()

        # Immediate response to satisfy Discord's 3-second rule
        return {"type": 5} 

    return {"type": 4, "data": {"content": "Interaction received."}}

@app.get("/api/scout")
async def daily_scout():
    """Vercel Cron job for trend discovery."""
    search = GoogleSearch({
        "q": "latest music production news 2026 AI audio plugins",
        "tbs": "qdr:d",
        "api_key": SERPAPI_KEY
    })
    results = search.get_dict()
    top = results.get("organic_results", [{}])[0]
    
    report = f"🎸 **SoundSwap Daily Intel**\n🔥 {top.get('title')}\n🔗 {top.get('link')}\n\n*Right-click this message > Apps > SoundSwap AI > Generate Draft to write an article!*"

    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    requests.post(url, headers={"Authorization": f"Bot {DISCORD_TOKEN}"}, json={"content": report})
    return {"status": "success"}