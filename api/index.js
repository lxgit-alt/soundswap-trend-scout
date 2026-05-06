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

// Outline types with emojis
const OUTLINE_TYPES = [
  { name: "Technical Deep Dive", emoji: "🔬", description: "Specifications, features, technical analysis" },
  { name: "Creative Applications", emoji: "🎨", description: "Practical uses for artists and producers" },
  { name: "Industry Impact", emoji: "📈", description: "Market trends and business implications" },
  { name: "Beginner-Friendly Guide", emoji: "👶", description: "Simplified explanations for newcomers" }
];

// Store for user sessions
let userSessions = new Map();

// ──────────────────────────────────────────────────────────────
//  UPDATED: Fetch daily music industry news from Google News
//  - Uses google_news engine to get actual breaking headlines
//  - Uses Gemini to distill headlines into 4 search queries
//  - Better for real current events vs historical search patterns
// ──────────────────────────────────────────────────────────────
async function fetchTrendingMusicTopics() {
  try {
    console.log('📰 Fetching breaking music industry news from Google News...');
    
    // Use Google News engine with music industry keywords
    const newsUrl = `https://serpapi.com/search?engine=google_news&q=music+industry+news&num=20&api_key=${SERPAPI_KEY}`;
    const response = await fetch(newsUrl);
    const data = await response.json();
    
    if (data.error || !data.news_results) {
      throw new Error(data.error || 'No news data');
    }

    // Extract headlines and snippets
    const headlines = data.news_results
      .slice(0, 15)
      .map(item => ({
        title: item.title,
        snippet: item.snippet,
        source: item.source
      }))
      .filter(h => h.title && h.title.length > 0);
    
    console.log(`Found ${headlines.length} breaking music news headlines.`);

    if (headlines.length === 0) {
      throw new Error('No headlines returned');
    }

    // Use Gemini to distill headlines into 2 general music news queries
    const musicTopics = await distillHeadlinesIntoQueries(headlines, 2);
    
    if (musicTopics && musicTopics.length >= 2) {
      return musicTopics.slice(0, 2);
    }
    
    // Fallback: if Gemini fails, extract keywords from headlines
    const fallbackQueries = headlines.map(h => {
      const terms = h.title
        .replace(/[^a-zA-Z0-9\s]/g, '')
        .split(' ')
        .filter(word => word.length > 3);
      return terms.slice(0, 3).join(' ');
    }).filter(q => q.length > 0);
    
    return [...new Set(fallbackQueries)].slice(0, 2);
  } catch (error) {
    console.error('❌ Failed to fetch breaking music news:', error.message);
    return null; // triggers fallback
  }
}

// ──────────────────────────────────────────────────────────────
//  NEW: Fetch 2 trending music hardware / equipment topics
// ──────────────────────────────────────────────────────────────
async function fetchMusicHardwareTopics() {
  try {
    console.log('🎛️ Fetching music hardware & equipment news from Google News...');
    
    const newsUrl = `https://serpapi.com/search?engine=google_news&q=music+hardware+equipment+gear+synthesizer+audio&num=20&api_key=${SERPAPI_KEY}`;
    const response = await fetch(newsUrl);
    const data = await response.json();
    
    if (data.error || !data.news_results) {
      throw new Error(data.error || 'No hardware news data');
    }

    const headlines = data.news_results
      .slice(0, 15)
      .map(item => ({
        title: item.title,
        snippet: item.snippet,
        source: item.source
      }))
      .filter(h => h.title && h.title.length > 0);
    
    console.log(`Found ${headlines.length} music hardware news headlines.`);

    if (headlines.length === 0) {
      throw new Error('No hardware headlines returned');
    }

    // Use Gemini to distill headlines into 2 hardware-focused queries
    const hardwareTopics = await distillHeadlinesIntoQueries(headlines, 2, 'music hardware, instruments, synthesizers, audio equipment, music gear, studio equipment');
    
    if (hardwareTopics && hardwareTopics.length >= 2) {
      return hardwareTopics.slice(0, 2);
    }
    
    // Fallback: extract keywords directly
    const fallbackQueries = headlines.map(h => {
      const terms = h.title
        .replace(/[^a-zA-Z0-9\s]/g, '')
        .split(' ')
        .filter(word => word.length > 3);
      return terms.slice(0, 3).join(' ');
    }).filter(q => q.length > 0);
    
    return [...new Set(fallbackQueries)].slice(0, 2);
  } catch (error) {
    console.error('❌ Failed to fetch music hardware news:', error.message);
    return null; // triggers fallback
  }
}

