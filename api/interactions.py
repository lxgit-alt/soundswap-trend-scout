import os
import json
import asyncio
import threading
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey

app = FastAPI()

# Import functions
import sys
sys.path.append('.')
from api.index import (
    daily_topics_store,
    verify_discord_signature,
    process_daily_topics_selection,
    process_outline_generation,
    process_topic_outlines,
    generate_final_blog
)

@app.post("/")
async def interactions(request: Request):
    """Handle Discord interactions."""
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify signature
    verify_discord_signature(body_str, signature, timestamp)
    data = json.loads(body_str)

    # 1. Handshake (Pings)
    if data.get("type") == 1:
        return {"type": 1}

    # 2. Handle Application Commands
    if data.get("type") == 2:
        command_data = data.get("data", {})
        command_name = command_data.get("name", "")
        token = data.get("token")
        
        if command_name == "blog":
            # Start async task
            thread = threading.Thread(
                target=lambda: asyncio.run(process_daily_topics_selection(token))
            )
            thread.start()
            return {"type": 5}
        
        elif command_name == "outlines":
            options = command_data.get("options", [])
            context_text = ""
            
            for opt in options:
                if opt.get("name") == "topic":
                    context_text = opt.get("value", "")
                    break
            
            if not context_text:
                context_text = "latest music production trends"
            
            thread = threading.Thread(
                target=lambda: asyncio.run(process_outline_generation(token, context_text))
            )
            thread.start()
            
            return {"type": 5}
        
        return {"type": 4, "data": {"content": "❌ Unknown command"}}

    return {"type": 4, "data": {"content": "Unknown Interaction"}}

@app.post("/followup")
async def handle_followup(request: Request):
    """Handle follow-up selections."""
    try:
        data = await request.json()
        token = data.get("token")
        user_input = data.get("content", "").strip()
        
        if user_input in ['1', '2', '3', '4']:
            topic_index = int(user_input) - 1
            
            thread = threading.Thread(
                target=lambda: asyncio.run(process_topic_outlines(token, topic_index))
            )
            thread.start()
            
            return {"status": "processing_outlines"}
        
        elif user_input in ['1️⃣', '2️⃣', '3️⃣', '4️⃣'] or user_input in ['1', '2', '3', '4']:
            outline_index = int(user_input[0]) - 1
            
            thread = threading.Thread(
                target=lambda: asyncio.run(generate_final_blog(token, outline_index))
            )
            thread.start()
            
            return {"status": "generating_blog"}
        
        return {"status": "invalid_input"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}