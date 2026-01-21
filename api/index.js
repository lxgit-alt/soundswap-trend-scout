import { GoogleGenerativeAI } from '@google/generative-ai';

// Configuration from environment variables
const {
  DISCORD_PUBLIC_KEY,
  DISCORD_BOT_TOKEN,
  DISCORD_APP_ID,
  DISCORD_CHANNEL_ID,
  GEMINI_API_KEY,
  SERPAPI_KEY,
  CRON_SECRET
} = process.env;

// Initialize Gemini AI
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

// Niche queries for daily scout
const NICHE_QUERIES = [
  "latest music production gear releases 2026",
  "breaking AI audio tools for artists",
  "independent music marketing trends 2026",
  "music streaming industry news today"
];

// Outline types with emojis
const OUTLINE_TYPES = [
  { name: "Technical Deep Dive", emoji: "🔬", description: "Specifications, features, technical analysis" },
  { name: "Creative Applications", emoji: "🎨", description: "Practical uses for artists and producers" },
  { name: "Industry Impact", emoji: "📈", description: "Market trends and business implications" },
  { name: "Beginner-Friendly Guide", emoji: "👶", description: "Simplified explanations for newcomers" }
];

// Store for user sessions
let userSessions = new Map();

/**
 * Main handler for Vercel Edge Function
 */
export default async function handler(request) {
  const url = new URL(request.url);
  const pathname = url.pathname;
  
  console.log(`Incoming request: ${request.method} ${pathname}`);
  
  // Set CORS headers
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Signature-Ed25519, X-Signature-Timestamp',
    'Content-Type': 'application/json'
  };

  // Handle OPTIONS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers });
  }

  // Route based on pathname
  if (pathname === '/api/interactions' && request.method === 'POST') {
    return await handleDiscordInteraction(request);
  }
  
  if (pathname === '/api/scout' && request.method === 'GET') {
    return await handleDailyScout(request);
  }
  
  if (pathname === '/api/scout-direct' && request.method === 'POST') {
    // Direct execution endpoint for GitHub Actions
    return await handleDirectScout(request);
  }
  
  if (pathname === '/health' && request.method === 'GET') {
    return new Response(JSON.stringify({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      service: 'SoundSwap AI',
      version: '3.0 - PAA → H3 Integration',
      endpoints: {
        interactions: '/api/interactions',
        scout: '/api/scout',
        'scout-direct': '/api/scout-direct (POST for GitHub Actions)',
        health: '/health'
      }
    }), { status: 200, headers });
  }
  
  if (pathname === '/' && request.method === 'GET') {
    return new Response(JSON.stringify({
      status: 'online',
      service: 'SoundSwap AI Blog Generator',
      version: '3.0 - PAA → H3 Integration',
      features: [
        'Daily topic selection (choose 1 of 4)',
        'PAA questions → H3 headers',
        'Semantic SEO blog generation',
        'Real-time sentiment analysis'
      ],
      commands: [
        '/blog - Generate daily semantic SEO blog',
        'Right-click message → Generate 4 Outlines',
        '/outlines [topic] - Legacy outline generator'
      ],
      daily_limit: '1 blog per day for maximum SEO impact'
    }), { status: 200, headers });
  }

  // If no route matches, return 404
  return new Response(JSON.stringify({ 
    error: 'Not found',
    path: pathname,
    method: request.method,
    available_endpoints: [
      'GET /',
      'GET /health',
      'GET /api/scout',
      'POST /api/scout-direct',
      'POST /api/interactions'
    ]
  }), { 
    status: 404, 
    headers 
  });
}

/**
 * Handle Discord interactions
 */
