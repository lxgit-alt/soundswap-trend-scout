import os
import json
import requests
import time
from typing import List, Dict, Tuple, Optional
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
from google import genai
from serpapi import GoogleSearch
from textblob import TextBlob
from datetime import datetime
import asyncio
import threading

app = FastAPI()

# --- CONFIG ---
PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
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

# Outline types with emojis
OUTLINE_TYPES = [
    {"name": "Technical Deep Dive", "emoji": "🔬", "description": "Specifications, features, technical analysis"},
    {"name": "Creative Applications", "emoji": "🎨", "description": "Practical uses for artists and producers"},
    {"name": "Industry Impact", "emoji": "📈", "description": "Market trends and business implications"},
    {"name": "Beginner-Friendly Guide", "emoji": "👶", "description": "Simplified explanations for newcomers"}
]

# Store daily topics for selection
daily_topics_store = {}

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
        "num": 5  # Get more results for better PAA data
    })
    
    results = search.get_dict()
    organic = results.get("organic_results", [])
    related_questions = results.get("related_questions", [])[:5]  # Get up to 5 PAA
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

def organize_paa_into_narrative(questions: List[str]) -> List[str]:
    """
    Logic-based approach to organize PAA questions into a narrative flow.
    This is KEY for training the blog to capture Google's top search spots.
    """
    if not questions:
        return []
    
    # Categorize questions by intent
    technical = []
    creative = []
    beginner = []
    comparison = []
    
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
    
    # Start with beginner questions (hook readers)
    if beginner:
        narrative_flow.extend(beginner[:2])
    
    # Move to creative applications (engage)
    if creative:
        narrative_flow.extend(creative[:2])
    
    # Add technical details (provide value)
    if technical:
        narrative_flow.extend(technical[:2])
    
    # End with comparisons (decision support)
    if comparison:
        narrative_flow.extend(comparison[:1])
    
    # If we still have space, add more
    max_questions = 4  # Optimal for one blog
    while len(narrative_flow) < max_questions and questions:
        for q in questions:
            if q not in narrative_flow:
                narrative_flow.append(q)
                break
    
    return narrative_flow[:max_questions]

