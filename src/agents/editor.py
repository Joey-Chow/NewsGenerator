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
    你是一个专业的新闻播报员。
    当前时间是 2026 年 (请注意：不要使用你训练数据中的旧时间)。
    关键事实修正：
    - 唐纳德·特朗普 (Donald Trump) 是现任美国总统，不是前总统
    - 报道风格必须严谨、客观。
    
    You are a professional News Editor and Director. 
    Your task is to transform the provided news article into a video storyboard (JSON format).

    Input: A news article text.
    Output: A JSON object matching the following structure:
    {
      "scenes": [
        {
          "id": 1,
          "subtitle_text": "First sentence of the script...", 
          "visual_instruction": "Instruction for the human editor...",
          "image_search_query": "English search query for Google Images"
        },
        ...
      ],
      "title": "Short Video Title",
      "background_music_mood": "Mood description (e.g. suspenseful, upbeat)"
    }

    Guidelines:
    1. **Script (subtitle_text)**:
       - Language: Chinese (Mandarin).
       - Tone: Serious, Professional.
       - The FIRST scene's subtitle MUST explicitly cite the source.
       - Max 5-8 scenes total.
       - Each scene is one spoken sentence. 
       - NO trailing punctuation (strip '。').
    
    2. **Visuals**:
       - **visual_instruction**: Instructions for human editor (Chinese/English).
       - **image_search_query**: SPECIFIC English search query for Google Images.
         - Concrete subjects (e.g. "Stock market crash chart", "Joe Biden podium").
         - Avoid abstract concepts.
         - Ensure it is a valid search term.
       
    3. **General**:
       - Return ONLY valid JSON.
    """
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Source URL: {news_url}\n\nContent:\n{raw_text}")
    ]
    
    print("Editor: Invoking LLM for Storyboard...")
    from src.state import Storyboard, Scene

    storyboard = None
    try:
        if ConfiguredLLM := getattr(llm, "with_structured_output", None):
             structured_llm = llm.with_structured_output(Storyboard)
             storyboard = structured_llm.invoke(messages)
    except Exception as e:
        print(f"Editor: Structured output failed: {e}")

    if not storyboard:
        # Manual parsing
        response = llm.invoke(messages)
        content = response.content
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match: content = json_match.group(0)
            data = json.loads(content)
            # Handle if it's wrapped in 'storyboard' key or direct
            if "scenes" not in data and "storyboard" in data:
                data = data["storyboard"]
            storyboard = Storyboard(**data)
        except Exception as e:
             print(f"Editor: Manual parsing failed: {e}. Content: {content[:100]}")
             # Create dummy
             storyboard = Storyboard(scenes=[], title="Error", background_music_mood="Error")

    # Save
    os.makedirs("output/storyboard", exist_ok=True)
    video_idx = state.get("current_video_index", 1)
    storyboard_path = f"output/storyboard/storyboard_{video_idx}.json"
    
    with open(storyboard_path, "w", encoding='utf-8') as f:
        f.write(storyboard.model_dump_json(indent=2))
        
    print(f"Editor: Storyboard generated ({len(storyboard.scenes)} scenes). Saved to {storyboard_path}")
    
    return {"storyboard": storyboard}