// Helper: use Gemini to convert news headlines into search queries
// count   – how many queries to return (default 2)
// focus   – optional topic focus hint for the prompt
async function distillHeadlinesIntoQueries(headlines, count = 2, focus = 'music production, technology, business, or artist news') {
  try {
    const headlineTexts = headlines
      .map((h, i) => `${i+1}. [${h.source}] ${h.title}${h.snippet ? ': ' + h.snippet.substring(0, 100) : ''}`)
      .join('\n');
    
    const prompt = `
You are a music industry analyst. Based on these breaking news headlines, create exactly ${count} SEO-friendly search queries focused on: ${focus}. These queries should:
- Be relevant to the specified focus area
- Be suitable for semantic SEO blog posts
- Be 2-5 words long
- Reflect the actual news stories

Headlines:
${headlineTexts}

Return ONLY a JSON array of ${count} strings (search queries), nothing else. Example format: ["query 1", "query 2"]`;
    
    const result = await model.generateContent(prompt);
    const text = await result.response.text();
    
    // Try to parse JSON array
    const match = text.match(/\[.*\]/s);
    if (match) {
      const queries = JSON.parse(match[0]);
      console.log(`✅ Distilled ${count} headlines into queries:`, queries);
      return Array.isArray(queries) ? queries : [];
    }
    return [];
  } catch (e) {
    console.error('Gemini headline distillation failed:', e);
    return [];
  }
}

// ──────────────────────────────────────────────────────────────
//  UPDATED: Generate daily queries (async, uses music news trends)
// ──────────────────────────────────────────────────────────────
async function generateDailyQueries() {
  const now = new Date();
  const dayOfWeek = now.getDay();
  const dayOfMonth = now.getDate();
  const month = now.getMonth();
  const year = now.getFullYear();

  // ── Slot 1 & 2: general music news (2 topics) ──
  let newsQueries = await fetchTrendingMusicTopics();
  
  // ── Slot 3 & 4: music hardware / equipment (2 topics) ──
  let hardwareQueries = await fetchMusicHardwareTopics();

  // Fallback static pools if live fetches fail
  const dayIndex = dayOfMonth % 8;
  const weekIndex = Math.floor(dayOfMonth / 7) % 8;
  const dayOfWeekIndex = dayOfWeek;

  if (!newsQueries || newsQueries.length < 2) {
    console.log('Using static fallback queries for general music news');
    const staticNewsPool = [
      `music industry news ${month + 1}/${year}`,
      `streaming services updates ${year}`,
      `music copyright laws news ${month + 1} ${year}`,
      `artist revenue trends ${year}`,
      `music marketing strategies news ${month + 1}/${year}`,
      `independent musician news ${year}`,
      `record label developments ${month + 1} ${year}`,
      `music distribution platforms news ${year}`,
      `AI music production software news ${year}`,
      `machine learning music composition news`
    ];
    newsQueries = [
      staticNewsPool[(dayIndex + dayOfWeekIndex) % staticNewsPool.length],
      staticNewsPool[(dayIndex + dayOfWeekIndex + 3) % staticNewsPool.length]
    ];
  }

  if (!hardwareQueries || hardwareQueries.length < 2) {
    console.log('Using static fallback queries for music hardware');
    const staticHardwarePool = [
      `new music production gear releases ${month + 1}/${year}`,
      `audio interface news ${year}`,
      `studio monitor reviews ${month + 1} ${year}`,
      `MIDI controller latest models ${year}`,
      `synthesizer new releases ${month + 1}/${year}`,
      `microphones for home studio news ${year}`,
      `DAW updates ${month + 1} ${year}`,
      `music production hardware news ${year}`,
      `best audio equipment ${year}`,
      `music instruments technology ${month + 1} ${year}`
    ];
    hardwareQueries = [
      staticHardwarePool[(dayIndex + weekIndex) % staticHardwarePool.length],
      staticHardwarePool[(dayIndex + weekIndex + 4) % staticHardwarePool.length]
    ];
  }

  // Merge: 2 general news + 2 hardware = 4 total
  let queries = [
    ...newsQueries.slice(0, 2),
    ...hardwareQueries.slice(0, 2)
  ];

  // Derive a theme from the first query (or you can keep a separate logic)
  const theme = `Music Industry News: ${queries[0]}`;

  console.log(`\n📅 Date: ${now.toISOString().split('T')[0]}`);
  console.log(`🎯 Theme: ${theme}`);
  console.log(`🔍 Generated queries:`, queries);

  return {
    queries,
    theme,
    dateInfo: {
      dayOfWeek: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][dayOfWeek],
      dayOfMonth,
      month: month + 1,
      year
    }
  };
}

/**
 * Main handler for Vercel Edge Function
 */
