import asyncio
import time
import feedparser
import httpx
import os
import json
from datetime import datetime
from google import genai

# Retrieve key securely from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY secret is missing in GitHub Repository Secrets.")

client = genai.Client(api_key=GEMINI_API_KEY)

# High-reliability core RSS feeds across 6 categories
SOURCES = [
    # 1. General & National News
    {"category": "general", "name": "ENA", "url": "https://www.ena.et/web/eng/rss"},
    {"category": "general", "name": "Addis Standard", "url": "https://addisstandard.com/feed/"},
    {"category": "general", "name": "BBC News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},

    # 2. Sports
    {"category": "sports", "name": "Soccer Ethiopia", "url": "https://soccerethiopia.net/feed/"},
    {"category": "sports", "name": "BBC Sport Africa", "url": "https://feeds.bbci.co.uk/sport/africa/rss.xml"},

    # 3. Technology & Innovation
    {"category": "tech", "name": "Shega.co", "url": "https://shega.co/feed/"},
    {"category": "tech", "name": "TechCrunch", "url": "https://techcrunch.com/feed/"},

    # 4. Business & Economy
    {"category": "business", "name": "Addis Fortune", "url": "https://addisfortune.news/feed/"},
    {"category": "business", "name": "Business Daily Africa", "url": "https://www.businessdailyafrica.com/service/rss/bda/2046/feed.rss"},

    # 5. Lifestyle & Entertainment
    {"category": "lifestyle", "name": "BellaNaija", "url": "https://www.bellanaija.com/feed/"},
    {"category": "lifestyle", "name": "Variety", "url": "https://variety.com/feed/"},

    # 6. Odd & Offbeat News
    {"category": "oddities", "name": "Oddity Central", "url": "https://www.odditycentral.com/feed"},
    {"category": "oddities", "name": "UPI Odd News", "url": "https://www.upi.com/rss/Odd_News/"}
]

async def fetch_single_feed(http_client, source):
    try:
        response = await http_client.get(source["url"], timeout=6.0)
        feed = feedparser.parse(response.content)
        items = []
        for entry in feed.entries[:2]:
            items.append({
                "category": source["category"],
                "source": source["name"],
                "headline": getattr(entry, 'title', ''),
                "context": getattr(entry, 'summary', '')
            })
        return items
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch {source['name']}: {e}")
        return []

async def fetch_all_feeds():
    async with httpx.AsyncClient(follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as http_client:
        tasks = [fetch_single_feed(http_client, src) for src in SOURCES]
        results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]

def generate_tri_lingual_articles(raw_items):
    combined_raw_text = json.dumps(raw_items, ensure_ascii=False, indent=2)
    
    prompt = f"""
You are the Chief Editor for a multi-lingual news agency.
Below is raw news feed data collected from various outlets:

{combined_raw_text}

MANDATORY TASK:
1. Select the top story for EACH available category (general, sports, tech, business, lifestyle, oddities).
2. For EACH selected story, write a long-form detailed article in THREE languages:
   - Amharic (AM)
   - Afaan Oromoo (OM)
   - English (EN)
3. Return ONLY a valid JSON array of objects without surrounding markdown formatting or backticks.

Exact Output Format:
[
  {{
    "category": "general|sports|tech|business|lifestyle|oddities",
    "source_name": "Source Name",
    "amharic": {{
      "title": "ርዕስ በአማርኛ...",
      "content": "<p>ዝርዝር መረጃ 1...</p><p>ዝርዝር መረጃ 2...</p>"
    }},
    "afaan_oromoo": {{
      "title": "Mata Duree Afaan Oromootiin...",
      "content": "<p>Keeyyata 1...</p><p>Keeyyata 2...</p>"
    }},
    "english": {{
      "title": "Detailed Title in English...",
      "content": "<p>Detailed paragraph 1...</p><p>Detailed paragraph 2...</p>"
    }}
  }}
]
"""

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    for model_name in models_to_try:
        try:
            print(f"Requesting content from model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            raw_text = response.text.strip()
            
            if "```" in raw_text:
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            
            clean_json = raw_text.strip()
            articles = json.loads(clean_json)
            print(f"✅ SUCCESS: Created {len(articles)} multi-lingual stories!")
            return articles
        except Exception as e:
            print(f"⚠️ Model {model_name} failed: {e}")
            time.sleep(1)

    print("❌ All model generation attempts failed.")
    return []

def save_markdown_posts(articles):
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H%M%S")

    for idx, article in enumerate(articles):
        cat = article.get("category", "general")
        source = article.get("source_name", "News")

        # 1. Save Amharic Post
        am_dir = "_posts/am"
        os.makedirs(am_dir, exist_ok=True)
        am_file = f"{am_dir}/{today}-{cat}-{timestamp}-{idx}.md"
        am_meta = f"---\nlayout: post\ntitle: \"{article['amharic']['title']}\"\ncategories: {cat}\nlang: am\nsource: \"{source}\"\n---\n\n{article['amharic']['content']}\n\n<p><strong>📌 ምንጭ:</strong> {source}</p>"
        with open(am_file, "w", encoding="utf-8") as f:
            f.write(am_meta)

        # 2. Save Afaan Oromoo Post
        om_dir = "_posts/om"
        os.makedirs(om_dir, exist_ok=True)
        om_file = f"{om_dir}/{today}-{cat}-{timestamp}-{idx}.md"
        om_meta = f"---\nlayout: post\ntitle: \"{article['afaan_oromoo']['title']}\"\ncategories: {cat}\nlang: om\nsource: \"{source}\"\n---\n\n{article['afaan_oromoo']['content']}\n\n<p><strong>📌 Madda:</strong> {source}</p>"
        with open(om_file, "w", encoding="utf-8") as f:
            f.write(om_meta)

        # 3. Save English Post
        en_dir = "_posts/en"
        os.makedirs(en_dir, exist_ok=True)
        en_file = f"{en_dir}/{today}-{cat}-{timestamp}-{idx}.md"
        en_meta = f"---\nlayout: post\ntitle: \"{article['english']['title']}\"\ncategories: {cat}\nlang: en\nsource: \"{source}\"\n---\n\n{article['english']['content']}\n\n<p><strong>📌 Source:</strong> {source}</p>"
        with open(en_file, "w", encoding="utf-8") as f:
            f.write(en_meta)

    print(f"✅ Generated and saved {len(articles) * 3} post files across AM, OM, and EN!")

async def main():
    try:
        print("Fetching feeds...")
        raw_news = await fetch_all_feeds()
        if not raw_news:
            print("❌ No news items fetched.")
            return
        
        print(f"Processing {len(raw_news)} raw items...")
        articles = generate_tri_lingual_articles(raw_news)
        if articles:
            save_markdown_posts(articles)
        else:
            print("⚠️ Article array empty. Skipping file saving.")
    except Exception as e:
        print(f"❌ Execution error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
