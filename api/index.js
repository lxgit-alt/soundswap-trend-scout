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

// Dynamic query generation based on day of week
function generateDailyQueries() {
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0 = Sunday, 6 = Saturday
  const dayOfMonth = now.getDate();
  const weekOfYear = Math.floor(dayOfMonth / 7) + 1;
  const month = now.getMonth(); // 0-11
  const year = now.getFullYear();
  
  // Monthly themes to prevent repetition
  const monthlyThemes = [
    'AI Music Production Tools',
    'Music Gear Releases',
    'Music Industry News',
    'Audio Technology',
    'Music Business Trends',
    'Creative Production Techniques'
  ];
  
  const theme = monthlyThemes[month % monthlyThemes.length];
  
  // Query pools for each category
  const aiToolsQueries = [
    `latest AI audio tools ${month + 1}/${year}`,
    `AI music production software ${year}`,
    `best AI plugins for producers ${month + 1}/${year}`,
    `AI mastering tools reviews ${year}`,
    `artificial intelligence in music production`,
    `AI vocal processing ${month + 1} ${year}`,
    `machine learning music composition`,
    `AI beat making tools ${year}`
  ];
  
  const gearQueries = [
    `new music production gear ${month + 1}/${year}`,
    `audio interface releases ${year}`,
    `studio monitor reviews ${month + 1} ${year}`,
    `MIDI controller latest models ${year}`,
    `synthesizer new releases ${month + 1}/${year}`,
    `microphones for home studio ${year}`,
    `DAW updates ${month + 1} ${year}`,
    `music production hardware ${year}`
  ];
  
  const newsQueries = [
    `music industry news ${month + 1}/${year}`,
    `streaming services updates ${year}`,
    `music copyright laws ${month + 1} ${year}`,
    `artist revenue trends ${year}`,
    `music marketing strategies ${month + 1}/${year}`,
    `independent musician news ${year}`,
    `record label developments ${month + 1} ${year}`,
    `music distribution platforms ${year}`
  ];
  
  const trendingQueries = [
    `viral music production trends ${month + 1}/${year}`,
    `what producers are talking about ${year}`,
    `emerging music technologies ${month + 1} ${year}`,
    `music production on social media ${year}`,
    `creative workflows ${month + 1}/${year}`,
    `music collaboration tools ${year}`,
    `home studio setup trends ${month + 1} ${year}`,
    `music education online ${year}`
  ];
  
  // Rotate queries based on day
  const dayIndex = dayOfMonth % 8;
  const weekIndex = weekOfYear % 8;
  const dayOfWeekIndex = dayOfWeek;
  
  // Generate 4 unique queries with rotating selection
  const queries = [
    aiToolsQueries[(dayIndex + dayOfWeekIndex) % aiToolsQueries.length],
    gearQueries[(dayIndex + weekIndex) % gearQueries.length],
    newsQueries[(dayOfMonth + dayOfWeekIndex) % newsQueries.length],
    trendingQueries[(dayIndex + month) % trendingQueries.length]
  ];
  
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
      version: '4.0 - Enhanced Query Rotation',
      features: [
        'Dynamic daily topic rotation',
        'AI Tools + Gear + News focus',
        'PAA questions → H3 headers',
        'Monthly themes to prevent repetition'
      ],
      commands: [
        '/blog - Generate daily semantic SEO blog',
        'Right-click message → Generate 4 Outlines',
        '/outlines [topic] - Legacy outline generator'
      ],
      daily_limit: '1 blog per day for maximum SEO impact'
    }), { status: 200, headers });
  }
  
  if (pathname === '/' && request.method === 'GET') {
    const { queries, theme } = generateDailyQueries();
    return new Response(JSON.stringify({
      status: 'online',
      service: 'SoundSwap AI Blog Generator',
      version: '4.0 - Enhanced Query Rotation',
      daily_theme: theme,
      today_queries: queries.slice(0, 2),
      features: [
        'Dynamic daily topic selection (rotating queries)',
        'Focus: AI Tools, Music Gear, Industry News',
        'PAA questions → H3 headers',
        'Real-time sentiment analysis'
      ],
      indexed_stats: 'Previous blogs indexed in <5 hours',
      commands: [
        '/blog - Generate daily semantic SEO blog',
        '/outlines [topic] - Generate 4 blog outlines'
      ]
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
                     'latest AI music production trends 2026';
        
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
    await editOriginalResponse(token, "🎸 **Loading today's dynamic topics...**");
    
    console.log('Getting SERP data for all topics...');
    const { queries, theme, dateInfo } = generateDailyQueries();
    const dailyTopics = [];
    
    // Get SERP data for all queries
    for (const query of queries) {
      try {
        const serpData = await getEnhancedSerpData(query, {
          isNews: query.toLowerCase().includes('news')
        });
        dailyTopics.push(serpData);
        console.log(`Got data for: ${query.slice(0, 40)}...`);
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
          status: '❌ ERROR'
        });
      }
    }
    
    // Store session
    userSessions.set(token, {
      step: 'topic_selection',
      topics: dailyTopics,
      createdAt: Date.now(),
      theme,
      dateInfo
    });
    
    // Build topic selection message
    let message = `🎸 **SOUNDSWAP DAILY BLOG TOPICS**\n`;
    message += `📅 ${dateInfo.dayOfWeek}, ${dateInfo.month}/${dateInfo.dayOfMonth}/${dateInfo.year}\n`;
    message += `🎯 Theme: ${theme}\n\n`;
    message += "**Choose ONE topic for today's semantic SEO blog:**\n\n";
    
    // Sort by score for better presentation
    dailyTopics.sort((a, b) => b.score - a.score);
    
    dailyTopics.forEach((topic, index) => {
      const emoji = ["🔥", "📈", "🎯", "⚡"][index] || "📝";
      const categoryEmoji = topic.category || '📝';
      const paaPreview = topic.questions?.length > 0 ? 
        `${topic.questions[0].slice(0, 50)}...` : "What music creators need to know";
      
      message += `${emoji} **${categoryEmoji} ${topic.query.slice(0, 50)}...**\n`;
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
    const serpData = await getEnhancedSerpData(topic.slice(0, 100), {
      isNews: topic.toLowerCase().includes('news')
    });
    const outlines = await generateFourOutlines(topic, serpData);
    
    let message = `🎸 **4 BLOG OUTLINES FOR:** ${topic.slice(0, 50)}...\n\n`;
    message += `📊 Trend: ${serpData.score}/100 ${serpData.status}\n`;
    message += `🏷️ Category: ${serpData.category}\n`;
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
    console.log('Executing enhanced daily scout...');
    
    // Generate dynamic queries
    const { queries, theme, dateInfo } = generateDailyQueries();
    const dailyTopics = [];
    
    // Get SERP data for each query
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
        console.log(`Got data for query ${i + 1}: ${query.slice(0, 40)}...`);
        await new Promise(resolve => setTimeout(resolve, 1000)); // Rate limiting
      } catch (error) {
        console.error(`Error processing query "${query}":`, error);
      }
    }
    
    // Build report
    const dateStr = new Date().toISOString().split('T')[0];
    let report = `🎸 **SOUNDSWAP DAILY BLOG SCOUT**\n`;
    report += `📅 ${dateInfo.dayOfWeek}, ${dateInfo.month}/${dateInfo.dayOfMonth}/${dateInfo.year}\n`;
    report += `🎯 Monthly Theme: ${theme}\n\n`;
    report += "**Choose ONE topic for today's semantic SEO blog:**\n\n";
    
    // Sort by score for better presentation
    dailyTopics.sort((a, b) => b.score - a.score);
    
    for (let i = 0; i < dailyTopics.length; i++) {
      const topic = dailyTopics[i];
      const emoji = ["🔥", "📈", "🎯", "⚡"][i] || "📝";
      const categoryEmoji = topic.category;
      const paaPreview = topic.questions?.length > 0 ? 
        `${topic.questions[0].slice(0, 50)}...` : "What music creators need to know";
      
      report += `${emoji} **${categoryEmoji} ${topic.query.slice(0, 50)}...**\n`;
      report += `   📊 Trend Score: ${topic.score}/100 ${topic.status}\n`;
      report += `   🏷️ Source: ${topic.source || 'Various'}\n`;
      report += `   🔗 Reference: ${topic.link.slice(0, 60)}...\n`;
      report += `   ❓ Top PAA: ${paaPreview}\n\n`;
    }
    
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    report += "**💡 BLOG GENERATION INSTRUCTIONS:**\n";
    report += "1. Type `/blog` in this channel\n";
    report += "2. Choose topic number (1-4)\n";
    report += "3. Select outline style\n";
    report += "4. Get full semantic SEO blog with PAA → H3 headers!\n\n";
    report += "**🎯 TODAY'S FOCUS AREAS:**\n";
    report += "- 🤖 AI Tools for Music Production\n";
    report += "- 🎛️ Latest Music Gear & Hardware\n";
    report += "- 📰 Music Industry News & Trends\n";
    report += "- 🎚️ Creative Production Techniques\n\n";
    report += "⏱️ *Only 1 high-quality blog per day for maximum SEO impact*\n";
    report += "✅ *Previous blogs indexed in <5 hours*";
    
    // Send to Discord
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
        category: t.category
      })),
      timestamp: new Date().toISOString()
    };
    
  } catch (error) {
    console.error('Enhanced scout execution error:', error);
    throw error;
  }
}

