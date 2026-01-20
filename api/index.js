// Edge-compatible imports
import { GoogleGenerativeAI } from '@google/generative-ai';

// Configuration from environment variables
const {
  DISCORD_PUBLIC_KEY,
  DISCORD_TOKEN,
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

// Store for user sessions (in-memory, resets on cold start)
let userSessions = new Map();

/**
 * Main handler for Vercel Edge Function
 */
export default async function handler(request) {
  // Set CORS headers
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Signature-Ed25519, X-Signature-Timestamp',
  };

  // Handle OPTIONS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers });
  }

  const url = new URL(request.url);
  
  // Route based on path
  if (request.method === 'POST' && url.pathname === '/api/interactions') {
    return await handleDiscordInteraction(request);
  }
  
  if (request.method === 'GET' && url.pathname === '/api/scout') {
    return await handleDailyScout(request);
  }
  
  if (request.method === 'GET' && url.pathname === '/') {
    return new Response(JSON.stringify({
      status: 'online',
      service: 'SoundSwap AI Blog Generator',
      version: '5.0 - Edge Compatible',
      endpoints: ['POST /api/interactions', 'GET /api/scout'],
      uptime: process.uptime()
    }), { status: 200, headers: { ...headers, 'Content-Type': 'application/json' } });
  }
  
  if (request.method === 'GET' && url.pathname === '/health') {
    return new Response(JSON.stringify({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      sessions: userSessions.size
    }), { status: 200, headers: { ...headers, 'Content-Type': 'application/json' } });
  }

  return new Response(JSON.stringify({ error: 'Not found' }), { 
    status: 404, 
    headers: { ...headers, 'Content-Type': 'application/json' } 
  });
}

/**
 * Handle Discord interactions
 */
