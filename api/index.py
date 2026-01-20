import os
import json
import requests
import time
from typing import List, Dict, Tuple
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
import google.generativeai as genai
from serpapi import Client
from textblob import TextBlob
from datetime import datetime
import asyncio
import threading

app = FastAPI()

# --- CONFIG ---
PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
APP_ID = os.getenv("DISCORD_APP_ID")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 4 High-impact topics for daily scout
NICHE_QUERIES = [
    "latest music production gear releases 2026",
    "breaking AI audio tools for artists",
    "independent music marketing trends 2026",
    "music streaming industry news today"
]

# Outline types with emojis
OUTLINE_TYPES = [
    {"name": "Technical Deep Dive", "emoji": "🔬", "description": "Specifications, features, technical analysis"},
    {"name": "Creative Applications", "emoji": "🎨", "description": "Practical uses for artists and producers"},
    {"name": "Industry Impact", "emoji": "📈", "description": "Market trends and business implications"},
    {"name": "Beginner-Friendly Guide", "emoji": "👶", "description": "Simplified explanations for newcomers"}
]

def verify_discord_signature(body: str, signature: str, timestamp: str):
    """Verify Discord interaction signature."""
    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid request signature")

def analyze_sentiment(text: str) -> Tuple[str, float]:
    """Analyze sentiment using TextBlob."""
    try:
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
    except Exception:
        return "NEUTRAL 😐", 0.0

def get_trend_score(keyword: str) -> int:
    """Get trend score from Google Trends."""
    try:
        client = Client(api_key=SERPAPI_KEY)
        results = client.search({
            "engine": "google_trends",
            "q": keyword,
            "data_type": "TIMESERIES",
            "date": "now 7-d"
        })
        timeseries = results.get("interest_over_time", {}).get("timeline_data", [])
        return int(timeseries[-1].get("values")[0].get("value")) if timeseries else 50
    except Exception as e:
        print(f"Trend score error for '{keyword}': {e}")
        return 50

def get_serp_data(query: str) -> Dict:
    """Fetch SERP data including related questions."""
    try:
        score = get_trend_score(query)
        client = Client(api_key=SERPAPI_KEY)
        
        results = client.search({
            "engine": "google",
            "q": query,
            "tbs": "qdr:d",
            "api_key": SERPAPI_KEY,
            "num": 3
        })
        
        organic = results.get("organic_results", [])
        related_questions = results.get("related_questions", [])[:3]
        questions = [q.get('question') for q in related_questions if q.get('question')]
        
        first_result = organic[0] if organic else {}
        
        status = "🔥 VIRAL" if score > 75 else "📈 TRENDING" if score > 50 else "📊 STEADY"
        
        return {
            "query": query,
            "score": score,
            "link": first_result.get('link', 'No link found'),
            "title": first_result.get('title', ''),
            "snippet": first_result.get('snippet', ''),
            "questions": questions,
            "status": status
        }
    except Exception as e:
        print(f"SERP data error for '{query}': {e}")
        return {
            "query": query,
            "score": 50,
            "link": "No link found",
            "title": "",
            "snippet": "",
            "questions": [],
            "status": "📊 STEADY"
        }