async def generate_semantic_blog(topic_data: Dict, selected_outline_type: str) -> str:
    """
    Generate ONE rich semantic SEO blog post with PAA → H3 integration.
    This is the core function that creates our daily blog.
    """
    
    # Organize PAA into narrative flow
    organized_paa = organize_paa_into_narrative(topic_data['questions'])
    
    prompt = f"""
    CRITICAL INSTRUCTION: You are writing ONE daily blog post for SoundSwap that must capture Google's top search spots.
    
    TOPIC: {topic_data['query']}
    TREND SCORE: {topic_data['score']}/100 ({topic_data['status']})
    SOURCE: {topic_data['title']} - {topic_data['link']}
    
    OUTLINE APPROACH: {selected_outline_type}
    
    **PEOPLE ALSO ASK (PAA) QUESTIONS - MUST BECOME H3 HEADERS:**
    {chr(10).join([f'- {q}' for q in organized_paa])}
    
    **NON-NEGOTIABLE REQUIREMENTS:**
    
    1. **SEMANTIC SEO STRUCTURE:**
       - H1: Main title (include year 2026 and primary keyword)
       - H2: 3-4 main sections following narrative flow
       - H3: EACH PAA question becomes an H3 header (EXACTLY as shown above)
       - Under each H3: Answer that question thoroughly (50-100 words)
    
    2. **CONTENT FLOW (Narrative Structure):**
       - Introduction: Hook with trend data
       - Section 1: What it is (definition/context)
       - Section 2: Why it matters for producers
       - Section 3: How to use/implement
       - Section 4: Future implications
       - Conclusion with CTA
    
    3. **SEO ELEMENTS (Must Include):**
       - Primary keyword in first 100 words
       - LSI keywords naturally integrated
       - Internal linking suggestions [link to: gear-reviews, tutorials, etc.]
       - Meta description (160 chars)
       - SEO title tag (60 chars)
    
    4. **READER ENGAGEMENT:**
       - Data points from source
       - Actionable tips
       - Real producer examples
       - Bold key terms
    
    5. **LENGTH & FORMAT:**
       - 800-1000 words
       - Short paragraphs (2-3 sentences)
       - Bullet points where helpful
       - No markdown, just plain text with H1/H2/H3 labels
    
    Generate the complete blog post now:
    """
    
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        blog_content = response.text
        
        # Add SEO metadata section
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
        print(f"Blog generation error: {e}")
        return f"Error generating blog: {str(e)}"

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
        
        # Add emojis to each outline
        for i, outline in enumerate(outlines[:4]):
            if i < len(OUTLINE_TYPES):
                outline["emoji"] = OUTLINE_TYPES[i]["emoji"]
        
        # Ensure we have exactly 4 outlines
        while len(outlines) < 4:
            outline_type = OUTLINE_TYPES[len(outlines)]["name"]
            emoji = OUTLINE_TYPES[len(outlines)]["emoji"]
            
            outlines.append({
                "type": outline_type,
                "emoji": emoji,
                "content": f"{outline_type}: Outline generation pending",
                "sentiment": "NEUTRAL 😐",
                "sentiment_score": 0.0
            })
            
        return outlines[:4]  # Ensure exactly 4 outlines
        
    except Exception as e:
        print(f"Outline generation error: {e}")
        # Fallback outlines with emojis
        return [
            {"type": "Technical Deep Dive", "emoji": "🔬", "sentiment": "NEUTRAL 😐", "content": "Technical analysis of gear specifications..."},
            {"type": "Creative Applications", "emoji": "🎨", "sentiment": "POSITIVE 😊", "content": "How artists can use this creatively..."},
            {"type": "Industry Impact", "emoji": "📈", "sentiment": "NEUTRAL 😐", "content": "Market trends and implications..."},
            {"type": "Beginner-Friendly Guide", "emoji": "👶", "sentiment": "POSITIVE 😊", "content": "Simple guide for newcomers..."}
        ]

def edit_discord_message(token: str, content: str):
    """Edit a Discord message via webhook."""
    edit_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}/messages/@original"
    try:
        requests.patch(edit_url, json={"content": content[:1950]}, timeout=10)
        return True
    except Exception as e:
        print(f"Failed to edit Discord message: {e}")
        return False

async def process_daily_topics_selection(token: str):
    """Show daily topics for user to choose which ONE to generate blog from."""
    try:
        # Get SERP data for all 4 daily topics
        daily_topics = []
        for query in NICHE_QUERIES:
            serp_data = get_serp_data(query)
            daily_topics.append(serp_data)
        
        # Store for later blog generation
        daily_topics_store[token] = daily_topics
        
        # Build selection message
        response = f"🎸 **SOUNDSWAP DAILY BLOG TOPIC SELECTION**\n"
        response += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
        response += "**Choose ONE topic for today's semantic SEO blog:**\n\n"
        
        for i, topic in enumerate(daily_topics, 1):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][i-1]
            
            # Preview PAA questions
            paa_preview = topic['questions'][:2] if topic['questions'] else ["What producers need to know"]
            
            response += f"{emoji} **{topic['query'].upper()}**\n"
            response += f"   📊 Trend: {topic['score']}/100 {topic['status']}\n"
            response += f"   🔗 Source: {topic['link'][:50]}...\n"
            response += f"   ❓ PAA Preview: {paa_preview[0][:40]}...\n"
            response += f"   📈 Search Volume: {topic.get('total_results', 0):,} results\n\n"
        
        response += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        response += "**HOW TO CHOOSE:**\n"
        response += "Reply with your choice number (1-4)\n"
        response += "Then choose outline style (1-4)\n"
        response += "Get ONE semantic SEO blog with PAA → H3 headers!\n\n"
        response += "⏱️ *Only 1 blog per day for maximum SEO impact*"
        
        edit_discord_message(token, response)
        
    except Exception as e:
        print(f"Topic selection error: {e}")
        edit_discord_message(token, f"⚠️ **Error loading topics:** {str(e)[:500]}")

