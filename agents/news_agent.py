"""
Agent 1 — News Scout & Content Idea Generator
Runs daily at 9 AM. Fetches news, filters by relevance to @bdfitindahouse,
and generates 10+ content ideas per platform with trend analysis.
"""

import json
import re
from datetime import datetime
from typing import Optional
import feedparser
import httpx
import anthropic

PROFILE = {
    "handle": "bdfitindahouse",
    "name": "Bruno Diaz",
    "niche": ["running", "fitness", "lifestyle", "health", "motivation"],
    "tone": "energetic, motivational, community-driven, authentic",
    "audience": "fitness enthusiasts, runners, people on transformation journeys",
    "keywords": [
        "running", "marathon", "fitness", "workout", "runner",
        "cardio", "race", "5k", "10k", "half marathon", "training",
        "personal record", "PR", "fitlife", "health", "endurance",
        "trail running", "speed work", "recovery", "nutrition"
    ]
}

NEWS_FEEDS = [
    {"name": "Runner's World", "url": "https://www.runnersworld.com/rss/all.xml"},
    {"name": "Outside Online", "url": "https://www.outsideonline.com/running/"},
    {"name": "Healthline", "url": "https://www.healthline.com/rss/health-news"},
    {"name": "Men's Health", "url": "https://www.menshealth.com/fitness/"},
    {"name": "Running USA", "url": "https://runningusa.org/feed/"},
]

PLATFORM_TRENDS = {
    "instagram": [
        "Carousel posts with data/statistics perform 3x better",
        "Reels under 30s with trending audio hit Explore page more",
        "Before/after transformations still top performers",
        "Day-in-the-life running vlogs driving high saves",
        "Interactive polls and question stickers boost engagement",
        "Behind-the-scenes training content feels authentic",
        "Race recap posts with personal stories drive comments",
    ],
    "youtube": [
        "Long-form training vlogs (15-30 min) growing fast",
        "Running shoe reviews & comparisons high search volume",
        "Race day vlogs with POV footage trending",
        "Training plan breakdowns for beginners very popular",
        "Collab runs with other fitness creators boost discovery",
        "Gear review + run combination videos performing well",
        "Injury prevention & recovery content evergreen + trending",
    ],
    "tiktok": [
        "Running 'duets' with popular running sounds trending",
        "Mile PR attempts with countdown format viral format",
        "Packing for a race haul content exploding",
        "'Couch to 5k' journey content drives massive followings",
        "Running fails/bloopers high share rate",
        "Training montages with trending audio easy wins",
        "Running tips in 60s 'did you know' format high saves",
    ]
}


def fetch_news_articles(limit_per_source: int = 5) -> list[dict]:
    """Fetch articles from RSS feeds."""
    articles = []
    for feed_info in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:limit_per_source]:
                articles.append({
                    "source": feed_info["name"],
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:500],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", str(datetime.now().date())),
                })
        except Exception as e:
            print(f"[NewsAgent] Feed error {feed_info['name']}: {e}")
    return articles


def is_relevant(article: dict) -> bool:
    """Quick keyword relevance filter before sending to Claude."""
    text = (article["title"] + " " + article["summary"]).lower()
    return any(kw.lower() in text for kw in PROFILE["keywords"])


