import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
APP_ID = os.getenv("DISCORD_APP_ID")

if not DISCORD_TOKEN:
    print("❌ DISCORD_BOT_TOKEN not found in .env file")
    exit(1)

if not APP_ID:
    print("❌ DISCORD_APP_ID not found in .env file")
    exit(1)

url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"

headers = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json"
}

print(f"🔧 Registering commands for App ID: {APP_ID}")
print(f"📝 Target URL: {url}")

# First, list current commands
print("\n📋 Current registered commands:")
response = requests.get(url, headers=headers)
if response.status_code == 200:
    commands = response.json()
    for cmd in commands:
        print(f"• /{cmd['name']} - {cmd.get('description', 'No description')}")

# Register NEW /blog command (MAIN COMMAND)
blog_command = {
    "name": "blog",
    "description": "Generate ONE semantic SEO blog from daily topics (PAA → H3 integration)",
    "type": 1,  # Slash command
    "integration_types": [0, 1],
    "dm_permission": True
}

print("\n📨 Registering NEW command '/blog'...")
response = requests.post(url, headers=headers, json=blog_command)

if response.status_code in [200, 201]:
    print("✅ /blog command registered successfully!")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"❌ Failed to register /blog: {response.status_code}")
    print(f"Response: {response.text}")

# Keep existing /outlines for backward compatibility
outlines_command = {
    "name": "outlines",
    "description": "Quick 4 blog outlines (legacy command)",
    "type": 1,
    "options": [
        {
            "name": "topic",
            "description": "Topic for outlines",
            "type": 3,
            "required": False
        }
    ],
    "integration_types": [0, 1],
    "dm_permission": True
}

print("\n📨 Registering command '/outlines'...")
response = requests.post(url, headers=headers, json=outlines_command)

if response.status_code in [200, 201]:
    print("✅ /outlines command registered successfully!")
else:
    print(f"❌ Failed to register /outlines: {response.status_code}")

print("\n🎯 **NEW WORKFLOW:**")
print("1. Daily scout posts 4 topics")
print("2. User types /blog")
print("3. Chooses ONE topic (1-4)")
print("4. Chooses outline style (1-4)")
print("5. Gets ONE semantic SEO blog with PAA → H3 headers")
print("\n⏱️  Only 1 blog per day for maximum SEO impact!")