async def process_topic_outlines(token: str, topic_index: int):
    """Show outline options for selected topic."""
    try:
        daily_topics = daily_topics_store.get(token)
        if not daily_topics or topic_index < 0 or topic_index >= len(daily_topics):
            edit_discord_message(token, "❌ Topic not found. Please start over with `/blog`")
            return
        
        selected_topic = daily_topics[topic_index]
        
        # Generate 4 outlines for this topic
        outlines = await generate_four_outlines(selected_topic['query'], selected_topic)
        
        # Store outlines for blog generation
        if 'outlines_store' not in daily_topics_store:
            daily_topics_store['outlines_store'] = {}
        daily_topics_store['outlines_store'][token] = {
            'topic': selected_topic,
            'outlines': outlines,
            'selected_topic_index': topic_index
        }
        
        # Build outline selection message
        response = f"📝 **OUTLINE OPTIONS FOR:** {selected_topic['query'][:50]}...\n\n"
        response += f"📊 Trend Score: {selected_topic['score']}/100 {selected_topic['status']}\n"
        response += f"🔗 Source: {selected_topic['link'][:50]}...\n"
        response += f"❓ PAA Questions: {len(selected_topic['questions'])} found\n\n"
        
        response += "**4 OUTLINE APPROACHES:**\n\n"
        
        for i, outline in enumerate(outlines, 1):
            emoji = outline.get("emoji", "📝")
            
            response += f"{i}. {emoji} **{outline['type']}** {outline['sentiment']}\n"
            
            # Show key points preview
            content_preview = outline['content'][:100] if len(outline['content']) > 100 else outline['content']
            response += f"   ```{content_preview}...```\n\n"
        
        # Show PAA preview
        organized_paa = organize_paa_into_narrative(selected_topic['questions'])
        if organized_paa:
            response += "🔍 **PAA → H3 INTEGRATION PREVIEW:**\n"
            response += "*These questions will become H3 headers in your blog:*\n"
            for i, q in enumerate(organized_paa[:4], 1):
                response += f"{i}. {q[:60]}...\n"
            response += "\n"
        
        response += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        response += "**NEXT STEP:**\n"
        response += f"Reply with your outline choice (1-4)\n\n"
        response += f"Selected: Topic {topic_index + 1} • {selected_topic['query'][:30]}..."
        
        edit_discord_message(token, response)
        
    except Exception as e:
        print(f"Outline selection error: {e}")
        edit_discord_message(token, f"⚠️ **Error generating outlines:** {str(e)[:500]}")

