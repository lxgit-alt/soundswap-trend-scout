const axios = require('axios');
require('dotenv').config();

async function registerCommands() {
  const { DISCORD_BOT_TOKEN, DISCORD_APP_ID } = process.env;
  
  if (!DISCORD_BOT_TOKEN) {
    console.error('❌ DISCORD_BOT_TOKEN not found in .env');
    process.exit(1);
  }
  
  if (!DISCORD_APP_ID) {
    console.error('❌ DISCORD_APP_ID not found in .env');
    process.exit(1);
  }
  
  const url = `https://discord.com/api/v10/applications/${DISCORD_APP_ID}/commands`;
  const headers = {
    'Authorization': `Bot ${DISCORD_BOT_TOKEN}`,
    'Content-Type': 'application/json'
  };
  
  console.log(`🔧 Registering commands for App ID: ${DISCORD_APP_ID}`);
  console.log(`📝 Target URL: ${url}`);
  
  // Command 1: /blog
  const blogCommand = {
    name: 'blog',
    description: 'Generate daily semantic SEO blog (choose from 4 topics)',
    type: 1
  };
  
  // Command 2: /outlines
  const outlinesCommand = {
    name: 'outlines',
    description: 'Generate 4 blog outline approaches',
    type: 1,
    options: [
      {
        name: 'topic',
        description: 'Topic for blog outlines',
        type: 3,
        required: false
      }
    ]
  };
  
  const commands = [blogCommand, outlinesCommand];
  
  console.log('\n📨 Registering commands...');
  
  for (const cmd of commands) {
    try {
      const response = await axios.post(url, cmd, { headers });
      if (response.status === 200 || response.status === 201) {
        console.log(`✅ /${cmd.name} registered successfully!`);
      } else {
        console.log(`❌ Failed to register /${cmd.name}: ${response.status}`);
        console.log(`Response: ${JSON.stringify(response.data, null, 2)}`);
      }
    } catch (error) {
      console.log(`❌ Failed to register /${cmd.name}: ${error.message}`);
      if (error.response) {
        console.log(`Response: ${JSON.stringify(error.response.data, null, 2)}`);
      }
    }
  }
  
  console.log('\n🎯 Commands registered! Use them in Discord:');
  console.log('1. /blog - Daily blog workflow');
  console.log('2. /outlines [topic] - Quick outlines');
  console.log('\n🚀 Your bot is ready!');
}

registerCommands().catch(console.error);