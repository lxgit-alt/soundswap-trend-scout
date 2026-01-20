import os
import json
import requests
import time
from typing import List, Dict, Tuple
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
from google import genai
from serpapi import GoogleSearch
from textblob import TextBlob
from datetime import datetime
import asyncio

app = FastAPI()

# --- CONFIG ---
PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
APP_ID = os.getenv("DISCORD_APP_ID")

# 4 High-impact topics for daily scout
NICHE_QUERIES = [
    "latest music production gear releases 2026",
    "breaking AI audio tools for artists",
    "independent music marketing trends 2026",
    "music streaming industry news today"
]

# Initialize Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def verify_discord_signature(body: str, signature: str, timestamp: str):
    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid request signature")

def analyze_sentiment(text: str) -> Tuple[str, float]:
    """Analyze sentiment using TextBlob."""
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    if polarity > 0.2:
        sentiment = "POSITIVE"
        emoji = "😊"
    elif polarity < -0.2:
        sentiment = "NEGATIVE"
        emoji = "😠"
    else:
        sentiment = "NEUTRAL"
        emoji = "😐"
    
    return f"{sentiment} {emoji}", round(polarity, 2)

def get_trend_score(keyword: str) -> int:
    """Get trend score from Google Trends."""
    try:
        search = GoogleSearch({
            "engine": "google_trends",
            "q": keyword,
            "data_type": "TIMESERIES",
            "date": "now 7-d",
            "api_key": SERPAPI_KEY
        })
        results = search.get_dict()
        timeseries = results.get("interest_over_time", {}).get("timeline_data", [])
        return int(timeseries[-1].get("values")[0].get("value")) if timeseries else 50
    except:
        return 50

def get_serp_data(query: str) -> Dict:
    """Fetch SERP data including related questions."""
    score = get_trend_score(query)
    
    search = GoogleSearch({
        "engine": "google",
        "q": query,
        "tbs": "qdr:d",
        "api_key": SERPAPI_KEY,
        "num": 3
    })
    
    results = search.get_dict()
    organic = results.get("organic_results", [])
    related_questions = [q.get('question') for q in results.get("related_questions", [])[:3]]
    
    first_result = organic[0] if organic else {}
    
    return {
        "query": query,
        "score": score,
        "link": first_result.get('link', 'No link found'),
        "title": first_result.get('title', ''),
        "snippet": first_result.get('snippet', ''),
        "questions": related_questions,
        "status": "🔥 VIRAL" if score > 75 else "📈 TRENDING" if score > 50 else "📊 STEADY"
    }

async def generate_four_outlines(context: str, serp_data: Dict) -> List[Dict]:
    """Generate 4 distinct blog outline approaches with sentiment analysis."""
    
    prompt = f"""
    CONTEXT: {context}
    
    SERP DATA:
    - Topic: {serp_data['query']}
    - Trend Score: {serp_data['score']}/100 ({serp_data['status']})
    - Source: {serp_data['title']}
    - People Also Ask: {', '.join(serp_data['questions'])}
    
    Generate 4 DISTINCT blog outline approaches:
    
    1. **Technical Deep Dive** - Focus on specifications, features, technical analysis
    2. **Creative Applications** - How artists/producers can practically use this
    3. **Industry Impact** - Market trends, business implications, future predictions
    4. **Beginner-Friendly Guide** - Simplified explanation for newcomers
    
    For EACH outline, provide:
    - Overall tone/sentiment (based on current industry discussions)
    - Target audience (who will find this most valuable)
    - 3-4 key talking points
    - Estimated reading time
    - SEO keywords to include
    
    Make each outline unique and actionable.
    """
    
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        # Parse the response into 4 outlines
        outlines = []
        current_outline = {}
        lines = response.text.split('\n')
        
        for line in lines:
            if line.startswith('1. **Technical'):
                if current_outline:
                    outlines.append(current_outline)
                current_outline = {"type": "Technical Deep Dive", "content": line}
            elif line.startswith('2. **Creative'):
                if current_outline:
                    outlines.append(current_outline)
                current_outline = {"type": "Creative Applications", "content": line}
            elif line.startswith('3. **Industry'):
                if current_outline:
                    outlines.append(current_outline)
                current_outline = {"type": "Industry Impact", "content": line}
            elif line.startswith('4. **Beginner'):
                if current_outline:
                    outlines.append(current_outline)
                current_outline = {"type": "Beginner-Friendly Guide", "content": line}
            elif current_outline:
                current_outline["content"] += "\n" + line
        
        if current_outline:
            outlines.append(current_outline)
            
        # Add sentiment analysis to each outline
        for outline in outlines:
            sentiment_label, sentiment_score = analyze_sentiment(outline["content"])
            outline["sentiment"] = sentiment_label
            outline["sentiment_score"] = sentiment_score
            
        return outlines[:4]  # Ensure exactly 4 outlines
        
    except Exception as e:
        print(f"Outline generation error: {e}")
        # Fallback outlines
        return [
            {"type": "Technical Deep Dive", "sentiment": "NEUTRAL 😐", "content": "Technical analysis of gear specifications..."},
            {"type": "Creative Applications", "sentiment": "POSITIVE 😊", "content": "How artists can use this creatively..."},
            {"type": "Industry Impact", "sentiment": "NEUTRAL 😐", "content": "Market trends and implications..."},
            {"type": "Beginner-Friendly Guide", "sentiment": "POSITIVE 😊", "content": "Simple guide for newcomers..."}
        ]

