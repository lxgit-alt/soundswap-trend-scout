import os
import json
import requests
import time
import asyncio
import threading
import concurrent.futures
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from nacl.signing import VerifyKey
import google.generativeai as genai
from serpapi import Client
from textblob import TextBlob
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Store daily topics for selection (in-memory, consider Redis for production)
daily_topics_store = {}
processing_tasks = {}

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
    """Get trend score from Google Trends with timeout."""
    try:
        client = Client(api_key=SERPAPI_KEY)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(client.search, {
                "engine": "google_trends",
                "q": keyword,
                "data_type": "TIMESERIES",
                "date": "now 7-d"
            })
            results = future.result(timeout=15)  # 15-second timeout
        
        timeseries = results.get("interest_over_time", {}).get("timeline_data", [])
        return int(timeseries[-1].get("values")[0].get("value")) if timeseries else 50
    except Exception as e:
        logger.error(f"Trend score error for '{keyword}': {e}")
        return 50

def get_serp_data(query: str) -> Dict:
    """Fetch SERP data including related questions with timeout handling."""
    try:
        score = get_trend_score(query)
        client = Client(api_key=SERPAPI_KEY)
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(client.search, {
                "engine": "google",
                "q": query,
                "tbs": "qdr:d",
                "api_key": SERPAPI_KEY,
                "num": 5
            })
            results = future.result(timeout=20)  # 20-second timeout
        
        organic = results.get("organic_results", [])
        related_questions = results.get("related_questions", [])[:5]
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
            "status": status,
            "total_results": results.get("search_information", {}).get("total_results", 0)
        }
    except concurrent.futures.TimeoutError:
        logger.error(f"SERP data timeout for '{query}'")
        return {
            "query": query,
            "score": 50,
            "link": "No link found",
            "title": "",
            "snippet": "",
            "questions": [],
            "status": "📊 STEADY",
            "total_results": 0
        }
    except Exception as e:
        logger.error(f"SERP data error for '{query}': {e}")
        return {
            "query": query,
            "score": 50,
            "link": "No link found",
            "title": "",
            "snippet": "",
            "questions": [],
            "status": "📊 STEADY",
            "total_results": 0
        }

def organize_paa_into_narrative(questions: List[str]) -> List[str]:
    """Logic-based approach to organize PAA questions into a narrative flow."""
    if not questions:
        return []
    
    # Categorize questions by intent
    technical, creative, beginner, comparison = [], [], [], []
    
    for q in questions:
        q_lower = q.lower()
        if any(word in q_lower for word in ['how to', 'tutorial', 'step by step', 'guide']):
            beginner.append(q)
        elif any(word in q_lower for word in ['best', 'vs', 'compare', 'difference']):
            comparison.append(q)
        elif any(word in q_lower for word in ['work', 'use', 'create', 'make']):
            creative.append(q)
        else:
            technical.append(q)
    
    # Create narrative flow: Beginner → Creative → Technical → Comparison
    narrative_flow = []
    
    if beginner:
        narrative_flow.extend(beginner[:2])
    if creative:
        narrative_flow.extend(creative[:2])
    if technical:
        narrative_flow.extend(technical[:2])
    if comparison:
        narrative_flow.extend(comparison[:1])
    
    # If we still have space, add more
    max_questions = 4
    while len(narrative_flow) < max_questions and questions:
        for q in questions:
            if q not in narrative_flow:
                narrative_flow.append(q)
                break
    
    return narrative_flow[:max_questions]