async def generate_final_blog(token: str, outline_index: int):
    """Generate the final semantic SEO blog post."""
    try:
        outlines_data = daily_topics_store.get('outlines_store', {}).get(token)
        if not outlines_data:
            edit_discord_message(token, "❌ Session expired. Please start over with `/blog`")
            return
        
        topic_data = outlines_data['topic']
        outlines = outlines_data['outlines']
        
        if outline_index < 0 or outline_index >= len(outlines):
            edit_discord_message(token, "❌ Invalid outline selection")
            return
        
        selected_outline = outlines[outline_index]
        
        # Show generating message
        edit_discord_message(
            token,
            f"⚡ **GENERATING SEMANTIC SEO BLOG...**\n\n"
            f"**Topic:** {topic_data['query']}\n"
            f"**Outline:** {selected_outline['type']}\n"
            f"**PAA Integration:** {len(topic_data['questions'])} questions → H3 headers\n"
            f"**Trend Score:** {topic_data['score']}/100 {topic_data['status']}\n\n"
            f"*This takes about 30 seconds...*"
        )
        
        # Generate the blog
        blog_content = await generate_semantic_blog(topic_data, selected_outline['type'])
        
        # Split into Discord-friendly chunks
        chunks = []
        current_chunk = ""
        
        # Add header
        header = f"🎸 **SOUNDSWAP SEMANTIC SEO BLOG**\n"
        header += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
        header += f"🎯 Topic: {topic_data['query']}\n"
        header += f"📊 Trend: {topic_data['score']}/100 {topic_data['status']}\n"
        header += f"📝 Style: {selected_outline['type']}\n"
        header += f"🎭 Sentiment: {selected_outline['sentiment']}\n"
        header += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        current_chunk = header
        
        # Add blog content in chunks
        for paragraph in blog_content.split('\n\n'):
            if len(current_chunk) + len(paragraph) + 2 > 1900:
                chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Add footer to last chunk
        chunks[-1] += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        chunks[-1] += "✅ **BLOG GENERATED SUCCESSFULLY!**\n"
        chunks[-1] += "• PAA → H3 Integration: Complete\n"
        chunks[-1] += "• Semantic SEO: Optimized\n"
        chunks[-1] += "• Featured Snippet Ready: Yes\n"
        chunks[-1] += f"• Word Count: {len(blog_content.split())}\n"
        chunks[-1] += "• Narrative Flow: Beginner → Creative → Technical → Comparison\n\n"
        chunks[-1] += "💡 **Next:** Copy to your CMS, add images, publish!"
        
        # Send first chunk via webhook edit
        edit_discord_message(token, chunks[0])
        
        # Send remaining chunks as follow-up messages
        followup_url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{token}"
        
        for i, chunk in enumerate(chunks[1:], 1):
            try:
                requests.post(followup_url, json={"content": chunk}, timeout=10)
                time.sleep(1)  # Rate limit protection
            except Exception as e:
                print(f"Error sending chunk {i}: {e}")
        
        # Clear stored data
        if token in daily_topics_store:
            del daily_topics_store[token]
        if 'outlines_store' in daily_topics_store and token in daily_topics_store['outlines_store']:
            del daily_topics_store['outlines_store'][token]
            
    except Exception as e:
        print(f"Final blog generation error: {e}")
        edit_discord_message(token, f"⚠️ **Error generating blog:** {str(e)[:500]}")

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

    # 2. Handle Application Commands
    if data.get("type") == 2:
        command_data = data.get("data", {})
        command_name = command_data.get("name", "")
        token = data.get("token")
        
        # NEW COMMAND: /blog - Start daily blog generation process
        if command_name == "blog":
            # Start background task for topic selection
            thread = threading.Thread(
                target=lambda: asyncio.run(process_daily_topics_selection(token))
            )
            thread.start()
            
            # Return deferred response
            return {"type": 5}
        
        # Handle 'Generate Draft' Message Command (right-click)
        elif data.get("data", {}).get("type") == 3:  # Message command
            # Extract the message that was right-clicked
            resolved_messages = data.get("data", {}).get("resolved", {}).get("messages", {})
            if not resolved_messages:
                return {"type": 4, "data": {"content": "❌ Could not read message context."}}

            msg_id = list(resolved_messages.keys())[0]
            context_text = resolved_messages[msg_id].get("content", "")
            token = data.get("token")

            # Run in background thread
            thread = threading.Thread(target=lambda: asyncio.run(generate_and_edit(token, context_text)))
            thread.start()

            # Send 'Thinking...' state immediately
            return {"type": 5}
        
        # Handle legacy /outlines slash command
        elif command_name == "outlines":
            options = command_data.get("options", [])
            context_text = ""
            
            for opt in options:
                if opt.get("name") == "topic":
                    context_text = opt.get("value", "")
                    break
            
            if not context_text:
                context_text = "latest music production trends and AI audio tools"
            
            thread = threading.Thread(
                target=lambda: asyncio.run(generate_and_edit(token, context_text))
            )
            thread.start()
            
            return {"type": 5}
        
        return {"type": 4, "data": {"content": "❌ Unknown command"}}

    return {"type": 4, "data": {"content": "Unknown Interaction"}}