/**
 * Enhanced SERP API Function
 */
async function getEnhancedSerpData(query, context = {}) {
  try {
    console.log(`🔍 Fetching enhanced SERP data for: ${query}`);
    
    // Add freshness modifier based on context
    const tbsModifier = context.isNews ? 'qdr:d' : 'qdr:w'; // day for news, week for others
    
    const searchUrl = `https://serpapi.com/search?q=${encodeURIComponent(query)}&tbs=${tbsModifier}&num=10&api_key=${SERPAPI_KEY}`;
    const searchResponse = await fetch(searchUrl);
    const searchData = await searchResponse.json();
    
    console.log(`✅ Enhanced SERP data received for: ${query.slice(0, 40)}...`);
    
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
    let secondaryResult = {};
    
    for (const result of organic) {
      if (!result.link || !result.title) continue;
      
      try {
        const url = new URL(result.link);
        const hostname = url.hostname.toLowerCase();
        
        // Skip excluded domains
        if (excludedDomains.some(domain => hostname.includes(domain))) {
          continue;
        }
        
        // Quality scoring system
        let qualityScore = 0;
        
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
          qualityScore += 30;
        } else if (industryDomains.some(domain => hostname.includes(domain))) {
          qualityScore += 20;
        }
        
        // Content quality checks
        if (result.title.length > 20 && result.title.length < 100) qualityScore += 10;
        if (result.snippet && result.snippet.length > 100) qualityScore += 15;
        if (result.date) qualityScore += 10; // Has publication date
        
        // Update best result if higher quality
        if (qualityScore > (bestResult.qualityScore || 0)) {
          if (bestResult.title) {
            secondaryResult = { ...bestResult };
          }
          bestResult = {
            ...result,
            qualityScore,
            hostname
          };
        } else if (qualityScore > (secondaryResult.qualityScore || 0)) {
          secondaryResult = {
            ...result,
            qualityScore,
            hostname
          };
        }
        
      } catch (e) {
        // Invalid URL, skip
      }
    }
    
    // Use best result, fallback to first organic
    const firstResult = bestResult.title ? bestResult : (organic[0] || {});
    
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
    
    // Generate context-relevant fallback questions
    if (questions.length < 3) {
      const queryWords = query.toLowerCase().split(' ').slice(0, 4);
      const fallbacks = [
        `What are the latest developments in ${queryWords.slice(0, 3).join(' ')}?`,
        `How is ${queryWords.slice(0, 2).join(' ')} impacting modern music production?`,
        `What should producers know about ${queryWords.slice(0, 2).join(' ')} in ${new Date().getFullYear()}?`,
        `How can artists use ${queryWords.slice(0, 2).join(' ')} to improve their workflow?`,
        `What are the benefits of ${queryWords.slice(0, 2).join(' ')} for independent musicians?`
      ];
      questions = [...questions, ...fallbacks.slice(0, 5 - questions.length)];
    }
    
    // Remove duplicates
    questions = [...new Set(questions)].slice(0, 5);
    
    // Calculate trend score with enhanced metrics
    let trendScore = 40; // Base score
    
    // Recency bonus
    trendScore += 25;
    
    // Volume bonus
    const totalResults = searchData.search_information?.total_results || 0;
    if (totalResults > 1000000) trendScore += 10;
    if (totalResults > 5000000) trendScore += 5;
    if (totalResults > 10000000) trendScore += 5;
    
    // Quality bonus
    if (firstResult.qualityScore > 30) trendScore += 15;
    else if (firstResult.qualityScore > 20) trendScore += 10;
    else if (firstResult.qualityScore > 10) trendScore += 5;
    
    // Questions bonus (indicates search interest)
    if (questions.length >= 3) trendScore += 5;
    
    // Clamp score
    trendScore = Math.min(Math.max(trendScore, 40), 95);
    
    // Determine status
    let status = '📊 STEADY';
    if (trendScore > 75) status = '🔥 VIRAL';
    else if (trendScore > 60) status = '📈 TRENDING';
    
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
      link: firstResult.link || 'https://example.com/no-link-found',
      title: firstResult.title || `Latest updates: ${query.slice(0, 50)}`,
      snippet: firstResult.snippet || `Stay informed about ${query.slice(0, 30)}...`,
      questions,
      status,
      total_results: totalResults,
      quality_score: firstResult.qualityScore || 0,
      source: firstResult.hostname || 'unknown'
    };
    
  } catch (error) {
    console.error(`❌ Enhanced SERP API error for "${query}":`, error.message);
    
    return {
      query,
      category: 'ERROR',
      score: 40,
      link: 'https://example.com/no-link-found',
      title: `Error fetching data for: ${query.slice(0, 40)}`,
      snippet: `Unable to retrieve information. Please try again or check the logs.`,
      questions: [
        `What is the latest in ${query.split(' ').slice(0, 2).join(' ')}?`,
        `How does ${query.split(' ').slice(0, 2).join(' ')} affect music production?`,
        `What are the trends in ${query.split(' ').slice(0, 2).join(' ')}?`
      ],
      status: '❌ ERROR',
      total_results: 0,
      quality_score: 0,
      source: 'error'
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
      - Category: ${serpData.category}
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
      
      IMPORTANT: Convert PAA questions into H3 header suggestions.
      
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
  
  // Simple parsing
  const lines = text.split('\n');
  let currentOutline = null;
  
  for (const line of lines) {
    if (line.includes('1.') || line.includes('Technical Deep Dive')) {
      if (currentOutline) outlines.push(currentOutline);
      currentOutline = { 
        type: 'Technical Deep Dive', 
        content: line,
        sentiment: '🔬 TECHNICAL'
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
      sentiment: outlines.length % 2 === 0 ? '🔬 TECHNICAL' : '🎨 CREATIVE'
    });
  }
  
  return outlines.slice(0, 4);
}

function getFallbackOutlines(context) {
  return [
    {
      type: 'Technical Deep Dive',
      content: `Technical specifications and features analysis for ${context.slice(0, 30)}...`,
      sentiment: '🔬 TECHNICAL'
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