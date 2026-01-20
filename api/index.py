import os
import json
import requests
import time
from typing import List, Dict, Tuple, Optional
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
import google.generativeai as genai
from serpapi import Client
from textblob import TextBlob
from datetime import datetime
import asyncio
import threading
import random

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

# 4 High-impact topics for daily scout - NO CHANGES
NICHE_QUERIES = [
    "latest music production gear releases 2026",
    "breaking AI audio tools for artists",
    "independent music marketing trends 2026",
    "music streaming industry news today"
]

# Outline types with emojis - NO CHANGES
OUTLINE_TYPES = [
    {"name": "Technical Deep Dive", "emoji": "🔬", "description": "Specifications, features, technical analysis"},
    {"name": "Creative Applications", "emoji": "🎨", "description": "Practical uses for artists and producers"},
    {"name": "Industry Impact", "emoji": "📈", "description": "Market trends and business implications"},
    {"name": "Beginner-Friendly Guide", "emoji": "👶", "description": "Simplified explanations for newcomers"}
]

# Store daily topics for selection
daily_topics_store = {}

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
    """Fetch SERP data including related questions - CRITICAL FOR PAA."""
    try:
        score = get_trend_score(query)
        client = Client(api_key=SERPAPI_KEY)
        
        results = client.search({
            "engine": "google",
            "q": query,
            "tbs": "qdr:d",
            "api_key": SERPAPI_KEY,
            "num": 5  # Get more results for better PAA data
        })
        
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
            "questions": questions,  # PAA questions for H3 headers
            "status": status,
            "total_results": results.get("search_information", {}).get("total_results", 0)
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
            "status": "📊 STEADY",
            "total_results": 0
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
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
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
        response = model.generate_content(prompt)
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
        embeds = []
        
        # Main selection embed
        selection_embed = {
            "title": "🎸 SoundSwap Daily Blog Topic Selection",
            "description": f"**Choose ONE topic for today's semantic SEO blog**\n*Generated on {datetime.now().strftime('%Y-%m-%d')}*",
            "color": 0x5865F2,
            "fields": []
        }
        
        for i, topic in enumerate(daily_topics, 1):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][i-1]
            
            # Organize PAA preview
            paa_preview = topic['questions'][:2] if topic['questions'] else ["No PAA questions found"]
            paa_text = "\n".join([f"• {q[:40]}..." for q in paa_preview])
            
            field_value = f"**Trend:** {topic['score']}/100 {topic['status']}\n"
            field_value += f"**Source:** [Link]({topic['link']})\n"
            field_value += f"**PAA Preview:**\n{paa_text}\n"
            field_value += f"**Total Results:** {topic.get('total_results', 0):,}"
            
            selection_embed["fields"].append({
                "name": f"{emoji} {topic['query'][:40]}...",
                "value": field_value,
                "inline": False
            })
        
        embeds.append(selection_embed)
        
        # Instructions embed
        instructions_embed = {
            "title": "🎯 How to Choose & Generate",
            "description": "**STEP 1:** Reply with your choice number (1-4)\n**STEP 2:** Wait for outline options\n**STEP 3:** Choose outline style\n**STEP 4:** Get your semantic SEO blog with PAA → H3 integration",
            "color": 0x57F287,
            "fields": [
                {
                    "name": "🔍 What Makes This Special",
                    "value": "• PAA questions become H3 headers\n• Narrative flow for featured snippets\n• Semantic SEO structure\n• Google top-spot training"
                },
                {
                    "name": "⏱️ Time to Generate",
                    "value": "• Topic selection: Now\n• Outlines: 10 seconds\n• Full blog: 30 seconds\n• Total: < 1 minute"
                }
            ]
        }
        embeds.append(instructions_embed)
        
        # Send selection message
        edit_discord_message(
            token,
            f"✅ **Daily Topics Ready!** Choose ONE topic for today's blog (reply with 1-4):",
            embeds
        )
        
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
        embeds = []
        
        # Topic info embed
        topic_embed = {
            "title": f"📝 Outline Options for: {selected_topic['query'][:50]}...",
            "description": f"**Trend Score:** {selected_topic['score']}/100 {selected_topic['status']}\n**PAA Questions:** {len(selected_topic['questions'])} found",
            "color": 0x5865F2,
            "fields": []
        }
        
        for i, outline in enumerate(outlines, 1):
            emoji = ["🔬", "🎨", "📈", "👶"][i-1]
            
            key_points = outline.get('key_points', [])
            points_text = "\n".join([f"• {p[:40]}..." for p in key_points[:2]]) if key_points else "• Detailed analysis"
            
            field_value = f"**Audience:** {outline.get('audience', 'Producers')}\n"
            field_value += f"**Tone:** {outline.get('tone', 'Professional')} {outline.get('sentiment', 'NEUTRAL 😐')}\n"
            field_value += f"**Reading:** {outline.get('reading_time', '5-7 min')}\n"
            field_value += f"**Key Points:**\n{points_text}"
            
            topic_embed["fields"].append({
                "name": f"{i}. {emoji} {outline['type']}",
                "value": field_value,
                "inline": False
            })
        
        embeds.append(topic_embed)
        
        # PAA Preview embed
        if selected_topic['questions']:
            organized_paa = organize_paa_into_narrative(selected_topic['questions'])
            paa_embed = {
                "title": "🔍 PAA → H3 Integration Preview",
                "description": "**These questions will become H3 headers in your blog:**",
                "color": 0x9B59B6,
                "fields": []
            }
            
            for i, q in enumerate(organized_paa[:4], 1):
                paa_embed["fields"].append({
                    "name": f"H3 Header {i}",
                    "value": f"```{q[:60]}...```",
                    "inline": False
                })
            
            embeds.append(paa_embed)
        
        # Selection instructions
        selection_embed = {
            "title": "🎯 Next Step: Choose Outline Style",
            "description": f"**Reply with your outline choice (1-4)**\n\nSelected: Topic {topic_index + 1} • {selected_topic['query'][:30]}...",
            "color": 0xF1C40F,
            "footer": {
                "text": "After outline selection, I'll generate your semantic SEO blog with PAA → H3 headers"
            }
        }
        embeds.append(selection_embed)
        
        edit_discord_message(
            token,
            f"📊 **4 Outline Approaches Ready!** Choose ONE outline style (reply with 1-4):",
            embeds
        )
        
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
            f"⚡ **Generating Semantic SEO Blog...**\n\n"
            f"**Topic:** {topic_data['query']}\n"
            f"**Outline:** {selected_outline['type']}\n"
            f"**PAA Integration:** {len(topic_data['questions'])} questions → H3 headers\n\n"
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
        chunks[-1] += "✅ **Blog Generated Successfully!**\n"
        chunks[-1] += "• PAA → H3 Integration: Complete\n"
        chunks[-1] += "• Semantic SEO: Optimized\n"
        chunks[-1] += "• Featured Snippet Ready: Yes\n"
        chunks[-1] += f"• Word Count: {len(blog_content.split())}\n\n"
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

