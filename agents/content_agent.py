"""
Agent 2 — Content Creator
Triggered when ideas are approved. Generates full content packages:
- Post copy, caption, hashtags
- Reel/TikTok scripts with hooks
- YouTube video production guide (script, shots, b-roll, thumbnails)
"""

import json
import re
from datetime import datetime
import anthropic

PROFILE = {
    "handle": "bdfitindahouse",
    "name": "Bruno Diaz",
    "niche": ["running", "fitness", "lifestyle"],
    "tone": "energetic, motivational, community-driven, authentic, relatable",
    "cta_style": "drive comments and saves, use strong calls to action",
    "brand_voice": "You're the friend who runs at 5 AM and makes everyone want to come along",
}


def generate_content(idea: dict, api_key: str) -> dict:
    """
    Generate full content package for an approved idea.
    Returns platform-appropriate content package.
    """
    client = anthropic.Anthropic(api_key=api_key)
    platform = idea.get("platform", "instagram")
    fmt = idea.get("format", "post")

    if platform == "instagram":
        return _generate_instagram_content(client, idea)
    elif platform == "youtube":
        return _generate_youtube_content(client, idea)
    elif platform == "tiktok":
        return _generate_tiktok_content(client, idea)
    else:
        return _generate_instagram_content(client, idea)


def _generate_instagram_content(client: anthropic.Anthropic, idea: dict) -> dict:
    fmt = idea.get("format", "post")

    if fmt == "reel":
        prompt = f"""
You are writing content for @{PROFILE['handle']} (Bruno Diaz) — a running & fitness creator.
Brand voice: {PROFILE['brand_voice']}
Tone: {PROFILE['tone']}

Approved idea:
Title: {idea['title']}
Hook: {idea.get('hook', '')}
Description: {idea.get('description', '')}
Trend: {idea.get('trend_connection', '')}

Generate a COMPLETE Instagram Reel content package. Return ONLY valid JSON:
{{
  "content_package": {{
    "platform": "instagram",
    "format": "reel",
    "title": "{idea['title']}",
    "hook_text": "Text shown in first 2-3 seconds (on-screen text)",
    "hook_voiceover": "What to say in the first 3 seconds to stop the scroll",
    "script": [
      {{"second": "0-3", "visual": "...", "voiceover": "...", "on_screen_text": "..."}},
      {{"second": "3-8", "visual": "...", "voiceover": "...", "on_screen_text": "..."}},
      {{"second": "8-15", "visual": "...", "voiceover": "...", "on_screen_text": "..."}},
      {{"second": "15-25", "visual": "...", "voiceover": "...", "on_screen_text": "..."}},
      {{"second": "25-30", "visual": "...", "voiceover": "...", "on_screen_text": "..."}}
    ],
    "caption": "Full Instagram caption with emojis, max 150 words",
    "cta": "Call to action in the caption",
    "hashtags": ["#tag1", "#tag2"],
    "audio_suggestion": "Trending song or sound type to use",
    "filming_tips": ["tip1", "tip2", "tip3"],
    "trending_technique": "How to make this specifically trendy right now"
  }}
}}
"""
    elif fmt == "carousel":
        prompt = f"""
You are writing content for @{PROFILE['handle']} (Bruno Diaz) — a running & fitness creator.
Tone: {PROFILE['tone']}

Approved idea:
Title: {idea['title']}
Description: {idea.get('description', '')}

Generate a COMPLETE Instagram Carousel content package. Return ONLY valid JSON:
{{
  "content_package": {{
    "platform": "instagram",
    "format": "carousel",
    "title": "{idea['title']}",
    "slides": [
      {{"slide": 1, "headline": "Cover slide headline", "subtext": "...", "visual_direction": "..."}},
      {{"slide": 2, "headline": "...", "subtext": "...", "visual_direction": "..."}},
      {{"slide": 3, "headline": "...", "subtext": "...", "visual_direction": "..."}},
      {{"slide": 4, "headline": "...", "subtext": "...", "visual_direction": "..."}},
      {{"slide": 5, "headline": "...", "subtext": "...", "visual_direction": "..."}},
      {{"slide": 6, "headline": "Last slide CTA", "subtext": "Follow for more", "visual_direction": "..."}}
    ],
    "caption": "Full caption with emojis",
    "cta": "Call to action",
    "hashtags": ["#tag1", "#tag2"],
    "design_tips": "Color palette, font style, visual cohesion tips"
  }}
}}
"""
    else:
        prompt = f"""
Generate an Instagram post for @{PROFILE['handle']} (Bruno Diaz).
Tone: {PROFILE['tone']}
Idea: {idea['title']} — {idea.get('description', '')}

Return ONLY valid JSON:
{{
  "content_package": {{
    "platform": "instagram",
    "format": "post",
    "caption": "Full caption with emojis, storytelling, max 200 words",
    "cta": "...",
    "hashtags": ["#tag1", "#tag2"],
    "photo_direction": "What photo/image to use and how to shoot it"
  }}
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        data = json.loads(_extract_json(response.content[0].text))
        return data.get("content_package", {})
    except Exception:
        return {"error": "Failed to parse content", "raw": response.content[0].text[:500]}


def _generate_youtube_content(client: anthropic.Anthropic, idea: dict) -> dict:
    fmt = idea.get("format", "long-form")

    prompt = f"""