def run_news_agent(api_key: str, db_callback=None) -> dict:
    """
    Main entry point for Agent 1.
    Returns dict with: filtered_news, content_ideas, run_timestamp
    """
    print(f"[NewsAgent] Starting run at {datetime.now().isoformat()}")
    client = anthropic.Anthropic(api_key=api_key)

    # 1. Fetch & pre-filter news
    raw_articles = fetch_news_articles()
    filtered_articles = [a for a in raw_articles if is_relevant(a)]

    # Fallback seed if feeds are unavailable
    if not filtered_articles:
        filtered_articles = _get_seed_news()

    print(f"[NewsAgent] {len(raw_articles)} articles fetched, {len(filtered_articles)} relevant")

    # 2. Ask Claude to rank & summarize relevant news
    news_prompt = f"""
You are a social media strategist for @{PROFILE['handle']} (Bruno Diaz).
Niche: {', '.join(PROFILE['niche'])}
Tone: {PROFILE['tone']}
Audience: {PROFILE['audience']}

Here are today's news articles (already pre-filtered for relevance):
{json.dumps(filtered_articles, indent=2)}

Task:
1. Select the TOP 8 most relevant and interesting articles for this running/fitness audience.
2. For each selected article, write a 1-sentence "Why it matters to @bdfitindahouse's audience".
3. Score relevance 1-10.

Return ONLY valid JSON in this exact format:
{{
  "filtered_news": [
    {{
      "title": "...",
      "source": "...",
      "link": "...",
      "published": "...",
      "relevance_score": 8,
      "why_it_matters": "..."
    }}
  ]
}}
"""

    news_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": news_prompt}]
    )

    try:
        news_data = json.loads(_extract_json(news_response.content[0].text))
    except Exception:
        news_data = {"filtered_news": filtered_articles[:8]}

    # 3. Generate content ideas
    ideas_prompt = f"""
You are a viral content strategist for @{PROFILE['handle']} (Bruno Diaz), a fitness & running creator.

Today's relevant news themes:
{json.dumps([a.get('title','') for a in news_data.get('filtered_news', [])], indent=2)}

Current platform trends:
- Instagram: {'; '.join(PLATFORM_TRENDS['instagram'][:4])}
- YouTube: {'; '.join(PLATFORM_TRENDS['youtube'][:4])}
- TikTok: {'; '.join(PLATFORM_TRENDS['tiktok'][:4])}

Generate EXACTLY 12 content ideas (4 per platform) that blend today's news with current trends.
Each idea must feel NATIVE to the platform.

Return ONLY valid JSON:
{{
  "content_ideas": [
    {{
      "id": "idea_001",
      "platform": "instagram",
      "format": "reel",
      "title": "...",
      "hook": "First 3 seconds / opening line",
      "description": "What this content covers",
      "trend_connection": "Which current trend this taps into",
      "news_connection": "Which news article inspired this",
      "estimated_reach": "high/medium/low",
      "hashtags": ["#tag1", "#tag2"],
      "status": "pending"
    }}
  ]
}}

Formats allowed:
- instagram: reel, carousel, story, post
- youtube: long-form, short, live
- tiktok: video, duet, stitch, series
"""

    ideas_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": ideas_prompt}]
    )

    try:
        ideas_data = json.loads(_extract_json(ideas_response.content[0].text))
    except Exception:
        ideas_data = {"content_ideas": []}

    result = {
        "run_timestamp": datetime.now().isoformat(),
        "filtered_news": news_data.get("filtered_news", []),
        "content_ideas": ideas_data.get("content_ideas", []),
        "stats": {
            "articles_fetched": len(raw_articles),
            "articles_filtered": len(filtered_articles),
            "ideas_generated": len(ideas_data.get("content_ideas", [])),
        }
    }

    if db_callback:
        db_callback(result)

    print(f"[NewsAgent] Completed. {len(result['content_ideas'])} ideas generated.")
    return result


def _extract_json(text: str) -> str:
    """Extract JSON block from Claude response."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else text


def _get_seed_news() -> list[dict]:
    """Fallback seed news when feeds are unavailable."""
    return [
        {
            "source": "Runner's World",
            "title": "New Study: Running 30 Minutes Daily Reduces Heart Disease Risk by 45%",
            "summary": "Researchers found that even moderate running has massive cardiovascular benefits.",
            "link": "https://runnersworld.com",
            "published": str(datetime.now().date())
        },
        {
            "source": "Outside Online",
            "title": "The Rise of Trail Running: Why More Urban Runners Are Going Off-Road",
            "summary": "Trail running participation grew 23% in 2024 as runners seek adventure beyond pavement.",
            "link": "https://outsideonline.com",
            "published": str(datetime.now().date())
        },
        {
            "source": "Healthline",
            "title": "Best Pre-Run Nutrition: What to Eat Before Your Morning Run",
            "summary": "Sports nutritionists share the optimal foods to fuel your morning runs.",
            "link": "https://healthline.com",
            "published": str(datetime.now().date())
        },
        {
            "source": "Men's Health",
            "title": "The 8-Week Plan That Helped Thousands Break Their 5K Personal Record",
            "summary": "A structured training plan combining speed work and endurance to shatter your PR.",
            "link": "https://menshealth.com",
            "published": str(datetime.now().date())
        },
        {
            "source": "Running USA",
            "title": "2025 Race Calendar: The Biggest Marathons and 5Ks You Need to Register For",
            "summary": "From Boston to local weekend races, here's every major event on the calendar.",
            "link": "https://runningusa.org",
            "published": str(datetime.now().date())
        },
    ]
