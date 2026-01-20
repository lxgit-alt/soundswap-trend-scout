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

# First, let's delete any existing commands to avoid conflicts
print("\n🗑️  Deleting existing commands...")
response = requests.get(url, headers=headers)
if response.status_code == 200:
    existing_commands = response.json()
    for cmd in existing_commands:
        delete_url = f"{url}/{cmd['id']}"
        del_response = requests.delete(delete_url, headers=headers)
        if del_response.status_code == 204:
            print(f"✅ Deleted command: {cmd['name']}")
        else:
            print(f"❌ Failed to delete {cmd['name']}: {del_response.status_code}")

# Now register the slash command (CORRECT WAY)
slash_command = {
    "name": "outlines",
    "description": "Generate 4 blog outline approaches with sentiment analysis",
    "type": 1,  # Slash command
    "options": [
        {
            "name": "topic",
            "description": "Topic for blog outlines (or reply to a message)",
            "type": 3,  # String
            "required": False
        }
    ],
    "integration_types": [0, 1],  # Guild and DM
    "dm_permission": True
}

print("\n📨 Registering slash command '/outlines'...")
response = requests.post(url, headers=headers, json=slash_command)

if response.status_code in [200, 201]:
    print("✅ Slash command registered successfully!")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"❌ Failed to register slash command: {response.status_code}")
    print(f"Response: {response.text}")

# Register a user context menu command (right-click on user)
user_context_command = {
    "name": "Generate User Outlines",
    "type": 2,  # User context menu
    "integration_types": [0, 1],
    "dm_permission": True
}

print("\n📨 Registering user context menu command...")
response = requests.post(url, headers=headers, json=user_context_command)

if response.status_code in [200, 201]:
    print("✅ User context command registered!")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"❌ Failed to register user context: {response.status_code}")
    print(f"Response: {response.text}")

print("\n🎯 To use the bot in Discord:")
print("1. Type /outlines [topic] in any channel")
print("2. Or type /outlines without a topic (it will use recent messages)")
print("\n⚠️  Note: For message context menu, we'll handle it differently in the FastAPI app.")