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

    import json
    import re

    prompt = """
    You are a serious news editor for a financial news automation system.
    Generate a JSON output containing a list of sentences in Chinese (Mandarin) based on the provided text.
    
    Output Format:
    A single valid JSON object: {"sentences": ["Sentence 1", "Sentence 2", ...]}
    
    Style Guidelines (in Chinese):
    - Tone: Serious, Professional, "Non-AI" (严肃，专业).
    - Style: Financial Times / BBC / CCTV Finance style.
    - Structure: Inverted Pyramid (Most important info first).
    - Maximum of 5 sentences.
    - No filler words like "In conclusion" (综上所述), "As we can see".
    - CRITICAL: The FIRST sentence MUST explicitly cite the source of the article (e.g., 'According to BBC News...', 'Reuters reports that...').
    - Split the news into clear, spoken sentences.
    - CRITICAL: Strip any trailing punctuation (period, exclamation, question mark) from the end of each sentence string in the JSON list.
    - The generated content should be the spoken script.
    """
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Source URL: {news_url}\n\nContent:\n{raw_text}")
    ]
    
    print("Editor: Invoking LLM for JSON script...")
    response = llm.invoke(messages)
    content = response.content
    
    # Parse JSON
    try:
        # Helper to find JSON block if it's wrapped in markdown code fence
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
            
        data = json.loads(content)
        sentences = data.get("sentences", [])
    except Exception as e:
        print(f"Editor: Failed to parse JSON response: {content[:100]}... Error: {e}")
        # Fallback: treat whole content as one sentence (maybe split by newlines)
        sentences = [content.strip()]

    # Reconstruct script_draft for TTS (add periods back for flow, if needed, or just space)
    # TTS usually handles spaces or newlines. Let's add periods back for safer TTS pausing if they were stripped.
    # Note: Chinese period is "。" 
    script_draft = "。".join(sentences) + "。"
    
    # Save script to file (now JSON)
    os.makedirs("output/script", exist_ok=True)
    file_id = os.urandom(4).hex()
    script_json_path = f"output/script/script_{file_id}.json"
    
    with open(script_json_path, "w", encoding='utf-8') as f:
        json.dump({"sentences": sentences}, f, ensure_ascii=False, indent=2)
    
    print(f"Editor: Script generated ({len(sentences)} sentences). Saved to {script_json_path}")
    
    # We return script_draft (string) for Reporter (TTS) and sentences (list) for Renderer (Visuals)
    return {
        "script_draft": script_draft, 
        "script_path": script_json_path, 
        "sentences": sentences
    }