async def generate_semantic_blog_with_progress(token: str, topic_data: Dict, selected_outline_type: str):
    """Generate blog with progress updates."""
    try:
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        
        # Send initial progress
        requests.patch(edit_url, json={
            "content": f"⚡ **Step 1/4: Analyzing PAA Questions...**\n\nTopic: {topic_data['query'][:50]}..."
        }, timeout=10)
        
        # Organize PAA
        organized_paa = organize_paa_into_narrative(topic_data['questions'])
        
        requests.patch(edit_url, json={
            "content": f"✅ **Step 2/4: PAA Analysis Complete**\n{len(organized_paa)} questions organized\n\n⚡ **Step 3/4: Generating blog content...**"
        }, timeout=10)
        
        # Generate blog
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Generate a semantic SEO blog post with these requirements:
        
        TOPIC: {topic_data['query']}
        TREND SCORE: {topic_data['score']}/100 ({topic_data['status']})
        OUTLINE: {selected_outline_type}
        
        PAA QUESTIONS (convert to H3 headers):
        {chr(10).join([f'- {q}' for q in organized_paa])}
        
        Structure:
        1. H1 with primary keyword
        2. 3-4 H2 sections
        3. Each PAA as H3 with 50-100 word answer
        4. SEO optimized (800-1000 words)
        5. Include meta description and keywords
        
        Write now:
        """
        
        response = model.generate_content(prompt)
        blog_content = response.text
        
        # Add metadata
        seo_section = f"""
        --- SEO METADATA ---
        Primary Keyword: {topic_data['query'].split()[0]} {topic_data['query'].split()[-1]}
        Word Count: {len(blog_content.split())}
        PAA Questions Used: {len(organized_paa)}
        Target Featured Snippet: Yes
        Schema Markup: HowTo + FAQPage
        ---
        """
        
        return seo_section + "\n\n" + blog_content
        
    except Exception as e:
        logger.error(f"Blog generation error: {e}")
        raise

async def generate_four_outlines_with_progress(token: str, context: str, serp_data: Dict):
    """Generate 4 outlines with progress updates."""
    try:
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        
        requests.patch(edit_url, json={
            "content": f"⚡ **Analyzing topic sentiment and trends...**\n\n{serp_data['query'][:50]}..."
        }, timeout=10)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Generate 4 distinct blog outlines for this context:
        
        CONTEXT: {context}
        TREND: {serp_data['score']}/100 ({serp_data['status']})
        SOURCE: {serp_data['title']}
        
        1. Technical Deep Dive
        2. Creative Applications  
        3. Industry Impact
        4. Beginner-Friendly Guide
        
        For each include: Audience, Tone, Key Points, SEO Keywords, Reading Time
        
        Format as:
        [TYPE: Name]
        Audience: [target]
        Tone: [tone]
        Key Points:
        - [point 1]
        - [point 2]
        - [point 3]
        SEO Keywords: [keyword1, keyword2, keyword3]
        Reading Time: [X minutes]
        """
        
        response = model.generate_content(prompt)
        outlines_text = response.text
        
        # Parse and add sentiment
        outlines = []
        current_outline = {}
        lines = outlines_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('[TYPE:'):
                if current_outline:
                    sentiment_label, sentiment_score = analyze_sentiment(json.dumps(current_outline))
                    current_outline["sentiment"] = sentiment_label
                    current_outline["sentiment_score"] = sentiment_score
                    outlines.append(current_outline)
                
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
            elif line.startswith('Tone:'):
                current_outline["tone"] = line.replace('Tone:', '').strip()
            elif line.startswith('Key Points:'):
                pass  # Skip header
            elif line.startswith('- ') and 'key_points' in current_outline:
                current_outline["key_points"].append(line[2:].strip())
            elif line.startswith('SEO Keywords:'):
                current_outline["seo_keywords"] = [k.strip() for k in line.replace('SEO Keywords:', '').split(',')]
            elif line.startswith('Reading Time:'):
                current_outline["reading_time"] = line.replace('Reading Time:', '').strip()
        
        # Add last outline
        if current_outline:
            sentiment_label, sentiment_score = analyze_sentiment(json.dumps(current_outline))
            current_outline["sentiment"] = sentiment_label
            current_outline["sentiment_score"] = sentiment_score
            outlines.append(current_outline)
        
        # Add emojis
        for i, outline in enumerate(outlines[:4]):
            if i < len(OUTLINE_TYPES):
                outline["emoji"] = OUTLINE_TYPES[i]["emoji"]
        
        # Ensure 4 outlines
        while len(outlines) < 4:
            outline_type = OUTLINE_TYPES[len(outlines)]["name"]
            outlines.append({
                "type": outline_type,
                "emoji": OUTLINE_TYPES[len(outlines)]["emoji"],
                "sentiment": "NEUTRAL 😐",
                "sentiment_score": 0.0,
                "content": f"{outline_type} outline"
            })
        
        return outlines[:4]
        
    except Exception as e:
        logger.error(f"Outline generation error: {e}")
        raise