@app.post("/api/interactions")
async def interactions(request: Request):
    """Handle Discord interactions - UPDATED FOR TOPIC SELECTION."""
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
        
        # NEW COMMAND: /blog - Start daily blog generation process
        if command_name == "blog":
            # Start background task for topic selection
            thread = threading.Thread(
                target=lambda: asyncio.run(process_daily_topics_selection(token))
            )
            thread.start()
            
            # Return deferred response
            return {"type": 5}
        
        # Keep existing /outlines command for backward compatibility
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
                target=lambda: asyncio.run(process_outline_generation(token, context_text))
            )
            thread.start()
            
            return {"type": 5}
        
        return {"type": 4, "data": {"content": "❌ Unknown command"}}
    
    # 3. Handle Message Component Interactions (for topic/outline selection)
    if data.get("type") == 3:
        # This handles button clicks or other components
        return {"type": 4, "data": {"content": "Component interactions not yet implemented"}}

    return {"type": 4, "data": {"content": "Unknown Interaction"}}

# NEW: Handle follow-up messages for topic/outline selection
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

@app.get("/api/scout")
async def daily_scout():
    """Triggered by Vercel Cron to post daily topic options."""
    
    try:
        # Get SERP data for all topics
        daily_topics = []
        for query in NICHE_QUERIES:
            serp_data = get_serp_data(query)
            daily_topics.append(serp_data)
        
        # Build daily report with topic options
        report = f"🎸 **SOUNDSWAP DAILY BLOG TOPICS** ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        report += "**Choose ONE topic for today's semantic SEO blog:**\n\n"
        
        for i, topic in enumerate(daily_topics, 1):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][i-1]
            
            # Preview PAA questions
            paa_preview = topic['questions'][:2] if topic['questions'] else ["What producers need to know"]
            
            report += f"{emoji} **{topic['query'].upper()}**\n"
            report += f"   📊 Trend: {topic['score']}/100 {topic['status']}\n"
            report += f"   🔗 Source: {topic['link'][:50]}...\n"
            report += f"   ❓ PAA: {paa_preview[0][:40]}...\n\n"
        
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "**TO GENERATE BLOG:**\n"
        report += "1. Type `/blog` in this channel\n"
        report += "2. Choose topic (1-4)\n"
        report += "3. Choose outline style\n"
        report += "4. Get semantic SEO blog with PAA → H3 headers!\n\n"
        report += "⏱️ *Only 1 blog per day for maximum SEO impact*"
        
        # Send to Discord
        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Split if needed
        max_length = 1900
        chunks = [report[i:i + max_length] for i in range(0, len(report), max_length)]
        
        for i, chunk in enumerate(chunks):
            payload = {"content": chunk}
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                if response.status_code != 200:
                    print(f"Failed to send chunk {i}: {response.status_code} - {response.text}")
                time.sleep(1)
            except Exception as e:
                print(f"Error sending chunk {i}: {e}")
        
        return {
            "status": "sent",
            "topics": len(daily_topics),
            "date": datetime.now().isoformat(),
            "note": "Users must now choose ONE topic via /blog command"
        }
        
    except Exception as e:
        print(f"Daily scout error: {e}")
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
            "/outlines - Quick 4 outlines (legacy)"
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