You are a YouTube content strategist for @{PROFILE['handle']} (Bruno Diaz) — running & fitness channel.
Tone: {PROFILE['tone']}

Approved idea:
Title: {idea['title']}
Format: {fmt}
Description: {idea.get('description', '')}
Trend: {idea.get('trend_connection', '')}

Generate a COMPLETE YouTube video production package. Return ONLY valid JSON:
{{
  "content_package": {{
    "platform": "youtube",
    "format": "{fmt}",
    "video_title": "SEO-optimized YouTube title (max 60 chars)",
    "thumbnail_concept": {{
      "text_overlay": "Bold text on thumbnail",
      "visual": "What image/scene to use",
      "color_scheme": "Colors that pop in feed",
      "emotion": "What feeling it should convey"
    }},
    "hook": "First 30 seconds script — must answer 'why watch this'",
    "outline": [
      {{"timestamp": "0:00", "section": "Hook / Open loop", "content": "...", "b_roll": "..."}},
      {{"timestamp": "0:30", "section": "Intro / Who you are", "content": "...", "b_roll": "..."}},
      {{"timestamp": "2:00", "section": "Main content part 1", "content": "...", "b_roll": "..."}},
      {{"timestamp": "5:00", "section": "Main content part 2", "content": "...", "b_roll": "..."}},
      {{"timestamp": "8:00", "section": "Main content part 3", "content": "...", "b_roll": "..."}},
      {{"timestamp": "11:00", "section": "Conclusion + CTA", "content": "...", "b_roll": "..."}}
    ],
    "full_script_intro": "Full word-for-word script for the first 2 minutes",
    "shots_list": [
      {{"shot": 1, "type": "...", "description": "...", "duration": "..."}},
      {{"shot": 2, "type": "...", "description": "...", "duration": "..."}},
      {{"shot": 3, "type": "...", "description": "...", "duration": "..."}}
    ],
    "equipment_needed": ["Camera", "Mic", "..."],
    "description": "Full YouTube description with timestamps and links placeholder",
    "tags": ["tag1", "tag2"],
    "seo_tips": "How to optimize this video for search",
    "trending_technique": "What makes this specifically viral right now"
  }}
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        data = json.loads(_extract_json(response.content[0].text))
        return data.get("content_package", {})
    except Exception:
        return {"error": "Failed to parse content", "raw": response.content[0].text[:500]}


def _generate_tiktok_content(client: anthropic.Anthropic, idea: dict) -> dict:
    fmt = idea.get("format", "video")

    prompt = f"""
You are a TikTok content strategist for @{PROFILE['handle']} (Bruno Diaz) — running & fitness creator.
Tone: {PROFILE['tone']}

Approved idea:
Title: {idea['title']}
Format: {fmt}
Hook: {idea.get('hook', '')}
Description: {idea.get('description', '')}
Trend: {idea.get('trend_connection', '')}

Generate a COMPLETE TikTok content package. Return ONLY valid JSON:
{{
  "content_package": {{
    "platform": "tiktok",
    "format": "{fmt}",
    "title": "{idea['title']}",
    "hook_text": "On-screen text for first 1 second (pattern interrupt)",
    "hook_voiceover": "Exact words to say in first 2 seconds",
    "script": [
      {{"second": "0-2", "visual": "...", "voiceover": "...", "on_screen_text": "...", "action": "..."}},
      {{"second": "2-5", "visual": "...", "voiceover": "...", "on_screen_text": "...", "action": "..."}},
      {{"second": "5-15", "visual": "...", "voiceover": "...", "on_screen_text": "...", "action": "..."}},
      {{"second": "15-25", "visual": "...", "voiceover": "...", "on_screen_text": "...", "action": "..."}},
      {{"second": "25-35", "visual": "...", "voiceover": "...", "on_screen_text": "...", "action": "..."}},
      {{"second": "35-45", "visual": "CTA scene", "voiceover": "Follow for daily running content!", "on_screen_text": "FOLLOW", "action": "Point to follow button"}}
    ],
    "caption": "TikTok caption (short, punchy, max 100 chars) + emojis",
    "hashtags": ["#fyp", "#running", "#fitness"],
    "audio_suggestion": "Specific trending sound or song type",
    "duet_stitch_angle": "How someone could duet or stitch this for engagement",
    "comment_bait": "Question to put at end to drive comments",
    "filming_tips": ["Tip 1", "Tip 2"],
    "trending_technique": "Exactly how this taps into a current TikTok trend",
    "viral_potential_reason": "Why this specific concept can go viral"
  }}
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3500,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        data = json.loads(_extract_json(response.content[0].text))
        return data.get("content_package", {})
    except Exception:
        return {"error": "Failed to parse content", "raw": response.content[0].text[:500]}


def _extract_json(text: str) -> str:
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else text