async def process_outline_generation(token: str, context_text: str):
    """Process outline generation with timeout handling."""
    try:
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        
        # Get SERP data
        requests.patch(edit_url, json={
            "content": f"🔍 **Gathering trend data for:**\n```{context_text[:80]}...```"
        }, timeout=10)
        
        serp_data = get_serp_data(context_text[:100])
        
        # Generate outlines
        requests.patch(edit_url, json={
            "content": f"✅ **Trend Analysis Complete**\nScore: {serp_data['score']}/100 {serp_data['status']}\n\n⚡ **Generating 4 blog outlines...**"
        }, timeout=10)
        
        outlines = await generate_four_outlines_with_progress(token, context_text, serp_data)
        
        # Build response
        response = f"🎸 **SoundSwap AI - 4 Blog Outlines**\n\n"
        response += f"**Topic:** {serp_data['query']}\n"
        response += f"**Trend:** {serp_data['score']}/100 {serp_data['status']}\n"
        response += f"**Source:** {serp_data['link'][:50]}...\n\n"
        
        response += "**4 BLOG APPROACHES:**\n\n"
        for i, outline in enumerate(outlines, 1):
            emoji = outline.get("emoji", "📝")
            response += f"{i}. {emoji} **{outline['type']}** {outline['sentiment']}\n"
            response += f"   Audience: {outline.get('audience', 'Producers')}\n"
            response += f"   Reading: {outline.get('reading_time', '5-7 min')}\n\n"
        
        response += "**📊 SENTIMENT ANALYSIS:**\n"
        for outline in outlines:
            bar = "🟢" * 3 if "POSITIVE" in outline['sentiment'] else "🔴" * 3 if "NEGATIVE" in outline['sentiment'] else "🟡" * 3
            response += f"• {outline['type'][:15]}...: {bar} ({outline['sentiment_score']:.2f})\n"
        
        response += "\n**🎯 Use `/blog` for full semantic SEO blog with PAA → H3 headers!**"
        
        requests.patch(edit_url, json={"content": response[:1950]}, timeout=10)
        
    except Exception as e:
        logger.error(f"Process outline error: {e}")
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        requests.patch(edit_url, json={
            "content": f"⚠️ **Error:** {str(e)[:500]}"
        }, timeout=10)

async def process_daily_topics_selection(token: str):
    """Show daily topics with efficient async processing."""
    try:
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        
        requests.patch(edit_url, json={
            "content": "⚡ **Fetching today's trending topics...**"
        }, timeout=10)
        
        # Fetch all topics in parallel
        daily_topics = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(get_serp_data, query) for query in NICHE_QUERIES]
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                try:
                    topic = future.result(timeout=25)
                    daily_topics.append(topic)
                    
                    # Send progress update
                    if i % 2 == 0 or i == len(NICHE_QUERIES):
                        requests.patch(edit_url, json={
                            "content": f"📊 **Topic {i}/{len(NICHE_QUERIES)} analyzed**\n\nGathering more data..."
                        }, timeout=10)
                        
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Topic {i} timed out")
                    daily_topics.append({
                        "query": NICHE_QUERIES[i-1],
                        "score": 50,
                        "link": "No link found",
                        "questions": [],
                        "status": "📊 STEADY"
                    })
        
        # Store topics
        daily_topics_store[token] = daily_topics
        
        # Build response
        response = f"🎸 **SOUNDSWAP DAILY TOPICS**\n📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
        response += "**Choose ONE for today's semantic SEO blog:**\n\n"
        
        for i, topic in enumerate(daily_topics, 1):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][i-1]
            response += f"{emoji} **{topic['query'].upper()}**\n"
            response += f"   📊 Trend: {topic['score']}/100 {topic['status']}\n"
            response += f"   🔗 Source: {topic['link'][:40]}...\n"
            if topic['questions']:
                response += f"   ❓ PAA: {topic['questions'][0][:35]}...\n"
            response += "\n"
        
        response += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        response += "**Reply with your choice (1-4)**\n"
        response += "*Only 1 blog per day for maximum SEO impact*"
        
        requests.patch(edit_url, json={"content": response[:1950]}, timeout=10)
        
    except Exception as e:
        logger.error(f"Topic selection error: {e}")
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        requests.patch(edit_url, json={
            "content": f"⚠️ **Error loading topics:** {str(e)[:500]}"
        }, timeout=10)