async def generate_and_edit(interaction_token: str, context_text: str):
    """Generate 4 outlines and edit the original message."""
    session = requests.Session()
    edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{interaction_token}/messages/@original"
    
    try:
        # Get SERP data for context
        serp_data = get_serp_data(context_text[:50])  # Use first 50 chars as query
        
        # Generate 4 outlines
        outlines = await generate_four_outlines(context_text, serp_data)
        
        # Build Discord response
        response = f"🎸 **SoundSwap AI - 4 Blog Outlines + Sentiment Analysis**\n"
        response += f"**Topic:** {serp_data['query']}\n"
        response += f"**Trend Score:** {serp_data['score']}/100 ({serp_data['status']})\n"
        response += f"**Source:** {serp_data['link']}\n\n"
        
        for i, outline in enumerate(outlines, 1):
            response += f"**{i}. {outline['type']}** {outline['sentiment']}\n"
            response += f"```{outline['content'][:300]}...```\n"
            
            if i < len(outlines):
                response += "─" * 30 + "\n"
        
        response += "\n**📊 Sentiment Summary:**\n"
        for outline in outlines:
            response += f"• {outline['type']}: {outline['sentiment']} (Score: {outline['sentiment_score']})\n"
        
        # Add reaction instructions
        response += "\n**React with:**\n"
        response += "1️⃣ - Technical Deep Dive\n"
        response += "2️⃣ - Creative Applications\n"
        response += "3️⃣ - Industry Impact\n"
        response += "4️⃣ - Beginner Guide\n"
        response += "✅ - Generate Full Blog from Selected Outline"
        
        # Edit the message
        session.patch(edit_url, json={"content": response[:1950]}, timeout=15)
        
    except Exception as e:
        # Fallback if generation fails
        session.patch(edit_url, json={"content": f"⚠️ **SoundSwap AI Error:** {str(e)[:1500]}"})

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

        # Run in background thread
        import threading
        thread = threading.Thread(target=lambda: asyncio.run(generate_and_edit(token, context_text)))
        thread.start()

        # Send 'Thinking...' state immediately
        return {"type": 5}

    return {"type": 4, "data": {"content": "Unknown Interaction"}}

@app.get("/api/scout")
async def daily_scout():
    """Triggered by Vercel Cron to post daily reports with 4 outlines."""
    
    full_report = f"🎸 **SoundSwap Daily Intel + 4 Blog Outlines** ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    
    for query in NICHE_QUERIES:
        try:
            # Get SERP data
            serp_data = get_serp_data(query)
            
            # Generate outlines
            outlines = await generate_four_outlines(query, serp_data)
            
            # Build section
            section = f"📡 **TOPIC: {query.upper()}**\n"
            section += f"🔢 Trend Score: {serp_data['score']}/100 ({serp_data['status']})\n"
            section += f"🔗 Source: {serp_data['link']}\n\n"
            
            section += "**4 BLOG OUTLINE APPROACHES:**\n"
            for i, outline in enumerate(outlines, 1):
                section += f"{i}. **{outline['type']}** {outline['sentiment']}\n"
            
            section += "\n**SENTIMENT BREAKDOWN:**\n"
            for outline in outlines:
                section += f"• {outline['type'][:15]}...: {outline['sentiment']}\n"
            
            section += "\n" + "─" * 40 + "\n\n"
            
            full_report += section
            
        except Exception as e:
            full_report += f"❌ Error for '{query}': {str(e)[:100]}\n\n"
    
    # Send to Discord
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    
    # Split message if too long
    max_length = 1900
    for i in range(0, len(full_report), max_length):
        chunk = full_report[i:i + max_length]
        requests.post(url, headers=headers, json={"content": chunk})
        time.sleep(1)  # Avoid rate limiting
    
    return {"status": "sent", "topics": len(NICHE_QUERIES)}