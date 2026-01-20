import os
import discord
from discord.ext import commands
from google import genai 
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini 1.5 Flash for the best balance of speed and quota
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True  # Crucial: allows the bot to read the message you reply to
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ SoundSwap Draft Specialist is Online: {bot.user}")
    print("Directing all energy to the !draft command.")

@bot.command()
async def draft(ctx):
    """
    Triggered when a user replies to a Scout report with '!draft'.
    It pulls the context from the parent message and writes a full article.
    """
    # 1. Check if the user actually replied to a message
    if not ctx.message.reference:
        await ctx.send("❌ **SoundSwap Hint:** Please **reply** to a scout report with `!draft` so I know what to write about!")
        return

    try:
        # 2. Fetch the message being replied to
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        
        async with ctx.typing(): # Shows 'SoundSwap AI is typing...' in Discord
            prompt = f"""
            System: You are the lead copywriter for SoundSwap, a platform for independent music producers.
            Task: Write a high-energy, 600-word blog post based on the following intel:
            
            Intel: {replied_msg.content}
            
            Requirements:
            - Professional yet punchy tone.
            - Focus on actionable takeaways for producers.
            - Structure: Catchy H1, Intro, 3 Body Sections with H2s, and a 'Final Verdict' CTA.
            """
            
            response = ai_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            
            full_text = response.text
            
            # 3. Handle Discord's 2000 character limit by chunking the output
            if len(full_text) > 1900:
                chunks = [full_text[i:i+1900] for i in range(0, len(full_text), 1900)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(full_text)
                
    except Exception as e:
        await ctx.send(f"⚠️ **Drafting Error:** {str(e)}")

bot.run(TOKEN)