async def process_topic_outlines(token: str, topic_index: int):
    """Process topic outlines."""
    try:
        daily_topics = daily_topics_store.get(token)
        if not daily_topics or topic_index < 0 or topic_index >= len(daily_topics):
            edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
            requests.patch(edit_url, json={
                "content": "❌ Topic not found. Use `/blog` to start over."
            }, timeout=10)
            return
        
        selected_topic = daily_topics[topic_index]
        
        # Store for blog generation
        if 'outlines_store' not in daily_topics_store:
            daily_topics_store['outlines_store'] = {}
        
        # Generate outlines
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        requests.patch(edit_url, json={
            "content": f"⚡ **Generating 4 outline approaches for:**\n```{selected_topic['query'][:60]}...```"
        }, timeout=10)
        
        outlines = await generate_four_outlines_with_progress(token, selected_topic['query'], selected_topic)
        
        daily_topics_store['outlines_store'][token] = {
            'topic': selected_topic,
            'outlines': outlines,
            'selected_topic_index': topic_index
        }
        
        # Build response
        response = f"📝 **4 OUTLINE APPROACHES**\n\n"
        response += f"**Topic:** {selected_topic['query'][:50]}...\n"
        response += f"**Trend:** {selected_topic['score']}/100 {selected_topic['status']}\n\n"
        
        for i, outline in enumerate(outlines, 1):
            emoji = ["🔬", "🎨", "📈", "👶"][i-1]
            response += f"{i}. {emoji} **{outline['type']}** {outline['sentiment']}\n"
            if outline.get('key_points'):
                response += f"   Key Points: {', '.join(outline['key_points'][:2])}\n"
            response += f"   Audience: {outline.get('audience', 'Producers')}\n\n"
        
        response += "**Reply with outline choice (1-4)**\n"
        response += "*Selected: Topic {}*".format(topic_index + 1)
        
        requests.patch(edit_url, json={"content": response[:1950]}, timeout=10)
        
    except Exception as e:
        logger.error(f"Topic outlines error: {e}")
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        requests.patch(edit_url, json={
            "content": f"⚠️ **Error generating outlines:** {str(e)[:500]}"
        }, timeout=10)

async def generate_final_blog(token: str, outline_index: int):
    """Generate final blog."""
    try:
        outlines_data = daily_topics_store.get('outlines_store', {}).get(token)
        if not outlines_data:
            edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
            requests.patch(edit_url, json={
                "content": "❌ Session expired. Use `/blog` to start over."
            }, timeout=10)
            return
        
        topic_data = outlines_data['topic']
        outlines = outlines_data['outlines']
        
        if outline_index < 0 or outline_index >= len(outlines):
            edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
            requests.patch(edit_url, json={
                "content": "❌ Invalid outline selection"
            }, timeout=10)
            return
        
        selected_outline = outlines[outline_index]
        
        # Generate blog
        blog_content = await generate_semantic_blog_with_progress(token, topic_data, selected_outline['type'])
        
        # Split and send
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        
        header = f"🎸 **SOUNDSWAP SEMANTIC SEO BLOG**\n"
        header += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
        header += f"🎯 Topic: {topic_data['query']}\n"
        header += f"📊 Trend: {topic_data['score']}/100 {topic_data['status']}\n"
        header += f"📝 Style: {selected_outline['type']}\n"
        header += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Send in chunks
        chunks = [blog_content[i:i+1900] for i in range(0, len(blog_content), 1900)]
        
        # Send header as first message
        requests.patch(edit_url, json={"content": header[:1950]}, timeout=10)
        
        # Send chunks as follow-ups
        followup_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}"
        for i, chunk in enumerate(chunks):
            try:
                requests.post(followup_url, json={"content": chunk}, timeout=10)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Chunk {i} error: {e}")
        
        # Send completion message
        requests.post(followup_url, json={
            "content": "✅ **Blog generated!** PAA → H3 integration complete. Ready for publishing!"
        }, timeout=10)
        
        # Cleanup
        if token in daily_topics_store:
            del daily_topics_store[token]
        if 'outlines_store' in daily_topics_store and token in daily_topics_store['outlines_store']:
            del daily_topics_store['outlines_store'][token]
            
    except Exception as e:
        logger.error(f"Final blog error: {e}")
        edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
        requests.patch(edit_url, json={
            "content": f"⚠️ **Error generating blog:** {str(e)[:500]}"
        }, timeout=10)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SoundSwap AI Blog Generator",
        "version": "3.0 - Fluid Compute",
        "max_duration": "300 seconds",
        "memory": "1024 MB",
        "endpoints": [
            "POST /api/interactions - Discord webhook",
            "GET /api/scout - Daily scout",
            "POST /api/interactions/followup - Topic selection"
        ]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(daily_topics_store)
    }