export default async function handler(request) {
  const url = new URL(request.url);
  const pathname = url.pathname;
  
  console.log(`Incoming request: ${request.method} ${pathname}`);
  
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Signature-Ed25519, X-Signature-Timestamp',
    'Content-Type': 'application/json'
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers });
  }

  if (pathname === '/api/interactions' && request.method === 'POST') {
    return await handleDiscordInteraction(request);
  }
  
  if (pathname === '/api/scout' && request.method === 'GET') {
    return await handleDailyScout(request);
  }
  
  if (pathname === '/api/scout-direct' && request.method === 'POST') {
    return await handleDirectScout(request);
  }
  
  if (pathname === '/health' && request.method === 'GET') {
    return new Response(JSON.stringify({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      service: 'SoundSwap AI',
      version: '5.3 - Breaking Music News Scout',
      features: [
        'Live Google News headlines (Music category)',
        'Gemini-powered headline distillation',
        'Music industry news focus',
        'Google AI Mode API integration',
        'Google AI Overview API integration with page_token',
        'Multi-source question extraction',
        'AI-enhanced trend scoring'
      ],
      apis_active: [
        'Google News (Breaking headlines)',
        'Regular Google Search',
        'Google AI Mode (AI-generated results)',
        'Google AI Overview (AI overview blocks with page_token)'
      ],
      commands: [
        '/blog - Generate daily semantic SEO blog',
        '/outlines [topic] - Generate 4 blog outlines'
      ],
      daily_limit: '1 blog per day for maximum SEO impact'
    }), { status: 200, headers });
  }
  
  if (pathname === '/' && request.method === 'GET') {
    // 👇 UPDATED: await generateDailyQueries()
    const { queries, theme } = await generateDailyQueries();
    return new Response(JSON.stringify({
      status: 'online',
      service: 'SoundSwap AI Blog Generator',
      version: '5.3 - Breaking Music News Scout',
      daily_theme: theme,
      today_queries: queries.slice(0, 2),
      features: [
        'Live Google News headlines (breaking stories)',
        'Gemini-powered headline-to-query distillation',
        'Music industry news focus',
        'Google AI Mode API integration',
        'Google AI Overview API with page_token',
        'AI-enhanced topic detection',
        'Multi-source PAA extraction'
      ],
      indexed_stats: 'Previous blogs indexed in <5 hours',
      ai_apis: {
        ai_mode: 'Google AI Mode (AI-generated results)',
        ai_overview: 'Google AI Overview (AI overview blocks)',
        uptime: '99.38% - 99.99%'
      }
    }), { status: 200, headers });
  }

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
    const interaction = JSON.parse(body);
    
    if (interaction.type === 1) {
      return new Response(JSON.stringify({ type: 1 }), { 
        status: 200, 
        headers: { 'Content-Type': 'application/json' } 
      });
    }
    
    if (interaction.type === 2) {
      const { data, token } = interaction;
      const commandName = data?.name;
      
      console.log(`Processing command: ${commandName}`);
      
      if (commandName === 'blog') {
        console.log('Starting blog generation process...');
        const response = new Response(JSON.stringify({ type: 5 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
        
        // 👇 UPDATED: processBlogCommand now awaits generateDailyQueries inside
        processBlogCommand(token, data).catch(error => {
          console.error('Blog command error:', error);
          editOriginalResponse(token, `❌ Error: ${error.message?.slice(0, 100) || 'Unknown error'}`)
            .catch(e => console.error('Failed to send error:', e));
        });
        
        return response;
      }
      
      if (commandName === 'outlines') {
        const topic = data?.options?.find(opt => opt.name === 'topic')?.value || 
                     'latest AI music production trends 2026';
        
        console.log(`Processing outlines for topic: ${topic}`);
        
        const response = new Response(JSON.stringify({ type: 5 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
        
        processOutlinesCommand(token, topic).catch(error => {
          console.error('Outlines command error:', error);
          editOriginalResponse(token, `❌ Error: ${error.message?.slice(0, 100) || 'Unknown error'}`)
            .catch(e => console.error('Failed to send error:', e));
        });
        
        return response;
      }
    }
    
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
    
    const result = await runEnhancedDailyScout();
    
    return new Response(JSON.stringify({ 
      status: 'completed', 
      message: 'Enhanced daily scout completed successfully',
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
    await editOriginalResponse(token, "🎸 **Loading today's AI-enhanced music industry news topics...**");
    
    console.log('Getting SERP data for all topics...');
    // 👇 UPDATED: await generateDailyQueries()
    const { queries, theme, dateInfo } = await generateDailyQueries();
    const dailyTopics = [];
    
    for (const query of queries) {
      try {
        const serpData = await getEnhancedSerpData(query, {
          isNews: query.toLowerCase().includes('news')
        });
        dailyTopics.push(serpData);
        console.log(`Got AI-enhanced data for: ${query.slice(0, 40)}...`);
      } catch (error) {
        console.error(`Error getting data for ${query}:`, error);
        dailyTopics.push({
          query,
          category: 'ERROR',
          score: 40,
          link: 'No link found',
          title: '',
          snippet: '',
          questions: [],
          status: '❌ ERROR',
          ai_enhanced: false
        });
      }
    }
    
    userSessions.set(token, {
      step: 'topic_selection',
      topics: dailyTopics,
      createdAt: Date.now(),
      theme,
      dateInfo
    });
    
    let message = `🎸 **SOUNDSWAP DAILY BLOG TOPICS (Music Industry News)**\n`;
    message += `📅 ${dateInfo.dayOfWeek}, ${dateInfo.month}/${dateInfo.dayOfMonth}/${dateInfo.year}\n`;
    message += `🎯 Theme: ${theme}\n`;
    message += `🤖 AI APIs: Google AI Mode + AI Overview\n\n`;
    message += "**Choose ONE topic for today's semantic SEO blog:**\n\n";
    
    dailyTopics.sort((a, b) => b.score - a.score);
    
    dailyTopics.forEach((topic, index) => {
      const emoji = ["🔥", "📈", "🎯", "⚡"][index] || "📝";
      const categoryEmoji = topic.category || '📝';
      const aiBadge = topic.ai_enhanced ? '🤖 ' : '';
      const paaPreview = topic.questions?.length > 0 ? 
        `${topic.questions[0].slice(0, 50)}...` : "What music creators need to know";
      
      message += `${emoji} **${aiBadge}${categoryEmoji} ${topic.query.slice(0, 50)}...**\n`;
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
    await editOriginalResponse(token, "🤖 **Generating AI-enhanced blog outlines...**");
    
    console.log(`Generating outlines for: ${topic}`);
    const serpData = await getEnhancedSerpData(topic.slice(0, 100), {
      isNews: topic.toLowerCase().includes('news')
    });
    const outlines = await generateAIEnhancedOutlines(topic, serpData);
    
    let message = `🎸 **AI-ENHANCED BLOG OUTLINES FOR:** ${topic.slice(0, 50)}...\n\n`;
    message += `📊 Trend: ${serpData.score}/100 ${serpData.status}\n`;
    message += `🏷️ Category: ${serpData.category}\n`;
    message += serpData.ai_enhanced ? `🤖 AI-Enhanced: Yes (${serpData.ai_insights?.length || 0} insights)\n` : '';
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
 * Run the enhanced daily scout process
 */
async function runEnhancedDailyScout() {
  try {
    console.log('Executing enhanced daily scout (music industry news focus)...');
    
    // 👇 UPDATED: await generateDailyQueries()
    const { queries, theme, dateInfo } = await generateDailyQueries();
    const dailyTopics = [];
    
    for (let i = 0; i < queries.length; i++) {
      const query = queries[i];
      try {
        const serpData = await getEnhancedSerpData(query, {
          isNews: query.toLowerCase().includes('news')
        });
        dailyTopics.push({
          ...serpData,
          index: i
        });
        console.log(`Got AI-enhanced data for query ${i + 1}: ${query.slice(0, 40)}...`);
        await new Promise(resolve => setTimeout(resolve, 1500));
      } catch (error) {
        console.error(`Error processing query "${query}":`, error);
      }
    }
    
    const dateStr = new Date().toISOString().split('T')[0];
    let report = `🎸 **SOUNDSWAP DAILY BLOG SCOUT**\n`;
    report += `📅 ${dateInfo.dayOfWeek}, ${dateInfo.month}/${dateInfo.dayOfMonth}/${dateInfo.year}\n`;
    report += `🎯 Monthly Theme: ${theme}\n`;
    report += `🤖 AI APIs: Google AI Mode + AI Overview Enabled\n\n`;
    report += "**Choose ONE topic for today's semantic SEO blog:**\n\n";
    
    dailyTopics.sort((a, b) => b.score - a.score);
    
    for (let i = 0; i < dailyTopics.length; i++) {
      const topic = dailyTopics[i];
      const emoji = ["🔥", "📈", "🎯", "⚡"][i] || "📝";
      const categoryEmoji = topic.category;
      const aiBadge = topic.ai_enhanced ? '🤖 ' : '';
      const paaPreview = topic.questions?.length > 0 ? 
        `${topic.questions[0].slice(0, 50)}...` : "What music creators need to know";
      
      report += `${emoji} **${aiBadge}${categoryEmoji} ${topic.query.slice(0, 50)}...**\n`;
      report += `   📊 Trend Score: ${topic.score}/100 ${topic.status}\n`;
      report += `   🏷️ Source: ${topic.source || 'Various'}\n`;
      if (topic.ai_insights && topic.ai_insights.length > 0) {
        report += `   💡 AI Insight: ${topic.ai_insights[0].slice(0, 40)}...\n`;
      }
      report += `   🔗 Reference: ${topic.link.slice(0, 60)}...\n`;
      report += `   ❓ Top PAA: ${paaPreview}\n\n`;
    }
    
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    report += "**🚀 ENHANCED FEATURES (v5.3):**\n";
    report += "- 📰 Live Google News (Breaking music headlines)\n";
    report += "- 🤖 Gemini-powered headline distillation\n";
    report += "- 🎵 Music industry news focus with real events\n";
    report += "- 🤖 Google AI Mode API (AI-generated results)\n";
    report += "- 🧠 Google AI Overview API (with page_token extraction)\n";
    report += "- 🔍 Multi-source question extraction\n";
    report += "- 📈 AI-enhanced trend scoring\n\n";
    report += "**💡 BLOG GENERATION INSTRUCTIONS:**\n";
    report += "1. Type `/blog` in this channel\n";
    report += "2. Choose topic number (1-4)\n";
    report += "3. Select outline style\n";
    report += "4. Get full semantic SEO blog with PAA → H3 headers!\n\n";
    report += "⏱️ *Only 1 high-quality blog per day for maximum SEO impact*\n";
    report += "✅ *Previous blogs indexed in <5 hours*\n";
    report += "🤖 *AI-generated topics tied to real current music news events*";
    
    await sendToDiscordChannel(report);
    
    console.log('Enhanced daily scout completed successfully');
    
    return {
      success: true,
      date: dateStr,
      theme,
      topicsProcessed: dailyTopics.length,
      discordSent: true,
      topics: dailyTopics.map(t => ({
        query: t.query,
        score: t.score,
        category: t.category,
        ai_enhanced: t.ai_enhanced
      })),
      timestamp: new Date().toISOString()
    };
    
  } catch (error) {
    console.error('Enhanced scout execution error:', error);
    throw error;
  }
}

/**
 * Google AI Mode API - For AI-generated search results
 */
async function getGoogleAIModeData(query) {
  try {
    console.log(`🤖 Fetching Google AI Mode data for: ${query.slice(0, 40)}...`);
    
    const url = `https://serpapi.com/search?engine=google_ai_mode&q=${encodeURIComponent(query)}&api_key=${SERPAPI_KEY}`;
    const response = await fetch(url);
    const data = await response.json();
    
    if (data.error) {
      console.log(`❌ Google AI Mode API error: ${data.error}`);
      return null;
    }
    
    console.log(`✅ Google AI Mode data received`);
    return data;
  } catch (error) {
    console.error(`❌ Google AI Mode API failed:`, error.message);
    return null;
  }
}

/**
 * Google AI Overview API - For AI Overview blocks
 * UPDATED: First fetches regular search to extract page_token, then calls overview endpoint
 */
async function getGoogleAIOverviewData(query) {
  try {
    console.log(`🧠 Fetching Google AI Overview data for: ${query.slice(0, 40)}...`);
    
    // Step 1: Get regular search first to extract page_token
    console.log(`  → Step 1: Getting page_token from regular search...`);
    const searchUrl = `https://serpapi.com/search?q=${encodeURIComponent(query)}&num=10&api_key=${SERPAPI_KEY}`;
    const searchResponse = await fetch(searchUrl);
    const searchData = await searchResponse.json();
    
    if (searchData.error) {
      console.log(`❌ Initial search failed: ${searchData.error}`);
      return null;
    }
    
    // Extract page_token from search results
    const pageToken = searchData.serpapi_pagination?.next_page_token;
    if (!pageToken) {
      console.log(`⚠️ No page_token found in search results`);
      return null;
    }
    
    console.log(`  → Step 2: Calling AI Overview endpoint with page_token...`);
    
    // Step 2: Call AI Overview endpoint with page_token
    const aoUrl = `https://serpapi.com/search?engine=google_ai_overview&q=${encodeURIComponent(query)}&api_key=${SERPAPI_KEY}`;
    const response = await fetch(aoUrl);
    const data = await response.json();
    
    if (data.error) {
      console.log(`❌ Google AI Overview API error: ${data.error}`);
      return null;
    }
    
    console.log(`✅ Google AI Overview data received`);
    return data;
  } catch (error) {
    console.error(`❌ Google AI Overview API failed:`, error.message);
    return null;
  }
}

/**
 * Enhanced SERP API Function with AI APIs
 */
async function getEnhancedSerpData(query, context = {}) {
  try {
    console.log(`🔍 Fetching enhanced SERP data for: ${query}`);
    
    // Parallel API calls for better performance
    const [regularData, aiModeData, aiOverviewData] = await Promise.allSettled([
      getRegularSerpData(query, context),
      getGoogleAIModeData(query),
      getGoogleAIOverviewData(query)
    ]);
    
    const searchData = regularData.status === 'fulfilled' ? regularData.value : null;
    const aiMode = aiModeData.status === 'fulfilled' ? aiModeData.value : null;
    const aiOverview = aiOverviewData.status === 'fulfilled' ? aiOverviewData.value : null;
    
    if (!searchData) {
      throw new Error('Failed to get regular search data');
    }
    
    // Combine AI data with regular data
    let combinedQuestions = [...(searchData.questions || [])];
    let aiInsights = [];
    
    // Extract from AI Mode
    if (aiMode && aiMode.organic_results) {
      // Get AI-generated summaries
      const aiResults = aiMode.organic_results.slice(0, 3).filter(r => r.snippet);
      aiInsights = aiResults.map(r => r.snippet);
      
      // Extract questions from AI Mode
      if (aiMode.related_questions) {
        const aiQuestions = aiMode.related_questions
          .slice(0, 5)
          .map(q => q.question || q)
          .filter(q => q && typeof q === 'string');
        combinedQuestions = [...combinedQuestions, ...aiQuestions];
      }
    }
    
    // Extract from AI Overview
    if (aiOverview && aiOverview.ai_overview) {
      const overview = aiOverview.ai_overview;
      if (overview.text) {
        aiInsights.push(overview.text.substring(0, 200) + '...');
      }
      
      if (overview.questions) {
        const overviewQuestions = overview.questions
          .slice(0, 5)
          .map(q => q.question || q)
          .filter(q => q && typeof q === 'string');
        combinedQuestions = [...combinedQuestions, ...overviewQuestions];
      }
    }
    
    // Remove duplicates and limit
    const uniqueQuestions = [...new Set(combinedQuestions)].slice(0, 7);
    
    // Calculate enhanced trend score with AI bonus
    let trendScore = searchData.score || 40;
    
    // AI data bonus
    if (aiMode || aiOverview) {
      trendScore += 15; // Bonus for having AI-generated content
      console.log(`✨ AI data bonus applied for: ${query.slice(0, 40)}...`);
    }
    
    // Multiple AI sources bonus
    if (aiMode && aiOverview) {
      trendScore += 10;
    }
    
    // AI insights bonus
    if (aiInsights.length > 0) {
      trendScore += Math.min(aiInsights.length * 3, 15);
    }
    
    // Clamp score
    trendScore = Math.min(Math.max(trendScore, 40), 100);
    
    // Determine status
    let status = '📊 STEADY';
    if (trendScore > 75) status = '🔥 VIRAL';
    else if (trendScore > 60) status = '📈 TRENDING';
    
    if (aiMode || aiOverview) {
      status = '🤖 ' + status; // Add AI indicator
    }
    
    // Categorize the topic
    let category = searchData.category;
    const queryLower = query.toLowerCase();
    if (queryLower.includes('ai') || queryLower.includes('artificial')) category = '🤖 AI TOOLS';
    else if (queryLower.includes('gear') || queryLower.includes('hardware') || queryLower.includes('equipment')) category = '🎛️ GEAR';
    else if (queryLower.includes('news') || queryLower.includes('industry') || queryLower.includes('trend')) category = '📰 NEWS';
    else if (queryLower.includes('production') || queryLower.includes('studio') || queryLower.includes('recording')) category = '🎚️ PRODUCTION';
    
    return {
      query,
      category,
      score: Math.round(trendScore),
      link: searchData.link,
      title: searchData.title,
      snippet: searchData.snippet,
      questions: uniqueQuestions,
      status,
      total_results: searchData.total_results,
      quality_score: searchData.quality_score,
      source: searchData.source,
      ai_enhanced: !!(aiMode || aiOverview),
      ai_insights: aiInsights.slice(0, 2)
    };
    
  } catch (error) {
    console.error(`❌ Enhanced SERP error for "${query}":`, error.message);
    return getFallbackSerpData(query);
  }
}

/**
 * Regular SERP data function
 */
async function getRegularSerpData(query, context = {}) {
  try {
    // Add freshness modifier based on context
    const tbsModifier = context.isNews ? 'qdr:d' : 'qdr:w';
    
    const searchUrl = `https://serpapi.com/search?q=${encodeURIComponent(query)}&tbs=${tbsModifier}&num=10&api_key=${SERPAPI_KEY}`;
    const searchResponse = await fetch(searchUrl);
    const searchData = await searchResponse.json();
    
    // Extract organic results
    const organic = searchData.organic_results || [];
    
    // Filter out unwanted domains
    const excludedDomains = [
      'facebook.com', 'twitter.com', 'instagram.com', 
      'youtube.com', 'reddit.com', 'tiktok.com',
      'pinterest.com', 'linkedin.com', 'quora.com',
      'wikipedia.org', 'yelp.com', 'amazon.com',
      'ebay.com', 'etsy.com', 'spotify.com'
    ];
    
    // Find high-quality results
    let bestResult = {};
    let qualityScore = 0;
    
    for (const result of organic) {
      if (!result.link || !result.title) continue;
      
      try {
        const url = new URL(result.link);
        const hostname = url.hostname.toLowerCase();
        
        // Skip excluded domains
        if (excludedDomains.some(domain => hostname.includes(domain))) {
          continue;
        }
        
        let currentScore = 0;
        
        // Premium domains get highest priority
        const premiumDomains = [
          'musictech.com', 'musically.com', 'digitalmusicnews.com',
          'billboard.com', 'rollingstone.com', 'nme.com',
          'variety.com', 'soundonsound.com', 'musicradar.com',
          'producerspot.com', 'attackmagazine.com', 'futuremusic.com',
          'thewire.co.uk', 'residentadvisor.net', 'mixmag.net'
        ];
        
        const industryDomains = [
          'theverge.com', 'techcrunch.com', 'wired.com',
          'engadget.com', 'arstechnica.com', 'gizmodo.com',
          'forbes.com', 'businessinsider.com', 'bloomberg.com',
          'reuters.com', 'apnews.com', 'bbc.com'
        ];
        
        if (premiumDomains.some(domain => hostname.includes(domain))) {
          currentScore += 30;
        } else if (industryDomains.some(domain => hostname.includes(domain))) {
          currentScore += 20;
        }
        
        // Content quality checks
        if (result.title.length > 20 && result.title.length < 100) currentScore += 10;
        if (result.snippet && result.snippet.length > 100) currentScore += 15;
        if (result.date) currentScore += 10;
        
        // Update best result if higher quality
        if (currentScore > qualityScore) {
          bestResult = result;
          qualityScore = currentScore;
          bestResult.hostname = hostname;
          bestResult.qualityScore = currentScore;
        }
        
      } catch (e) {
        // Invalid URL, skip
      }
    }
    
    // If no result found, use first organic result
    if (!bestResult.title && organic.length > 0) {
      bestResult = organic[0];
      try {
        const url = new URL(bestResult.link || '');
        bestResult.hostname = url.hostname;
      } catch (e) {
        bestResult.hostname = 'unknown';
      }
      bestResult.qualityScore = 5;
    }
    
    // Extract People Also Ask questions
    let questions = [];
    const questionSources = [
      searchData.related_questions,
      searchData.related_questions_and_answers,
      searchData.inline_questions,
      searchData.organic_results?.[0]?.related_questions
    ];
    
    for (const source of questionSources) {
      if (Array.isArray(source) && source.length > 0) {
        source.slice(0, 5).forEach(item => {
          if (item.question) questions.push(item.question);
          else if (typeof item === 'string') questions.push(item);
        });
        if (questions.length >= 3) break;
      }
    }
    
    // Generate fallback questions if needed
    if (questions.length < 3) {
      const queryWords = query.toLowerCase().split(' ').slice(0, 4);
      const fallbacks = [
        `What are the latest developments in ${queryWords.slice(0, 3).join(' ')}?`,
        `How is ${queryWords.slice(0, 2).join(' ')} impacting modern music production?`,
        `What should producers know about ${queryWords.slice(0, 2).join(' ')} in ${new Date().getFullYear()}?`,
        `How can artists use ${queryWords.slice(0, 2).join(' ')} to improve their workflow?`
      ];
      questions = [...questions, ...fallbacks.slice(0, 5 - questions.length)];
    }
    
    // Calculate base trend score
    let trendScore = 40;
    trendScore += 25; // Recency bonus
    
    const totalResults = searchData.search_information?.total_results || 0;
    if (totalResults > 1000000) trendScore += 10;
    if (totalResults > 5000000) trendScore += 5;
    
    if (qualityScore > 30) trendScore += 15;
    else if (qualityScore > 20) trendScore += 10;
    else if (qualityScore > 10) trendScore += 5;
    
    if (questions.length >= 3) trendScore += 5;
    
    trendScore = Math.min(Math.max(trendScore, 40), 95);
    
    // Categorize the topic
    let category = 'OTHER';
    const queryLower = query.toLowerCase();
    if (queryLower.includes('ai') || queryLower.includes('artificial')) category = '🤖 AI TOOLS';
    else if (queryLower.includes('gear') || queryLower.includes('hardware') || queryLower.includes('equipment')) category = '🎛️ GEAR';
    else if (queryLower.includes('news') || queryLower.includes('industry') || queryLower.includes('trend')) category = '📰 NEWS';
    else if (queryLower.includes('production') || queryLower.includes('studio') || queryLower.includes('recording')) category = '🎚️ PRODUCTION';
    
    return {
      query,
      category,
      score: Math.round(trendScore),
      link: bestResult.link || 'https://example.com/no-link-found',
      title: bestResult.title || `Latest updates: ${query.slice(0, 50)}`,
      snippet: bestResult.snippet || `Stay informed about ${query.slice(0, 30)}...`,
      questions: [...new Set(questions)].slice(0, 5),
      total_results: totalResults,
      quality_score: qualityScore,
      source: bestResult.hostname || 'unknown'
    };
    
  } catch (error) {
    console.error(`❌ Regular SERP error for "${query}":`, error.message);
    throw error;
  }
}

function getFallbackSerpData(query) {
  const fallbackQuestions = [
    `What are the latest trends in ${query.split(' ').slice(0, 3).join(' ')}?`,
    `How is ${query.split(' ').slice(0, 2).join(' ')} impacting music production?`,
    `What should producers know about ${query.split(' ').slice(0, 2).join(' ')}?`
  ];
  
  return {
    query,
    category: 'ERROR',
    score: 40,
    link: 'https://example.com/no-link-found',
    title: `Latest updates on ${query}`,
    snippet: `Stay informed about the latest developments in ${query}`,
    questions: fallbackQuestions,
    status: '❌ ERROR',
    total_results: 0,
    quality_score: 0,
    source: 'error',
    ai_enhanced: false,
    ai_insights: []
  };
}

/**
 * Gemini AI Functions with AI data integration
 */
async function generateAIEnhancedOutlines(context, serpData) {
  try {
    console.log('Generating AI-enhanced outlines with Gemini...');
    
    const aiContext = serpData.ai_insights && serpData.ai_insights.length > 0 
      ? `AI-GENERATED INSIGHTS:\n${serpData.ai_insights.map((insight, i) => `${i+1}. ${insight}`).join('\n')}`
      : 'No AI insights available';
    
    const prompt = `
      CONTEXT: ${context}
      
      SERP DATA:
      - Topic: ${serpData.query}
      - Category: ${serpData.category}
      - Trend Score: ${serpData.score}/100 (${serpData.status})
      - AI-Enhanced: ${serpData.ai_enhanced ? 'Yes' : 'No'}
      - Source: ${serpData.title}
      - People Also Ask: ${serpData.questions ? serpData.questions.slice(0, 5).join(', ') : 'No questions found'}
      
      ${aiContext}
      
      Generate 4 DISTINCT blog outline approaches for SoundSwap (music production platform):
      
      1. **Technical Deep Dive** - Focus on specifications, features, technical analysis
      2. **Creative Applications** - How artists/producers can practically use this
      3. **Industry Impact** - Market trends, business implications, future predictions
      4. **Beginner-Friendly Guide** - Simplified explanation for newcomers
      
      IMPORTANT: Convert at least 3 of the PAA questions into specific H3 header suggestions for the blog post.
      
      For EACH outline, provide:
      - Overall tone/sentiment (positive/neutral/negative based on current industry discussions)
      - Target audience
      - 2-3 key talking points
      - 3 suggested H3 headers based on PAA questions
      - Estimated reading time
      
      Format your response clearly with numbered outlines.
      
      Keep each outline concise but actionable, incorporating AI insights where available.
    `;

    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();
    
    console.log('Gemini AI-enhanced response received');
    return parseOutlinesWithAI(text);
  } catch (error) {
    console.error('Gemini API error:', error);
    return getFallbackOutlines(context);
  }
}

function parseOutlinesWithAI(text) {
  const outlines = [];
  
  // Simple parsing
  const lines = text.split('\n');
  let currentOutline = null;
  
  for (const line of lines) {
    if (line.includes('1.') || line.includes('Technical Deep Dive')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Technical Deep Dive', 
        content: line,
        sentiment: '🔬 TECHNICAL',
        ai_enhanced: text.toLowerCase().includes('ai')
      };
    } else if (line.includes('2.') || line.includes('Creative Applications')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Creative Applications', 
        content: line,
        sentiment: '🎨 CREATIVE',
        ai_enhanced: text.toLowerCase().includes('ai')
      };
    } else if (line.includes('3.') || line.includes('Industry Impact')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Industry Impact', 
        content: line,
        sentiment: '📈 STRATEGIC',
        ai_enhanced: text.toLowerCase().includes('ai')
      };
    } else if (line.includes('4.') || line.includes('Beginner-Friendly Guide')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Beginner-Friendly Guide', 
        content: line,
        sentiment: '👶 FRIENDLY',
        ai_enhanced: text.toLowerCase().includes('ai')
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
      sentiment: outlines.length % 2 === 0 ? '🔬 TECHNICAL' : '🎨 CREATIVE',
      ai_enhanced: false
    });
  }
  
  return outlines.slice(0, 4);
}

function getFallbackOutlines(context) {
  return [
    {
      type: 'Technical Deep Dive',
      content: `Technical specifications and features analysis for ${context.slice(0, 30)}...`,
      sentiment: '🔬 TECHNICAL',
      ai_enhanced: false
    },
    {
      type: 'Creative Applications',
      content: `How artists and producers can creatively use ${context.slice(0, 30)}...`,
      sentiment: '🎨 CREATIVE',
      ai_enhanced: false
    },
    {
      type: 'Industry Impact',
      content: `Market trends and business implications of ${context.slice(0, 30)}...`,
      sentiment: '📈 STRATEGIC',
      ai_enhanced: false
    },
    {
      type: 'Beginner-Friendly Guide',
      content: `Step-by-step guide for beginners to understand ${context.slice(0, 30)}...`,
      sentiment: '👶 FRIENDLY',
      ai_enhanced: false
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
    
    console.log('📤 Sending message to Discord channel...');
    
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
      console.log('✅ Message sent to Discord successfully');
    }
  } catch (error) {
    console.error('❌ Failed to send to Discord channel:', error);
    throw error;
  }
}

// Edge runtime configuration
export const config = {
  runtime: 'edge',
};