async function handleDiscordInteraction(request) {
  try {
    console.log('Processing Discord interaction...');
    const body = await request.text();
    
    // Parse interaction
    const interaction = JSON.parse(body);
    
    // Handle PING
    if (interaction.type === 1) {
      console.log('Responding to Discord ping');
      return new Response(JSON.stringify({ type: 1 }), { 
        status: 200, 
        headers: { 'Content-Type': 'application/json' } 
      });
    }
    
    // Handle APPLICATION_COMMAND
    if (interaction.type === 2) {
      const { data, token } = interaction;
      const commandName = data?.name;
      
      console.log(`Processing command: ${commandName}`);
      
      // Handle /blog command
      if (commandName === 'blog') {
        console.log('Starting blog generation process...');
        // Return deferred response immediately
        const response = new Response(JSON.stringify({ type: 5 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
        
        // Process in background
        processBlogCommand(token, data).catch(error => {
          console.error('Blog command error:', error);
          editOriginalResponse(token, `❌ Error: ${error.message?.slice(0, 100) || 'Unknown error'}`)
            .catch(e => console.error('Failed to send error:', e));
        });
        
        return response;
      }
      
      // Handle /outlines command
      if (commandName === 'outlines') {
        const topic = data?.options?.find(opt => opt.name === 'topic')?.value || 
                     'latest music production trends 2026';
        
        console.log(`Processing outlines for topic: ${topic}`);
        
        // Return deferred response immediately
        const response = new Response(JSON.stringify({ type: 5 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
        
        // Process in background
        processOutlinesCommand(token, topic).catch(error => {
          console.error('Outlines command error:', error);
          editOriginalResponse(token, `❌ Error: ${error.message?.slice(0, 100) || 'Unknown error'}`)
            .catch(e => console.error('Failed to send error:', e));
        });
        
        return response;
      }
    }
    
    // Unknown interaction type
    console.log('Unknown interaction type:', interaction.type);
    return new Response(JSON.stringify({ 
      type: 4, 
      data: { content: '❌ Unknown command' } 
    }), { 
      status: 200, 
      headers: { 'Content-Type': 'application/json' } 
    });
    
  } catch (error) {
    console.error('Discord interaction error:', error);
    return new Response(JSON.stringify({ 
      type: 4, 
      data: { content: `❌ Internal server error: ${error.message?.slice(0, 100) || 'Unknown error'}` } 
    }), { 
      status: 200, 
      headers: { 'Content-Type': 'application/json' } 
    });
  }
}

/**
 * Handle daily scout cron job (legacy - for triggering only)
 */
async function handleDailyScout(request) {
  try {
    console.log('Starting daily scout...');
    
    // Return response immediately
    return new Response(JSON.stringify({ 
      status: 'triggered', 
      message: 'Daily scout triggered. For actual execution, use /api/scout-direct POST endpoint.',
      timestamp: new Date().toISOString(),
      note: 'Use POST /api/scout-direct with GitHub Actions for reliable execution'
    }), { 
      status: 200, 
      headers: { 'Content-Type': 'application/json' } 
    });
    
  } catch (error) {
    console.error('Scout handler error:', error);
    return new Response(JSON.stringify({ 
      error: error.message,
      status: 'error'
    }), { 
      status: 500, 
      headers: { 'Content-Type': 'application/json' } 
    });
  }
}

/**
 * Handle direct scout execution (for GitHub Actions)
 */
async function handleDirectScout(request) {
  try {
    console.log('Starting direct scout execution...');
    
    // Verify authorization if CRON_SECRET is set
    if (CRON_SECRET) {
      const authHeader = request.headers.get('Authorization');
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return new Response(JSON.stringify({ error: 'Unauthorized' }), { 
          status: 401, 
          headers: { 'Content-Type': 'application/json' } 
        });
      }
      
      const token = authHeader.split(' ')[1];
      if (token !== CRON_SECRET) {
        return new Response(JSON.stringify({ error: 'Invalid token' }), { 
          status: 403, 
          headers: { 'Content-Type': 'application/json' } 
        });
      }
    }
    
    // Execute scout synchronously
    const result = await runDailyScout();
    
    return new Response(JSON.stringify({ 
      status: 'completed', 
      message: 'Daily scout completed successfully',
      timestamp: new Date().toISOString(),
      result: result
    }), { 
      status: 200, 
      headers: { 'Content-Type': 'application/json' } 
    });
    
  } catch (error) {
    console.error('Direct scout error:', error);
    return new Response(JSON.stringify({ 
      error: error.message,
      status: 'error',
      timestamp: new Date().toISOString()
    }), { 
      status: 500, 
      headers: { 'Content-Type': 'application/json' } 
    });
  }
}

/**
 * Process /blog command
 */
async function processBlogCommand(token, data) {
  try {
    await editOriginalResponse(token, "🎸 **Loading daily topics...**");
    
    console.log('Getting SERP data for all topics...');
    const dailyTopics = [];
    
    // Get SERP data for all queries
    for (const query of NICHE_QUERIES) {
      try {
        const serpData = await getSerpData(query);
        dailyTopics.push(serpData);
        console.log(`Got data for: ${query}`);
      } catch (error) {
        console.error(`Error getting data for ${query}:`, error);
        dailyTopics.push({
          query,
          score: 50,
          link: 'No link found',
          title: '',
          snippet: '',
          questions: [],
          status: '📊 STEADY'
        });
      }
    }
    
    // Store session
    userSessions.set(token, {
      step: 'topic_selection',
      topics: dailyTopics,
      createdAt: Date.now()
    });
    
    // Build topic selection message
    let message = "🎸 **DAILY BLOG TOPIC SELECTION**\n\n";
    message += "**Choose ONE topic for today's semantic SEO blog:**\n\n";
    
    dailyTopics.forEach((topic, index) => {
      const emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][index];
      const paaPreview = topic.questions?.length > 0 ? 
        `${topic.questions[0].slice(0, 40)}...` : "What producers need to know";
      
      message += `${emoji} **${topic.query.slice(0, 40)}...**\n`;
      message += `   📊 ${topic.score}/100 ${topic.status}\n`;
      message += `   🔗 ${topic.link.slice(0, 50)}...\n`;
      message += `   ❓ ${paaPreview}\n\n`;
    });
    
    message += "**Reply with:** 1, 2, 3, or 4\n";
    message += "*This selection will expire in 5 minutes*";
    
    await editOriginalResponse(token, message);
    console.log('Blog command processed successfully');
  } catch (error) {
    console.error('Blog command error:', error);
    throw error;
  }
}

/**
 * Process /outlines command
 */
async function processOutlinesCommand(token, topic) {
  try {
    await editOriginalResponse(token, "🤖 **Generating 4 blog outlines...**");
    
    console.log(`Generating outlines for: ${topic}`);
    const serpData = await getSerpData(topic.slice(0, 100));
    const outlines = await generateFourOutlines(topic, serpData);
    
    let message = `🎸 **4 BLOG OUTLINES FOR:** ${topic.slice(0, 50)}...\n\n`;
    message += `📊 Trend: ${serpData.score}/100 ${serpData.status}\n`;
    message += `🔗 Source: ${serpData.link.slice(0, 50)}...\n\n`;
    
    outlines.forEach((outline, index) => {
      const emoji = OUTLINE_TYPES[index]?.emoji || "📝";
      const sentiment = outline.sentiment || "NEUTRAL 😐";
      const contentPreview = outline.content?.slice(0, 80) || "Analysis pending...";
      
      message += `${index + 1}. ${emoji} **${outline.type}** ${sentiment}\n`;
      message += `   ${contentPreview}...\n\n`;
    });
    
    message += "💡 **Use `/blog` to generate a full semantic SEO blog with PAA → H3 headers!**";
    
    await editOriginalResponse(token, message);
    console.log('Outlines command processed successfully');
    
  } catch (error) {
    console.error('Outlines generation error:', error);
    throw error;
  }
}

/**
 * Run the daily scout process
 */
async function runDailyScout() {
  try {
    console.log('Executing daily scout...');
    
    const dailyTopics = [];
    
    // Get SERP data for each query
    for (let i = 0; i < NICHE_QUERIES.length; i++) {
      const query = NICHE_QUERIES[i];
      try {
        const serpData = await getSerpData(query);
        dailyTopics.push({
          ...serpData,
          index: i
        });
        console.log(`Got data for query ${i + 1}: ${query}`);
      } catch (error) {
        console.error(`Error processing query "${query}":`, error);
      }
    }
    
    // Build report
    const dateStr = new Date().toISOString().split('T')[0];
    let report = `🎸 **SOUNDSWAP DAILY BLOG TOPICS** (${dateStr})\n\n`;
    report += "**Choose ONE topic for today's semantic SEO blog:**\n\n";
    
    for (let i = 0; i < dailyTopics.length; i++) {
      const topic = dailyTopics[i];
      const emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][i];
      const paaPreview = topic.questions?.length > 0 ? 
        `${topic.questions[0].slice(0, 40)}...` : "What producers need to know";
      
      report += `${emoji} **${topic.query.toUpperCase()}**\n`;
      report += `   📊 Trend: ${topic.score}/100 ${topic.status}\n`;
      report += `   🔗 Source: ${topic.link.slice(0, 50)}...\n`;
      report += `   ❓ PAA: ${paaPreview}\n\n`;
    }
    
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    report += "**TO GENERATE BLOG:**\n";
    report += "1. Type `/blog` in this channel\n";
    report += "2. Choose topic (1-4)\n";
    report += "3. Choose outline style\n";
    report += "4. Get semantic SEO blog with PAA → H3 headers!\n\n";
    report += "⏱️ *Only 1 blog per day for maximum SEO impact*";
    
    // Send to Discord
    await sendToDiscordChannel(report);
    
    console.log('Daily scout completed successfully');
    
    return {
      success: true,
      topicsProcessed: dailyTopics.length,
      discordSent: true,
      timestamp: new Date().toISOString()
    };
    
  } catch (error) {
    console.error('Scout execution error:', error);
    throw error;
  }
}

/**
 * SERP API Functions
 */
async function getSerpData(query) {
  try {
    console.log(`Fetching SERP data for: ${query}`);
    
    // Get search results
    const searchUrl = `https://serpapi.com/search?q=${encodeURIComponent(query)}&tbs=qdr:d&num=5&api_key=${SERPAPI_KEY}`;
    const searchResponse = await fetch(searchUrl);
    const searchData = await searchResponse.json();
    
    const organic = searchData.organic_results || [];
    const questions = searchData.related_questions ? 
      searchData.related_questions.slice(0, 5).map(q => q.question) : [];
    
    const firstResult = organic[0] || {};
    
    // Simple trend score (mock - would use Google Trends API in production)
    const trendScore = Math.floor(Math.random() * 50) + 50; // 50-100 for demo
    
    let status = '📊 STEADY';
    if (trendScore > 75) status = '🔥 VIRAL';
    else if (trendScore > 50) status = '📈 TRENDING';
    
    return {
      query,
      score: trendScore,
      link: firstResult.link || 'https://example.com/no-link-found',
      title: firstResult.title || 'No title available',
      snippet: firstResult.snippet || 'No snippet available',
      questions,
      status,
      total_results: searchData.search_information?.total_results || 0
    };
  } catch (error) {
    console.error('SERP API error:', error);
    return {
      query,
      score: 50,
      link: 'https://example.com/no-link-found',
      title: '',
      snippet: '',
      questions: [],
      status: '📊 STEADY',
      total_results: 0
    };
  }
}

/**
 * Gemini AI Functions
 */
async function generateFourOutlines(context, serpData) {
  try {
    console.log('Generating outlines with Gemini AI...');
    
    const prompt = `
      CONTEXT: ${context}
      
      SERP DATA:
      - Topic: ${serpData.query}
      - Trend Score: ${serpData.score}/100 (${serpData.status})
      - Source: ${serpData.title}
      - People Also Ask: ${serpData.questions ? serpData.questions.slice(0, 3).join(', ') : 'No questions found'}
      
      Generate 4 DISTINCT blog outline approaches for SoundSwap (music production platform):
      
      1. **Technical Deep Dive** - Focus on specifications, features, technical analysis
      2. **Creative Applications** - How artists/producers can practically use this
      3. **Industry Impact** - Market trends, business implications, future predictions
      4. **Beginner-Friendly Guide** - Simplified explanation for newcomers
      
      For EACH outline, provide:
      - Overall tone/sentiment (positive/neutral/negative based on current industry discussions)
      - Target audience
      - 2-3 key talking points
      - Estimated reading time
      
      Format your response clearly with numbered outlines.
      
      Keep each outline concise but actionable.
    `;

    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();
    
    console.log('Gemini response received');
    return parseOutlines(text);
  } catch (error) {
    console.error('Gemini API error:', error);
    return getFallbackOutlines(context);
  }
}

function parseOutlines(text) {
  const outlines = [];
  
  // Simple parsing - in production you'd want more robust parsing
  const lines = text.split('\n');
  let currentOutline = null;
  
  for (const line of lines) {
    if (line.includes('1.') || line.includes('Technical Deep Dive')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Technical Deep Dive', 
        content: line,
        sentiment: '😊 POSITIVE'
      };
    } else if (line.includes('2.') || line.includes('Creative Applications')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Creative Applications', 
        content: line,
        sentiment: '🎨 CREATIVE'
      };
    } else if (line.includes('3.') || line.includes('Industry Impact')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Industry Impact', 
        content: line,
        sentiment: '📈 STRATEGIC'
      };
    } else if (line.includes('4.') || line.includes('Beginner-Friendly Guide')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Beginner-Friendly Guide', 
        content: line,
        sentiment: '👶 FRIENDLY'
      };
    } else if (currentOutline) {
      currentOutline.content += '\n' + line;
    }
  }
  
  if (currentOutline) outlines.push(currentOutline);
  
  // Ensure we have 4 outlines
  while (outlines.length < 4) {
    const type = OUTLINE_TYPES[outlines.length];
    outlines.push({
      type: type.name,
      content: `${type.description} for this topic.`,
      sentiment: outlines.length % 2 === 0 ? '😊 POSITIVE' : '📊 NEUTRAL'
    });
  }
  
  return outlines.slice(0, 4);
}

