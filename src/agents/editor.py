from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os

import requests
from bs4 import BeautifulSoup

def scraper_node(state: dict):
    """
    Fetches the content from the news_url.
    """
    url = state.get("news_url")
    print(f"Scraper: Fetching content from {url}...")
    
    try:
        # Use a standard user-agent
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # clean up the html
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Basic content extraction heuristics
        # 1. Try to find the article body
        article = soup.find('article')
        if article:
            text = article.get_text(separator="\n", strip=True)
        else:
            # Fallback to all p tags
            paragraphs = soup.find_all('p')
            text = "\n".join([p.get_text(strip=True) for p in paragraphs])
            
        headline = ""
        h1 = soup.find('h1')
        if h1:
            headline = h1.get_text(strip=True)

        if not text:
            text = "Could not extract text. " + headline

        print(f"Scraper: Content fetched ({len(text)} chars).")
        return {"raw_text": text, "headlines": [headline] if headline else []}

    except Exception as e:
        print(f"Scraper Error: {e}")
        return {"raw_text": f"Error fetching {url}: {e}"}

def editor_node(state: dict):
    """
    Summarizes the raw text using an LLM into a script.
    """
    raw_text = state.get("raw_text", "")
    news_url = state.get("news_url", "")
    
    print("Editor: Summarizing/Writing script...")
    
    # Check for API Keys
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    llm = None
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        print("Editor: Using Google Gemini...")
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7, google_api_key=gemini_key)

    prompt = """
    You are a serious news editor for a financial news automation system.
    Write a 30-45 second news script in Chinese (Mandarin) based on the provided text.
    
    Style Guidelines (in Chinese):
    - Tone: Serious, Professional, "Non-AI" (严肃，专业).
    - Style: Financial Times / BBC / CCTV Finance style.
    - Structure: Inverted Pyramid (Most important info first).
    - No filler words like "In conclusion" (综上所述), "As we can see".
    - Focus on data, numbers, and facts.
    - Do not include visual directions, just the spoken script.
    """
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Source URL: {news_url}\n\nContent:\n{raw_text}")
    ]
    
    response = llm.invoke(messages)
    script_draft = response.content
    
    # Save script to file
    os.makedirs("output/script", exist_ok=True)
    script_path = f"output/script/script_{os.urandom(4).hex()}.txt"
    with open(script_path, "w") as f:
        f.write(script_draft)
    
    print(f"Editor: Script generated ({len(script_draft)} chars). Saved to {script_path}")
    return {"script_draft": script_draft, "script_path": script_path}
