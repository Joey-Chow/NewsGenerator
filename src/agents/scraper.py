import os
import requests
import json
import xml.etree.ElementTree as ET
import re
import asyncio
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
    all_articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
    for rss_url in rss_urls:
        try:
            resp = requests.get(rss_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text.encode('utf-8'))
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
                        if desc: desc = BeautifulSoup(desc, "html.parser").get_text(strip=True)
                        if not any(a['url'] == url for a in all_articles):
                            all_articles.append({"url": url, "title": title, "description": desc})
                            count += 1
                        if count >= limit_per_feed: break
        except Exception as e: print(f"RSS Error: {e}")
    return all_articles

def extract_content_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    headline = ""
    h1 = soup.find('h1')
    if h1: headline = h1.get_text(strip=True)
    else:
        title_tag = soup.find('title')
        if title_tag:
            headline = title_tag.get_text(strip=True)
            headline = re.split(r' - The Globe and Mail| \| The Globe and Mail', headline)[0]
    text = ""
    body = soup.find('div', class_=re.compile(r'article-body|c-article-body', re.I))
    if body: text = body.get_text(separator="\n", strip=True)
    if len(text) < 400:
        article = soup.find('article')
        if article: text = article.get_text(separator="\n", strip=True)
    if len(text) < 400:
        main_tag = soup.find('main')
        if main_tag: text = main_tag.get_text(separator="\n", strip=True)
    if len(text) < 400:
        paragraphs = soup.find_all('p')
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40]
        text = "\n".join(valid_paragraphs)
    return text, headline

async def batch_scraper_node(state: AgentState):
    """
    Globe and Mail RSS Scraper (Async wrapper)
    """
    # Skip scraping if articles were pre-injected (e.g., by eval runner)
    if state.get("scraped_articles"):
        print("Scraper: Articles already present in state, skipping RSS fetch.")
        return {}

    def sync_scraper():
        print("Scraper: Fetching articles...")
        rss_articles = get_articles_from_rss(TGM_RSS_FEEDS, limit_per_feed=3)
        if not rss_articles: return {"scraped_articles": [], "news_urls": []}
        scraped_data = []
        headers = {"User-Agent": "Mozilla/5.0"}
        playwright_instance = None
        browser = None
        for item in rss_articles:
            url = item['url']
            content_found = False
            text, headline = "", ""
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    text, headline = extract_content_from_html(resp.text)
                    if len(text) > 400: content_found = True
            except: pass
            if not content_found:
                try:
                    if not playwright_instance:
                        playwright_instance = sync_playwright().start()
                        browser = playwright_instance.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    text, headline = extract_content_from_html(page.content())
                    content_found = True
                    context.close()
                except: pass
            scraped_data.append({"url": url, "raw_news": text, "headline": headline or item['title']})
        if browser: browser.close()
        if playwright_instance: playwright_instance.stop()
        os.makedirs("output/raw_news", exist_ok=True)
        with open("output/raw_news/scraped_data.json", "w", encoding='utf-8') as f:
            json.dump(scraped_data, f, indent=2, ensure_ascii=False)
        return {"scraped_articles": scraped_data, "news_urls": [a['url'] for a in rss_articles]}

    return await asyncio.to_thread(sync_scraper)
