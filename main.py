import os
import requests
import google.generativeai as genai
from serpapi import Client
from dotenv import load_dotenv
from datetime import datetime

# 1. Load environment variables (Local VS Code testing)
load_dotenv()

# --- CONFIGURATION ---
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini 1.5 Flash
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 4 Core Topics (Keeps you under 250 SerpApi credits/month)
NICHE_QUERIES = [
    "latest music production gear releases 2026",
    "breaking AI audio tools for artists",
    "independent music marketing trends 2026",
    "music streaming industry news today"
]

def get_ai_enhanced_intel(topic, score, link, snippets, questions):
    """Uses Gemini to analyze Sentiment and generate an SEO Outline."""
    
    prompt = f"""
    You are the Senior Content Strategist for SoundSwap (a hub for music producers).
    
    INPUT DATA:
    - Topic: {topic}
    - Trend Score: {score}/100
    - Top Headlines/Snippets: {snippets}
    - People Also Ask: {", ".join(questions)}
    
    TASK:
    1. ANALYZE SENTIMENT: Based on the snippets, is the industry reaction 'Hype' (Positive), 'Controversy' (Negative), or 'Mixed/Neutral'? Provide a 1-sentence reason.
    2. GENERATE OUTLINE: Create a viral H1 title and a structured blog outline.
    3. H3 HEADERS: Use the 'People Also Ask' questions as H3 headers.
    4. PRO-TIP: Add one 'SoundSwap Pro-Tip' for independent artists.
    
    FORMAT: Use Markdown for Discord. Include a 'SENTIMENT' badge at the top.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini AI Error: {str(e)}"

def get_trend_score(keyword):
    """Fetches Google Trends interest score (1 SerpApi credit)."""
    try:
        client = Client(api_key=SERPAPI_KEY)
        results = client.search({
            "engine": "google_trends",
            "q": keyword,
            "data_type": "TIMESERIES",
            "date": "now 7-d"
        })
        timeseries = results.get("interest_over_time", {}).get("timeline_data", [])
        return int(timeseries[-1].get("values")[0].get("value")) if timeseries else 0
    except:
        return 0

def get_serp_data(query):
    """Fetches Google Search data (1 SerpApi credit)."""
    score = get_trend_score(query)
    params = {
        "engine": "google",
        "q": query,
        "tbs": "qdr:d", # Past 24 hours
        "api_key": SERPAPI_KEY
    }
    
    try:
        client = Client(api_key=SERPAPI_KEY)
        results = client.search(params)
        organic = results.get("organic_results", [])
        
        # Collect snippets for Sentiment Analysis
        snippets = " | ".join([f"{r.get('title')}: {r.get('snippet')}" for r in organic[:3]])
        paa = [q.get('question') for q in results.get("related_questions", [])]
        first_link = organic[0].get('link') if organic else "N/A"
        
        # Run AI Analysis
        ai_report = get_ai_enhanced_intel(query, score, first_link, snippets, paa)
        
        header = f"📡 **TOPIC: {query.upper()}**\n"
        header += f"📊 Trend Score: {score}/100 | 🔗 Source: <{first_link}>\n"
        
        return f"{header}\n{ai_report}\n"
    except Exception as e:
        return f"❌ Error scouting {query}: {str(e)}"

def main():
    if not all([SERPAPI_KEY, DISCORD_WEBHOOK, GEMINI_API_KEY]):
        print("❌ Setup incomplete. Check your API Keys.")
        return

    today = datetime.now().strftime('%B %d, %Y')
    full_report = f"🔥 **SoundSwap Daily AI Intelligence + Sentiment** ({today})\n"
    full_report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for q in NICHE_QUERIES:
        full_report += get_serp_data(q) + "\n"

    # Split for Discord 2000-char limit
    for i in range(0, len(full_report), 1900):
        requests.post(DISCORD_WEBHOOK, json={"content": full_report[i:i+1900]})
    
    print("🚀 AI Analysis & Outlines dispatched to SoundSwap Discord!")

if __name__ == "__main__":
    main()