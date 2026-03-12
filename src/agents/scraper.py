import os
import requests
import json
import xml.etree.ElementTree as ET
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from src.state import AgentState

# --- The Globe and Mail RSS Configuration ---
TGM_RSS_FEEDS = [
    "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/world/",
    "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/business/",
    "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/technology/"
]

def get_articles_from_rss(rss_urls, limit_per_feed=2):
    """
    Fetches and parses Globe and Mail RSS feeds to extract article metadata using standard library XML parser.
    Returns a list of dicts: {"url": ..., "title": ..., "description": ...}
    """
    all_articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    
    for rss_url in rss_urls:
        try:
            print(f"Fetching RSS: {rss_url}")
            resp = requests.get(rss_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                content = resp.text.encode('utf-8')
                root = ET.fromstring(content)
                items = root.findall('.//item')
                count = 0
                for item in items:
                    link_node = item.find('link')
                    title_node = item.find('title')
                    desc_node = item.find('description')
                    
                    if link_node is not None and link_node.text:
                        url = link_node.text.strip()
                        title = title_node.text.strip() if title_node is not None and title_node.text else "No Title"
                        desc = desc_node.text.strip() if desc_node is not None and desc_node.text else ""
                        
                        # Clean CDATA or HTML from description if needed (TGM often has it)
                        if desc:
                            desc = BeautifulSoup(desc, "html.parser").get_text(strip=True)

                        # Avoid duplicates
                        if not any(a['url'] == url for a in all_articles):
                            all_articles.append({
                                "url": url,
                                "title": title,
                                "description": desc
                            })
                            count += 1
                        if count >= limit_per_feed:
                            break
                print(f"  -> Found {count} items")
            else:
                print(f"  -> Failed to fetch RSS ({resp.status_code})")
        except Exception as e:
            print(f"  -> RSS Error: {e}")
            
    return all_articles

def extract_content_from_html(html_content):
    """
    Helper function to robustly extract text and headline from HTML.
    Optimized for The Globe and Mail.
    Returns (text, headline) tuple.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Headline Extraction
    headline = ""
    h1 = soup.find('h1')
    if h1:
        headline = h1.get_text(strip=True)
    else:
        title_tag = soup.find('title')
        if title_tag:
            headline = title_tag.get_text(strip=True)
            # Clean up TGM suffix
            headline = re.split(r' - The Globe and Mail| \| The Globe and Mail', headline)[0]

    # 2. Content Extraction Heuristics
    text = ""
    
    # Priority A: TGM Article Body
    body = soup.find('div', class_=re.compile(r'article-body|c-article-body', re.I))
    if body:
        text = body.get_text(separator="\n", strip=True)
    
    # Priority B: <article> tag
    if len(text) < 400:
        article = soup.find('article')
        if article:
            text = article.get_text(separator="\n", strip=True)
    
    # Priority C: <main> tag
    if len(text) < 400:
        main_tag = soup.find('main')
        if main_tag:
            text = main_tag.get_text(separator="\n", strip=True)
            
    # Priority D: Aggressive <p> tag scraping
    if len(text) < 400:
        paragraphs = soup.find_all('p')
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40]
        text = "\n".join(valid_paragraphs)

    # Filter out common paywall/nav text patterns for TGM
    junk_patterns = ["Subscribe to The Globe", "exclusive for subscribers", "Log In", "Create Free Account"]
    if any(pattern in text for pattern in junk_patterns) and len(text) < 800:
        # If we see paywall markers and text is short, it's likely a fail
        return "", headline
        
    return text, headline

# --- Batch Scraper Step ---
def batch_scraper_node(state: AgentState):
    """
    Globe and Mail RSS Scraper:
    1. Fetches article metadata from TGM RSS feeds.
    2. Scrapes full content.
    3. Fallback to RSS description if scraping fails.
    """
    print("Batch Scraper: Fetching articles metadata from The Globe and Mail RSS feeds...")
    rss_articles = get_articles_from_rss(TGM_RSS_FEEDS, limit_per_feed=3)
    
    if not rss_articles:
        print("Batch Scraper: No articles found in RSS feeds.")
        return {"scraped_articles": [], "news_urls": []}

    print(f"Batch Scraper: Processing {len(rss_articles)} articles...")
    
    scraped_data = []
    
    # Requests headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }

    # Browser instance (lazy init if needed)
    playwright_instance = None
    browser = None
    
    for item in rss_articles:
        url = item['url']
        rss_title = item['title']
        rss_desc = item['description']
        
        print(f"  - Fetching {url}...")
        text = ""
        headline = ""
        content_found = False
        
        # --- Attempt 1: Requests (Fast) ---
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                text, headline = extract_content_from_html(resp.text)
                if len(text) > 400:
                    content_found = True
                    print(f"    -> Success (Requests): {len(text)} chars")
            else:
                print(f"    -> Request failed ({resp.status_code}).")
        except Exception as e:
            print(f"    -> Request Error: {e}")

        # --- Attempt 2: Playwright (Robust fallback) ---
        if not content_found:
            print("    -> Attempting Playwright Fallback...")
            try:
                if not playwright_instance:
                    playwright_instance = sync_playwright().start()
                    browser = playwright_instance.chromium.launch(headless=True, args=["--disable-http2"])
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                
                text, headline = extract_content_from_html(page.content())
                if len(text) > 400:
                    content_found = True
                    print(f"    -> Success (Playwright): {len(text)} chars")
                else:
                    print(f"    -> Playwright also returned limited content (Paywall likely).")
                
                context.close()
            except Exception as e:
                print(f"    -> Playwright Fallback Error: {e}")

        # --- Final Content Preparation ---
        # Prefer rss_title if scraped headline is generic or missing
        is_generic_headline = headline.lower() in ["the globe and mail", "globe and mail", "tgm", "error"]
        final_headline = rss_title if (not headline or is_generic_headline or len(headline) < 10) else headline
        
        # We no longer provide a 'summary' fallback to RSS description.
        # We only provide the scraped text in 'raw_news'.
        
        scraped_data.append({
            "url": url,
            "raw_news": text,
            "headline": final_headline
        })

    # Cleanup Playwright
    if browser: browser.close()
    if playwright_instance: playwright_instance.stop()

    # Save Scraped Data
    os.makedirs("output/raw_news", exist_ok=True)
    save_path = "output/raw_news/scraped_data.json"
    with open(save_path, "w", encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=2, ensure_ascii=False)
        
    print(f"Batch Scraper: Completed. {len(scraped_data)} processed. Saved to {save_path}")
    return {"scraped_articles": scraped_data, "news_urls": [a['url'] for a in rss_articles]}
