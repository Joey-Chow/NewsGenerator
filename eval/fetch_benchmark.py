"""
Fetch real articles from Globe and Mail RSS to populate benchmark_articles.json.

Usage:
    python -m eval.fetch_benchmark
"""
import json
import requests
from src.agents.scraper import get_articles_from_rss, extract_content_from_html, TGM_RSS_FEEDS


def main():
    print("Fetching articles from RSS feeds...")
    articles = get_articles_from_rss(TGM_RSS_FEEDS, limit_per_feed=3)
    print(f"Found {len(articles)} RSS entries")

    results = []
    for item in articles:
        print(f"  Scraping: {item['title'][:60]}...")
        try:
            resp = requests.get(
                item["url"],
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            text, headline = extract_content_from_html(resp.text)
            if len(text) > 100:
                results.append({
                    "url": item["url"],
                    "title": item["title"],
                    "raw_news": text,
                })
                print(f"    OK ({len(text)} chars)")
            else:
                print(f"    Skipped (too short: {len(text)} chars)")
        except Exception as e:
            print(f"    Failed: {e}")

    results = results[:5]
    out_path = "eval/benchmark_articles.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(results)} articles to {out_path}")


if __name__ == "__main__":
    main()