async def generate_four_outlines(context: str, serp_data: Dict) -> List[Dict]:
    """Generate 4 distinct blog outline approaches with sentiment analysis."""
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    CONTEXT: {context}
    
    SERP DATA:
    - Topic: {serp_data['query']}
    - Trend Score: {serp_data['score']}/100 ({serp_data['status']})
    - Source Title: {serp_data['title']}
    - Source Snippet: {serp_data['snippet'][:200] if serp_data['snippet'] else 'N/A'}
    - People Also Ask: {', '.join(serp_data['questions']) if serp_data['questions'] else 'No questions found'}
    
    TASK: Generate 4 DISTINCT blog outline approaches for SoundSwap (music production platform):
    
    1. **Technical Deep Dive**
       - Focus on specifications, features, technical analysis
       - Target: Experienced producers, gear enthusiasts
       - Tone: Professional, detailed, analytical
    
    2. **Creative Applications**
       - How artists/producers can practically use this
       - Target: Creative professionals, music makers
       - Tone: Inspirational, practical, hands-on
    
    3. **Industry Impact**
       - Market trends, business implications, future predictions
       - Target: Industry professionals, investors, entrepreneurs
       - Tone: Strategic, forward-looking, authoritative
    
    4. **Beginner-Friendly Guide**
       - Simplified explanation for newcomers
       - Target: New producers, hobbyists, students
       - Tone: Friendly, educational, encouraging
    
    FORMAT EACH OUTLINE AS:
    [TYPE: Technical Deep Dive]
    Audience: [target audience]
    Tone: [tone with sentiment analysis]
    Key Points:
    - [Point 1]
    - [Point 2]
    - [Point 3]
    SEO Keywords: [3-5 keywords]
    Reading Time: [X minutes]
    
    Make each outline unique, actionable, and based on the provided data.
    """
    
    try:
        response = model.generate_content(prompt)
        outlines_text = response.text
        
        # Parse the response into structured outlines
        outlines = []
        current_outline = {}
        lines = outlines_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('[TYPE:'):
                # Save previous outline
                if current_outline:
                    # Analyze sentiment before adding
                    content_str = json.dumps(current_outline)
                    sentiment_label, sentiment_score = analyze_sentiment(content_str)
                    current_outline["sentiment"] = sentiment_label
                    current_outline["sentiment_score"] = sentiment_score
                    outlines.append(current_outline)
                
                # Start new outline
                outline_type = line.replace('[TYPE:', '').replace(']', '').strip()
                current_outline = {
                    "type": outline_type,
                    "audience": "",
                    "tone": "",
                    "key_points": [],
                    "seo_keywords": [],
                    "reading_time": "",
                    "content": line + "\n"
                }
            elif line.startswith('Audience:'):
                current_outline["audience"] = line.replace('Audience:', '').strip()
                current_outline["content"] += line + "\n"
            elif line.startswith('Tone:'):
                current_outline["tone"] = line.replace('Tone:', '').strip()
                current_outline["content"] += line + "\n"
            elif line.startswith('Key Points:'):
                current_outline["content"] += line + "\n"
            elif line.startswith('- ') and 'key_points' in current_outline:
                point = line[2:].strip()
                current_outline["key_points"].append(point)
                current_outline["content"] += line + "\n"
            elif line.startswith('SEO Keywords:'):
                keywords = line.replace('SEO Keywords:', '').strip()
                current_outline["seo_keywords"] = [k.strip() for k in keywords.split(',')]
                current_outline["content"] += line + "\n"
            elif line.startswith('Reading Time:'):
                current_outline["reading_time"] = line.replace('Reading Time:', '').strip()
                current_outline["content"] += line + "\n"
            elif current_outline:
                current_outline["content"] += line + "\n"
        
        # Add the last outline
        if current_outline:
            content_str = json.dumps(current_outline)
            sentiment_label, sentiment_score = analyze_sentiment(content_str)
            current_outline["sentiment"] = sentiment_label
            current_outline["sentiment_score"] = sentiment_score
            outlines.append(current_outline)
        
        # Ensure we have exactly 4 outlines
        while len(outlines) < 4:
            outline_type = OUTLINE_TYPES[len(outlines)]["name"]
            emoji = OUTLINE_TYPES[len(outlines)]["emoji"]
            
            outlines.append({
                "type": outline_type,
                "emoji": emoji,
                "audience": "SoundSwap users",
                "tone": "Professional",
                "key_points": ["Analysis pending"],
                "seo_keywords": ["music", "production", "gear"],
                "reading_time": "5 minutes",
                "sentiment": "NEUTRAL 😐",
                "sentiment_score": 0.0,
                "content": f"[TYPE: {outline_type}]\nGenerated as fallback"
            })
        
        # Add emojis to each outline
        for i, outline in enumerate(outlines[:4]):
            if i < len(OUTLINE_TYPES):
                outline["emoji"] = OUTLINE_TYPES[i]["emoji"]
        
        return outlines[:4]
        
    except Exception as e:
        print(f"Outline generation error: {e}")
        # Fallback outlines
        outlines = []
        for i, outline_type in enumerate(OUTLINE_TYPES):
            outlines.append({
                "type": outline_type["name"],
                "emoji": outline_type["emoji"],
                "audience": "SoundSwap users",
                "tone": "Professional",
                "key_points": [f"{outline_type['description']} point"],
                "sentiment": "POSITIVE 😊" if i % 2 == 0 else "NEUTRAL 😐",
                "sentiment_score": 0.3 if i % 2 == 0 else 0.1,
                "content": f"{outline_type['description']} for {context[:50]}..."
            })
        return outlines

def edit_discord_message(token: str, content: str = None, embeds: List[Dict] = None):
    """Edit a Discord message via webhook."""
    edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
    try:
        data = {}
        if content:
            data["content"] = content[:1950]
        if embeds:
            data["embeds"] = embeds[:10]  # Discord limit
        
        requests.patch(edit_url, json=data, timeout=10)
        return True
    except Exception as e:
        print(f"Failed to edit Discord message: {e}")
        return False

async def process_outline_generation(token: str, context_text: str):
    """Process outline generation and update Discord."""
    try:
        # Create initial response to show we're working
        edit_discord_message(token, f"🎸 **SoundSwap AI is thinking...**\nGenerating 4 blog outlines for:\n```{context_text[:100]}...```")
        
        # Get SERP data
        serp_data = get_serp_data(context_text[:100])
        
        # Generate 4 outlines
        outlines = await generate_four_outlines(context_text, serp_data)
        
        # Build Discord response with embeds for better formatting
        embeds = []
        
        # Main embed
        main_embed = {
            "title": "🎸 SoundSwap AI - 4 Blog Outlines",
            "description": f"**Topic:** {serp_data['query'][:200]}\n**Trend Score:** {serp_data['score']}/100 {serp_data['status']}",
            "color": 0x5865F2,  # Discord blurple
            "fields": [],
            "footer": {
                "text": f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            },
            "thumbnail": {
                "url": "https://cdn.discordapp.com/emojis/1108096873328418836.webp?size=96&quality=lossless"
            }
        }
        
        # Add each outline as a field
        for i, outline in enumerate(outlines, 1):
            emoji = outline.get("emoji", "📝")
            key_points = outline.get('key_points', [])
            points_text = "\n".join([f"• {p[:50]}..." for p in key_points[:2]]) if key_points else "• Detailed analysis"
            
            field_value = f"**Audience:** {outline.get('audience', 'Producers')}\n"
            field_value += f"**Tone:** {outline.get('tone', 'Professional')} {outline.get('sentiment', 'NEUTRAL 😐')}\n"
            field_value += f"**Reading Time:** {outline.get('reading_time', '5-7 min')}\n"
            if points_text:
                field_value += f"**Key Points:**\n{points_text}"
            
            main_embed["fields"].append({
                "name": f"{emoji} {i}. {outline['type']}",
                "value": field_value[:1024],  # Discord field value limit
                "inline": False
            })
        
        embeds.append(main_embed)
        
        # Sentiment summary embed
        positive_count = sum(1 for o in outlines if "POSITIVE" in o.get('sentiment', ''))
        negative_count = sum(1 for o in outlines if "NEGATIVE" in o.get('sentiment', ''))
        neutral_count = len(outlines) - positive_count - negative_count
        
        sentiment_embed = {
            "title": "📈 Real-time Sentiment Analysis",
            "color": 0x57F287 if positive_count >= negative_count else 0xED4245,
            "fields": [],
            "description": f"Overall sentiment: {positive_count} positive, {neutral_count} neutral, {negative_count} negative"
        }
        
        for outline in outlines:
            sentiment_score = outline.get('sentiment_score', 0)
            
            # Create visual sentiment bar
            if sentiment_score > 0.2:
                bar = "🟩" * 3 + "⬜" * 2
                label = "Strong Positive"
            elif sentiment_score > 0:
                bar = "🟩" * 2 + "⬜" * 3
                label = "Positive"
            elif sentiment_score < -0.2:
                bar = "🟥" * 3 + "⬜" * 2
                label = "Strong Negative"
            elif sentiment_score < 0:
                bar = "🟥" * 2 + "⬜" * 3
                label = "Negative"
            else:
                bar = "🟨" * 3 + "⬜" * 2
                label = "Neutral"
            
            sentiment_embed["fields"].append({
                "name": f"{outline['emoji']} {outline['type'][:15]}",
                "value": f"`{sentiment_score:+.2f}` {label}\n{bar}",
                "inline": True
            })
        
        embeds.append(sentiment_embed)
        
        # Action embed
        action_embed = {
            "title": "🎯 Next Steps",
            "description": "**React with:**\n1️⃣ - Technical Deep Dive\n2️⃣ - Creative Applications\n3️⃣ - Industry Impact\n4️⃣ - Beginner Guide\n\n**Then react with:** ✅ - Generate full blog from selected outline",
            "color": 0xFEE75C,  # Yellow
            "footer": {
                "text": "SoundSwap AI | Right-click → Copy Message Link to save"
            }
        }
        
        embeds.append(action_embed)
        
        # Source info embed
        if serp_data['link'] != 'No link found':
            source_embed = {
                "title": "🔍 Source Information",
                "description": f"[{serp_data['title'][:100]}...]({serp_data['link']})\n\n{serp_data['snippet'][:200]}...",
                "color": 0x95A5A6,
                "fields": [
                    {
                        "name": "📊 Trend Data",
                        "value": f"Score: {serp_data['score']}/100\nStatus: {serp_data['status']}",
                        "inline": True
                    },
                    {
                        "name": "❓ People Also Ask",
                        "value": "\n".join([f"• {q[:50]}..." for q in serp_data['questions'][:2]]) if serp_data['questions'] else "No questions found",
                        "inline": True
                    }
                ]
            }
            embeds.append(source_embed)
        
        # Update the Discord message with embeds
        success = edit_discord_message(
            token,
            f"✅ **Generated 4 Blog Outlines + Sentiment Analysis**\nBased on: {context_text[:100]}...",
            embeds
        )
        
        if not success:
            # Fallback to simple text if embeds fail
            simple_response = f"🎸 **SoundSwap AI - 4 Blog Outlines**\n\n"
            simple_response += f"**Topic:** {serp_data['query']}\n"
            simple_response += f"**Trend Score:** {serp_data['score']}/100 {serp_data['status']}\n\n"
            
            for i, outline in enumerate(outlines, 1):
                simple_response += f"{i}. **{outline['type']}** {outline.get('sentiment', '')}\n"
                simple_response += f"   Audience: {outline.get('audience', '')}\n"
                simple_response += f"   Tone: {outline.get('tone', '')}\n\n"
            
            simple_response += "**React with 1️⃣-4️⃣ to select outline, then ✅ for full blog**"
            edit_discord_message(token, simple_response[:1950])
        
    except Exception as e:
        print(f"Outline generation error: {e}")
        edit_discord_message(token, f"⚠️ **SoundSwap AI Error:** {str(e)[:1500]}")

@app.post("/api/interactions")
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
        
        if command_name == "outlines":
            # Get topic from command options or referenced message
            options = command_data.get("options", [])
            context_text = ""
            
            # Check for topic in command options
            for opt in options:
                if opt.get("name") == "topic":
                    context_text = opt.get("value", "")
                    break
            
            # If no topic provided, try to get referenced message
            if not context_text:
                resolved = command_data.get("resolved", {})
                messages = resolved.get("messages", {})
                if messages:
                    msg_id = list(messages.keys())[0]
                    context_text = messages[msg_id].get("content", "")
            
            # If still no context, use a default
            if not context_text:
                context_text = "latest music production trends and AI audio tools"
            
            # Start background task for outline generation
            thread = threading.Thread(
                target=lambda: asyncio.run(process_outline_generation(token, context_text))
            )
            thread.start()
            
            # Return deferred response (shows "Bot is thinking...")
            return {"type": 5}
        
        return {"type": 4, "data": {"content": "❌ Unknown command"}}

    # 3. Handle message components (like button clicks)
    if data.get("type") == 3:
        # This would handle reactions/buttons (like selecting an outline)
        return {"type": 4, "data": {"content": "Component interaction received"}}

    return {"type": 4, "data": {"content": "Unknown Interaction"}}

@app.get("/api/scout")
async def daily_scout():
    """Triggered by Vercel Cron to post daily reports with 4 outlines."""
    
    full_report = f"🎸 **SoundSwap Daily Intel + 4 Blog Outlines** ({datetime.now().strftime('%Y-%m-%d')})\n"
    full_report += "*Use `/outlines [topic]` to generate 4 blog approaches for any topic!*\n\n"
    
    for query in NICHE_QUERIES:
        try:
            # Get SERP data
            serp_data = get_serp_data(query)
            
            # Generate outlines
            outlines = await generate_four_outlines(query, serp_data)
            
            # Build section
            section = f"📡 **TOPIC: {query.upper()}**\n"
            section += f"🔢 Trend Score: {serp_data['score']}/100 {serp_data['status']}\n"
            section += f"🔗 Source: {serp_data['link'][:80]}...\n\n"
            
            section += "**4 BLOG APPROACHES:**\n"
            for i, outline in enumerate(outlines, 1):
                emoji = outline.get("emoji", "📝")
                sentiment = outline.get('sentiment', 'NEUTRAL 😐').split()[0]
                section += f"{emoji} {i}. **{outline['type']}** ({sentiment})\n"
            
            # Sentiment analysis
            positive_count = sum(1 for o in outlines if "POSITIVE" in o.get('sentiment', ''))
            negative_count = sum(1 for o in outlines if "NEGATIVE" in o.get('sentiment', ''))
            
            section += f"\n**📊 SENTIMENT:** "
            if positive_count > negative_count:
                section += f"Mostly Positive ({positive_count}/4 outlines)"
            elif negative_count > positive_count:
                section += f"Mostly Negative ({negative_count}/4 outlines)"
            else:
                section += "Neutral/Mixed"
            
            section += "\n\n" + "─" * 40 + "\n\n"
            
            full_report += section
            
        except Exception as e:
            full_report += f"❌ Error for '{query}': {str(e)[:80]}...\n\n"
    
    # Add footer with instructions
    full_report += "\n🎯 **How to use:**\n"
    full_report += "1. Reply to this message with `/outlines`\n"
    full_report += "2. Or type `/outlines [your topic]` in any channel\n"
    full_report += "3. Get 4 blog outlines + sentiment analysis instantly!"
    
    # Send to Discord
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Split message if too long
    max_length = 1900
    chunks = [full_report[i:i + max_length] for i in range(0, len(full_report), max_length)]
    
    for i, chunk in enumerate(chunks):
        payload = {"content": chunk}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"Failed to send chunk {i}: {response.status_code} - {response.text}")
            time.sleep(1)  # Avoid rate limiting
        except Exception as e:
            print(f"Error sending chunk {i}: {e}")
    
    return {"status": "sent", "topics": len(NICHE_QUERIES), "chunks": len(chunks)}

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SoundSwap AI",
        "version": "2.0",
        "features": [
            "4 blog outlines generation",
            "Real-time sentiment analysis",
            "Trend scoring",
            "Daily automated reports",
            "Discord slash commands"
        ],
        "endpoints": [
            "POST /api/interactions",
            "GET /api/scout"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)