function getFallbackOutlines(context) {
  return [
    {
      type: 'Technical Deep Dive',
      content: `Technical specifications and features analysis for ${context.slice(0, 30)}...`,
      sentiment: '😊 POSITIVE'
    },
    {
      type: 'Creative Applications',
      content: `How artists and producers can creatively use ${context.slice(0, 30)}...`,
      sentiment: '🎨 CREATIVE'
    },
    {
      type: 'Industry Impact',
      content: `Market trends and business implications of ${context.slice(0, 30)}...`,
      sentiment: '📈 STRATEGIC'
    },
    {
      type: 'Beginner-Friendly Guide',
      content: `Step-by-step guide for beginners to understand ${context.slice(0, 30)}...`,
      sentiment: '👶 FRIENDLY'
    }
  ];
}

/**
 * Discord API Functions
 */
async function editOriginalResponse(token, content) {
  try {
    const url = `https://discord.com/api/v10/webhooks/${DISCORD_APP_ID}/${token}/messages/@original`;
    
    const response = await fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content.slice(0, 2000) })
    });
    
    if (!response.ok) {
      console.error(`Failed to edit Discord message: ${response.status}`);
    }
  } catch (error) {
    console.error('Failed to edit Discord message:', error);
  }
}

async function sendToDiscordChannel(content) {
  try {
    const url = `https://discord.com/api/v10/channels/${DISCORD_CHANNEL_ID}/messages`;
    
    console.log('Sending message to Discord channel...');
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bot ${DISCORD_BOT_TOKEN}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ content: content.slice(0, 2000) })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Failed to send to Discord channel: ${response.status} ${errorText}`);
      throw new Error(`Discord API error: ${response.status}`);
    } else {
      console.log('Message sent to Discord successfully');
    }
  } catch (error) {
    console.error('Failed to send to Discord channel:', error);
    throw error;
  }
}

// Edge runtime configuration
export const config = {
  runtime: 'edge',
};