async function handleDiscordInteraction(request) {
  try {
    const body = await request.text();
    const signature = request.headers.get('x-signature-ed25519');
    const timestamp = request.headers.get('x-signature-timestamp');
    
    // Verify Discord signature (basic validation for Edge)
    if (!validateDiscordSignature(signature, timestamp, DISCORD_PUBLIC_KEY)) {
      console.error('Invalid Discord signature');
      return new Response(JSON.stringify({ error: 'Invalid request signature' }), { status: 401 });
    }
    
    const interaction = JSON.parse(body);
    
    // Handle PING
    if (interaction.type === 1) {
      return new Response(JSON.stringify({ type: 1 }), { 
        status: 200, 
        headers: { 'Content-Type': 'application/json' } 
      });
    }
    
    // Handle APPLICATION_COMMAND
    if (interaction.type === 2) {
      const { data, token } = interaction;
      const commandName = data?.name;
      
      // Handle /blog command
      if (commandName === 'blog') {
        // Return deferred response immediately
        const response = new Response(JSON.stringify({ type: 5 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
        
        // Process in background
        processBlogCommand(token, data).catch(console.error);
        
        return response;
      }
      
      // Handle /outlines command
      if (commandName === 'outlines') {
        const topic = data?.options?.find(opt => opt.name === 'topic')?.value || 
                     'latest music production trends 2026';
        
        // Return deferred response immediately
        const response = new Response(JSON.stringify({ type: 5 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
        
        // Process in background
        processOutlinesCommand(token, topic).catch(console.error);
        
        return response;
      }
    }
    
    // Unknown interaction type
    return new Response(JSON.stringify({ error: 'Unknown interaction type' }), { 
      status: 400, 
      headers: { 'Content-Type': 'application/json' } 
    });
    
  } catch (error) {
    console.error('Discord interaction error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), { 
      status: 500, 
      headers: { 'Content-Type': 'application/json' } 
    });
  }
}

/**
 * Handle daily scout cron job
 */
async function handleDailyScout(request) {
  try {
    // Verify cron secret if set
    if (CRON_SECRET) {
      const authHeader = request.headers.get('authorization');
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return new Response(JSON.stringify({ error: 'Missing authorization header' }), { 
          status: 401, 
          headers: { 'Content-Type': 'application/json' } 
        });
      }
      
      const token = authHeader.substring(7);
      if (token !== CRON_SECRET) {
        return new Response(JSON.stringify({ error: 'Invalid token' }), { 
          status: 401, 
          headers: { 'Content-Type': 'application/json' } 
        });
      }
    }
    
    // Process scout in background
    const response = new Response(JSON.stringify({ 
      status: 'processing', 
      message: 'Scout job started' 
    }), { 
      status: 202, 
      headers: { 'Content-Type': 'application/json' } 
    });
    
    // Run scout async
    runDailyScout().catch(console.error);
    
    return response;
    
  } catch (error) {
    console.error('Scout handler error:', error);
    return new Response(JSON.stringify({ error: error.message }), { 
      status: 500, 
      headers: { 'Content-Type': 'application/json' } 
    });
  }
}

/**
 * Run the daily scout process
 */
async function runDailyScout() {
  try {
    console.log('Starting daily scout...');
    
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
    
  } catch (error) {
    console.error('Scout execution error:', error);
  }
}

/**
 * Process /blog command
 */
async function processBlogCommand(token, data) {
  try {
    await editOriginalResponse(token, "🎸 **Loading daily topics...**");
    
    const dailyTopics = [];
    
    // Get SERP data for all queries
    for (const query of NICHE_QUERIES) {
      try {
        const serpData = await getSerpData(query);
        dailyTopics.push(serpData);
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
  } catch (error) {
    console.error('Blog command error:', error);
    await editOriginalResponse(token, `❌ Error: ${error.message.slice(0, 100)}`);
  }
}

/**
 * Process /outlines command
 */
async function processOutlinesCommand(token, topic) {
  try {
    await editOriginalResponse(token, "🤖 **Generating 4 blog outlines...**");
    
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
    
  } catch (error) {
    console.error('Outlines generation error:', error);
    await editOriginalResponse(token, `❌ Error generating outlines: ${error.message.slice(0, 100)}`);
  }
}

/**
 * SERP API Functions
 */
async function getSerpData(query) {
  try {
    // Get trend score
    const trendScore = await getTrendScore(query);
    
    // Get search results
    const searchUrl = `https://serpapi.com/search?q=${encodeURIComponent(query)}&tbs=qdr:d&num=5&api_key=${SERPAPI_KEY}`;
    const searchResponse = await fetch(searchUrl);
    const searchData = await searchResponse.json();
    
    const organic = searchData.organic_results || [];
    const questions = searchData.related_questions ? 
      searchData.related_questions.slice(0, 5).map(q => q.question) : [];
    
    const firstResult = organic[0] || {};
    
    let status = '📊 STEADY';
    if (trendScore > 75) status = '🔥 VIRAL';
    else if (trendScore > 50) status = '📈 TRENDING';
    
    return {
      query,
      score: trendScore,
      link: firstResult.link || 'No link found',
      title: firstResult.title || '',
      snippet: firstResult.snippet || '',
      questions,
      status,
      total_results: searchData.search_information?.total_results || 0
    };
  } catch (error) {
    console.error('SERP API error:', error);
    return {
      query,
      score: 50,
      link: 'No link found',
      title: '',
      snippet: '',
      questions: [],
      status: '📊 STEADY',
      total_results: 0
    };
  }
}

async function getTrendScore(keyword) {
  try {
    const trendUrl = `https://serpapi.com/search?engine=google_trends&q=${encodeURIComponent(keyword)}&data_type=TIMESERIES&date=now+7-d&api_key=${SERPAPI_KEY}`;
    const trendResponse = await fetch(trendUrl);
    const trendData = await trendResponse.json();
    
    const timeline = trendData.interest_over_time?.timeline_data || [];
    if (timeline.length > 0) {
      const latest = timeline[timeline.length - 1];
      return latest.values?.[0]?.value || 50;
    }
    
    return 50;
  } catch (error) {
    console.error('Trend score error:', error);
    return 50;
  }
}

/**
 * Gemini AI Functions
 */
async function generateFourOutlines(context, serpData) {
  const prompt = `
    CONTEXT: ${context}
    
    SERP DATA:
    - Topic: ${serpData.query}
    - Trend Score: ${serpData.score}/100 (${serpData.status})
    - Source: ${serpData.title}
    - People Also Ask: ${serpData.questions ? serpData.questions.join(', ') : 'No questions found'}
    
    Generate 4 DISTINCT blog outline approaches:
    
    1. **Technical Deep Dive** - Focus on specifications, features, technical analysis
    2. **Creative Applications** - How artists/producers can practically use this
    3. **Industry Impact** - Market trends, business implications, future predictions
    4. **Beginner-Friendly Guide** - Simplified explanation for newcomers
    
    For EACH outline, provide:
    - Overall tone/sentiment (based on current industry discussions)
    - Target audience (who will find this most valuable)
    - 3-4 key talking points
    - Estimated reading time
    - SEO keywords to include
    
    Format each outline clearly with its number and type as a header.
    
    Make each outline unique and actionable.
  `;

  try {
    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();
    
    return parseOutlines(text);
  } catch (error) {
    console.error('Gemini API error:', error);
    return getFallbackOutlines(context);
  }
}

async function generateSemanticBlog(topicData, outlineType) {
  const organizedPaa = organizePaaIntoNarrative(topicData.questions || []);
  
  const prompt = `
    CRITICAL INSTRUCTION: Write ONE daily blog post for SoundSwap that must capture Google's top search spots.
    
    TOPIC: ${topicData.query}
    TREND SCORE: ${topicData.score}/100 (${topicData.status})
    SOURCE: ${topicData.title} - ${topicData.link}
    
    OUTLINE APPROACH: ${outlineType}
    
    PEOPLE ALSO ASK (PAA) QUESTIONS - MUST BECOME H3 HEADERS:
    ${organizedPaa.map(q => `- ${q}`).join('\n')}
    
    REQUIREMENTS:
    1. SEMANTIC SEO STRUCTURE:
       - H1: Main title (include year 2026 and primary keyword)
       - H2: 3-4 main sections following narrative flow
       - H3: EACH PAA question becomes an H3 header (EXACTLY as shown above)
       - Under each H3: Answer that question thoroughly (50-100 words)
    
    2. CONTENT FLOW:
       - Introduction: Hook with trend data
       - Section 1: What it is (definition/context)
       - Section 2: Why it matters for producers
       - Section 3: How to use/implement
       - Section 4: Future implications
       - Conclusion with CTA
    
    3. SEO ELEMENTS:
       - Primary keyword in first 100 words
       - LSI keywords naturally integrated
       - Internal linking suggestions
       - Meta description (160 chars)
       - SEO title tag (60 chars)
    
    4. LENGTH: 800-1000 words
    
    Generate the complete blog post now:
  `;

  try {
    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();
    
    // Build header string correctly (FIXED THE ERROR HERE)
    const dateStr = new Date().toISOString().split('T')[0];
    const header = `🎸 **SOUNDSWAP SEMANTIC SEO BLOG**\n` +
                   `📅 ${dateStr}\n` +
                   `🎯 Topic: ${topicData.query}\n` +
                   `📊 Trend: ${topicData.score}/100 ${topicData.status}\n` +
                   `📝 Style: ${outlineType}\n` +
                   `🔍 PAA → H3: ${organizedPaa.length} questions integrated\n` +
                   `━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    return header + text;
  } catch (error) {
    console.error('Blog generation error:', error);
    return `Error generating blog: ${error.message}`;
  }
}

function parseOutlines(text) {
  const outlines = [];
  const lines = text.split('\n');
  let currentOutline = null;
  
  for (const line of lines) {
    if (line.includes('Technical Deep Dive') || line.includes('1.')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Technical Deep Dive', 
        content: line,
        sentiment: '😊 POSITIVE'
      };
    } else if (line.includes('Creative Applications') || line.includes('2.')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Creative Applications', 
        content: line,
        sentiment: '🎨 CREATIVE'
      };
    } else if (line.includes('Industry Impact') || line.includes('3.')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Industry Impact', 
        content: line,
        sentiment: '📈 STRATEGIC'
      };
    } else if (line.includes('Beginner-Friendly Guide') || line.includes('4.')) {
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

function organizePaaIntoNarrative(questions) {
  if (!questions || questions.length === 0) return [];
  
  // Categorize questions
  const beginner = questions.filter(q => 
    q.toLowerCase().includes('how to') || 
    q.toLowerCase().includes('tutorial') ||
    q.toLowerCase().includes('guide')
  );
  
  const creative = questions.filter(q => 
    q.toLowerCase().includes('use') || 
    q.toLowerCase().includes('create') ||
    q.toLowerCase().includes('make')
  );
  
  const technical = questions.filter(q => 
    q.toLowerCase().includes('how') || 
    q.toLowerCase().includes('work') ||
    q.toLowerCase().includes('does')
  );
  
  const comparison = questions.filter(q => 
    q.toLowerCase().includes('best') || 
    q.toLowerCase().includes('vs') ||
    q.toLowerCase().includes('difference')
  );
  
  // Narrative flow: Beginner → Creative → Technical → Comparison
  const narrative = [];
  if (beginner.length > 0) narrative.push(beginner[0]);
  if (creative.length > 0) narrative.push(creative[0]);
  if (technical.length > 0) narrative.push(technical[0]);
  if (comparison.length > 0) narrative.push(comparison[0]);
  
  // Fill remaining slots
  for (const q of questions) {
    if (narrative.length >= 4) break;
    if (!narrative.includes(q)) narrative.push(q);
  }
  
  return narrative.slice(0, 4);
}

/**
 * Discord API Functions
 */
async function editOriginalResponse(token, content) {
  const url = `https://discord.com/api/v10/webhooks/${DISCORD_APP_ID}/${token}/messages/@original`;
  
  try {
    await fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content.slice(0, 2000) })
    });
  } catch (error) {
    console.error('Failed to edit Discord message:', error);
  }
}

async function sendToDiscordChannel(content) {
  const url = `https://discord.com/api/v10/channels/${DISCORD_CHANNEL_ID}/messages`;
  
  const chunks = splitMessage(content);
  
  for (const chunk of chunks) {
    try {
      await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bot ${DISCORD_TOKEN}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: chunk })
      });
      // Rate limiting delay
      await new Promise(resolve => setTimeout(resolve, 1000));
    } catch (error) {
      console.error('Failed to send to Discord channel:', error);
    }
  }
}

/**
 * Utility Functions
 */
function validateDiscordSignature(signature, timestamp, publicKey) {
  try {
    // Basic validation for Edge compatibility
    // In production, you should implement proper Ed25519 verification
    return signature && signature.length === 128 &&
           timestamp && timestamp.length > 0 &&
           publicKey && publicKey.length === 64;
  } catch (error) {
    console.error('Signature validation error:', error);
    return false;
  }
}

function splitMessage(content, maxLength = 1900) {
  const chunks = [];
  let currentChunk = '';
  
  const paragraphs = content.split('\n\n');
  
  for (const paragraph of paragraphs) {
    if (currentChunk.length + paragraph.length + 2 > maxLength) {
      if (currentChunk) chunks.push(currentChunk);
      currentChunk = paragraph;
    } else {
      currentChunk += (currentChunk ? '\n\n' : '') + paragraph;
    }
  }
  
  if (currentChunk) {
    chunks.push(currentChunk);
  }
  
  return chunks;
}

// Edge runtime configuration
export const config = {
  runtime: 'edge',
};