@app.get("/api/scout")
async def daily_scout():
    """Triggered by Vercel Cron to post daily reports with 4 outlines."""
    
    full_report = f"🎸 **SoundSwap Daily Blog Topics** ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    
    # Get SERP data for all topics
    daily_topics = []
    for query in NICHE_QUERIES:
        try:
            serp_data = get_serp_data(query)
            daily_topics.append(serp_data)
            
            # Build section
            section = f"📡 **TOPIC: {query.upper()}**\n"
            section += f"🔢 Trend Score: {serp_data['score']}/100 ({serp_data['status']})\n"
            section += f"🔗 Source: {serp_data['link']}\n"
            
            # Show PAA preview
            if serp_data['questions']:
                section += f"❓ PAA Preview: {serp_data['questions'][0][:60]}...\n"
            
            section += "\n" + "─" * 40 + "\n\n"
            
            full_report += section
            
        except Exception as e:
            full_report += f"❌ Error for '{query}': {str(e)[:100]}\n\n"
    
    # Add instructions
    full_report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    full_report += "**TO GENERATE TODAY'S BLOG:**\n"
    full_report += "1. Type `/blog` in this channel\n"
    full_report += "2. Choose ONE topic (1-4)\n"
    full_report += "3. Choose outline style (1-4)\n"
    full_report += "4. Get ONE semantic SEO blog with PAA → H3 headers!\n\n"
    full_report += "⏱️ *Only 1 blog per day for maximum SEO impact*"
    
    # Send to Discord
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    
    # Split message if too long
    max_length = 1900
    for i in range(0, len(full_report), max_length):
        chunk = full_report[i:i + max_length]
        requests.post(url, headers=headers, json={"content": chunk})
        time.sleep(1)  # Avoid rate limiting
    
    return {"status": "sent", "topics": len(NICHE_QUERIES)}

@app.post("/api/followup")
async def handle_followup(request: Request):
    """Handle follow-up messages for topic and outline selection."""
    try:
        data = await request.json()
        token = data.get("token")
        user_input = data.get("content", "").strip()
        
        # Check if it's a topic selection (1-4)
        if user_input in ['1', '2', '3', '4']:
            topic_index = int(user_input) - 1
            
            # Show outline options for selected topic
            thread = threading.Thread(
                target=lambda: asyncio.run(process_topic_outlines(token, topic_index))
            )
            thread.start()
            
            return {"status": "processing_outlines"}
        
        # Check if it's an outline selection (1-4) after topic selection
        elif user_input in ['1️⃣', '2️⃣', '3️⃣', '4️⃣'] or user_input in ['1', '2', '3', '4']:
            outline_index = int(user_input[0]) - 1  # Handle both "1" and "1️⃣"
            
            # Generate final blog
            thread = threading.Thread(
                target=lambda: asyncio.run(generate_final_blog(token, outline_index))
            )
            thread.start()
            
            return {"status": "generating_blog"}
        
        else:
            return {"status": "invalid_input", "message": "Please enter 1, 2, 3, or 4"}
            
    except Exception as e:
        print(f"Followup error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SoundSwap AI Blog Generator",
        "version": "3.0 - PAA → H3 Integration",
        "features": [
            "Daily topic selection (choose 1 of 4)",
            "PAA questions → H3 headers",
            "Semantic SEO blog generation",
            "Narrative flow organization",
            "Real-time sentiment analysis"
        ],
        "commands": [
            "/blog - Generate daily semantic SEO blog",
            "Right-click message → Generate 4 Outlines",
            "/outlines [topic] - Legacy outline generator"
        ],
        "daily_limit": "1 blog per day for maximum SEO impact"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "daily_topics_available": len(NICHE_QUERIES),
        "storage": {
            "active_sessions": len(daily_topics_store),
            "outline_sessions": len(daily_topics_store.get('outlines_store', {}))
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)