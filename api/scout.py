import os
import requests
import time
import concurrent.futures
from datetime import datetime
from fastapi import FastAPI

app = FastAPI()

# Import functions
import sys
sys.path.append('.')
from api.index import (
    NICHE_QUERIES,
    get_serp_data,
    DISCORD_TOKEN,
    CHANNEL_ID
)

@app.get("/")
async def daily_scout():
    """Daily scout with timeout handling."""
    try:
        # Fetch topics in parallel with timeouts
        daily_topics = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(get_serp_data, query) for query in NICHE_QUERIES]
            for future in concurrent.futures.as_completed(futures):
                try:
                    topic = future.result(timeout=25)
                    daily_topics.append(topic)
                except concurrent.futures.TimeoutError:
                    continue
        
        # Build report
        report = f"🎸 **SOUNDSWAP DAILY TOPICS** ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        report += "**Choose ONE for today's blog:**\n\n"
        
        for i, topic in enumerate(daily_topics, 1):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][i-1]
            report += f"{emoji} **{topic['query'].upper()}**\n"
            report += f"   📊 Trend: {topic['score']}/100 {topic['status']}\n"
            report += f"   🔗 Source: {topic['link'][:40]}...\n\n"
        
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "**Use `/blog` to generate your semantic SEO blog!**"
        
        # Send to Discord
        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json"
        }
        
        chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
        
        for i, chunk in enumerate(chunks):
            try:
                requests.post(url, headers=headers, json={"content": chunk}, timeout=10)
                time.sleep(1)
            except Exception as e:
                print(f"Chunk {i} error: {e}")
        
        return {
            "status": "sent",
            "topics": len(daily_topics),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}