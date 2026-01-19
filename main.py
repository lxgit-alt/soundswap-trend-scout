import os
import requests
from serpapi import Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# 4 High-impact topics to stay under 250 credits/month
NICHE_QUERIES = [
    "latest music production gear releases 2026",
    "breaking AI audio tools for artists",
    "independent music marketing trends 2026",
    "music streaming industry news today"
]

def generate_blog_outline(topic, score, link, questions):
    """Generates a structured SEO blog outline based on scraped data."""
    status = "🔥 VIRAL" if score > 75 else "📈 TRENDING"
    
    outline = f"📝 **BLOG STRATEGY: {topic.upper()}**\n"
    outline += f"*Trend Score: {score}/100 ({status})*\n"
    outline += f"*Source: {link}*\n\n"
    
    outline += "**H1: The Ultimate Guide to " + topic.title() + " in 2026**\n"
    outline += "───\n"
    outline += "**Intro:** Hook the reader with the 24h news update from the source link.\n"
    
    outline += "\n**H2: Why this matters for SoundSwap Creators**\n"
    outline += "* Bullet points on workflow impact and artist growth.\n"

    if questions:
        outline += "\n**H2: Common Questions (SEO FAQ Section)**\n"
        for q in questions[:3]:
            outline += f"✅ **H3: {q}**\n   * Answer this in 50 words to win the Google Snippet.\n"
    
    outline += "\n**Conclusion & CTA:** Summarize and invite users to SoundSwap.\n"
    outline += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    return outline

def get_trend_score(keyword):
    try:
        client = Client(api_key=SERPAPI_KEY)
        results = client.search({"engine": "google_trends", "q": keyword, "data_type": "TIMESERIES", "date": "now 7-d"})
        timeseries = results.get("interest_over_time", {}).get("timeline_data", [])
        return int(timeseries[-1].get("values")[0].get("value")) if timeseries else 0
    except: return 0

def get_serp_data(query):
    score = get_trend_score(query)
    params = {"engine": "google", "q": query, "tbs": "qdr:d", "api_key": SERPAPI_KEY}
    
    try:
        client = Client(api_key=SERPAPI_KEY)
        results = client.search(params)
        organic = results.get("organic_results", [])
        paa = [q.get('question') for q in results.get("related_questions", [])]
        
        first_link = organic[0].get('link') if organic else "No link found"
        
        # Build the summary and the outline
        summary = f"📡 **TOPIC: {query.upper()}**\nScore: {score}/100\nLink: <{first_link}>\n"
        outline = generate_blog_outline(query, score, first_link, paa)
        
        return f"{summary}\n{outline}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def send_to_discord(message):
    # Discord limit is 2000 chars; we split to be safe
    for i in range(0, len(message), 1900):
        requests.post(DISCORD_WEBHOOK, json={"content": message[i:i+1900]})

def main():
    if not SERPAPI_KEY or not DISCORD_WEBHOOK:
        print("Missing API Keys.")
        return

    full_report = f"🎸 **SoundSwap Daily Intel + Blog Outlines** ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    
    for q in NICHE_QUERIES:
        full_report += get_serp_data(q) + "\n"

    send_to_discord(full_report)
    print("🚀 Intel and outlines dispatched!")

if __name__ == "__main__":
    main()