import os
import time
import random
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from dotenv import load_dotenv

# 1. Load environment variables (for local VS Code testing)
load_dotenv()

# --- CONFIGURATION ---
# SoundSwap-specific search queries to find blog inspiration
QUERIES = [
    "trending audio production tech 2026",
    "music streaming industry news",
    "AI music tools for independent artists",
    "SoundCloud vs Spotify for creators 2026"
]

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

def get_stealth_headers():
    """Generates random browser headers to look like a real user."""
    ua = UserAgent()
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

def scrape_google(query):
    """Scrapes the top 3 results from Google for a given query."""
    print(f"🔎 Scouting trends for: {query}...")
    
    # URL encode the query
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en"
    
    # Random delay (2-5 seconds) to avoid bot detection
    time.sleep(random.uniform(2, 5))
    
    try:
        response = requests.get(search_url, headers=get_stealth_headers(), timeout=15)
        response.raise_for_status()
        
        # Parse using lxml for speed and accuracy
        soup = BeautifulSoup(response.text, "lxml")
        
        results = []
        # Target the standard Google result container class
        for g in soup.select(".tF2Cxc")[:3]:
            title = g.select_one("h3").text if g.select_one("h3") else "No Title"
            link = g.select_one("a")["href"] if g.select_one("a") else "No Link"
            results.append(f"**{title}**\n<{link}>")
            
        return "\n".join(results) if results else "⚠️ No results found. Google might be blocking the request."

    except Exception as e:
        return f"❌ Scraping Error: {str(e)}"

def send_to_discord(report_content):
    """Sends the final report to the SoundSwap Discord channel."""
    if not DISCORD_WEBHOOK:
        print("❌ Error: DISCORD_WEBHOOK not found in environment variables.")
        return

    payload = {
        "content": f"🎵 **SoundSwap Daily Trend Scout** 🎵\n\n{report_content}\n---\n*Ready for today's blog posts?*"
    }
    
    try:
        res = requests.post(DISCORD_WEBHOOK, json=payload)
        res.raise_for_status()
        print("✅ Report sent to Discord successfully!")
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

def main():
    """Orchestrates the scraping and notification process."""
    full_report = ""
    
    for q in QUERIES:
        scraped_data = scrape_google(q)
        full_report += f"📡 **Query: {q}**\n{scraped_data}\n\n"
    
    send_to_discord(full_report)

if __name__ == "__main__":
    main()