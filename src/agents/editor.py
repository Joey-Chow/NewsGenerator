from langchain_core.messages import SystemMessage, HumanMessage
import os
import requests
from bs4 import BeautifulSoup
import json
import re
from src.state import AgentState, Storyboard
from playwright.sync_api import sync_playwright

def extract_content_from_html(html_content):
    """
    Helper function to robustly extract text and headline from HTML.
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

    # 2. Content Extraction Heuristics
    text = ""
    
    # Priority A: <article> tag
    article = soup.find('article')
    if article:
        text = article.get_text(separator="\n", strip=True)
    
    # Priority B: <main> tag (if article missing or too short)
    if len(text) < 300:
        main_tag = soup.find('main')
        if main_tag:
            text = main_tag.get_text(separator="\n", strip=True)
            
    # Priority C: Aggressive <p> tag scraping (filter out short links/menus)
    if len(text) < 300:
        paragraphs = soup.find_all('p')
        # Filter out very short paragraphs (likely menu items/footer) to reduce noise
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        text = "\n".join(valid_paragraphs)

    if not text:
        text = "Could not extract text. " + headline
        
    return text, headline

# --- Batch Scraper Step ---
def batch_scraper_node(state: AgentState):
    """
    Hybrid Scraper:
    1. Try fast 'requests' fetch.
    2. Fallback to 'playwright' (headless browser) if failed or content < 300 chars.
    """
    urls = state.get("news_urls", [])
    print(f"Batch Scraper: Processing {len(urls)} URLs...")
    
    scraped_data = []
    
    # Requests headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }

    # Browser instance (lazy init if needed)
    playwright_instance = None
    browser = None
    
    for url in urls:
        print(f"  - Fetching {url}...")
        text = ""
        headline = ""
        content_found = False
        
        # --- Attempt 1: Requests (Fast) ---
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                text, headline = extract_content_from_html(resp.text)
                if len(text) > 300:
                    content_found = True
                    print(f"    -> Success (Requests): {len(text)} chars")
                else:
                    print(f"    -> Warning: Requests returned short content ({len(text)} chars). Trying fallback...")
            else:
                print(f"    -> Request failed ({resp.status_code}). Trying fallback...")
        except Exception as e:
            print(f"    -> Request Error: {e}")

        # --- Attempt 2: Playwright (Robust) ---
        if not content_found:
            print("    -> Launching Playwright Fallback...")
            try:
                # Initialize browser ONLY if needed
                if not playwright_instance:
                    playwright_instance = sync_playwright().start()
                    # Disable HTTP/2 to prevent protocol errors on some sites
                    browser = playwright_instance.chromium.launch(headless=True, args=["--disable-http2"])
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    bypass_csp=True
                )
                page = context.new_page()
                
                # Navigate with recovery logic
                try:
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")
                except Exception as nav_err:
                    if "Timeout" in str(nav_err) or "TIMED_OUT" in str(nav_err):
                        print(f"      -> Warning: Navigation timed out. Scraping partial content...")
                    else:
                        print(f"      -> Playwright Navigation Error: {nav_err}")
                        # Don't re-raise, try to get what we can or fail gracefully
                
                # Scroll
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except: pass
                page.wait_for_timeout(3000)
                
                # Parse
                text, headline = extract_content_from_html(page.content())
                content_found = True # Even if short, this is our best bet
                print(f"    -> Success (Playwright): {len(text)} chars")
                
                context.close() # Clean up page/context
                
            except Exception as e:
                print(f"    -> Critical Scraper Failure: {e}")
                text = "Scraping Failed."
                headline = "Error"

        scraped_data.append({
            "url": url,
            "raw_text": text,
            "headline": headline
        })

    # Cleanup Playwright
    if browser:
        browser.close()
    if playwright_instance:
        playwright_instance.stop()

    # Save Scraped Data for Review
    os.makedirs("output", exist_ok=True)
    with open("output/scraped_data.json", "w", encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=2, ensure_ascii=False)
        
    print(f"Batch Scraper: Completed. {len(scraped_data)}/{len(urls)} processed. Saved to output/scraped_data.json")
    return {"scraped_articles": scraped_data}


# --- Batch Editor Step ---
def batch_editor_node(state: AgentState):
    """
    Iterates through 'scraped_articles' and generates storyboards for ALL of them.
    Output: draft_storyboards (List[Storyboard])
    """
    articles = state.get("scraped_articles", [])
    print(f"Batch Editor: Processing {len(articles)} articles...")
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    llm = None
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Using a slightly faster/cheaper model for batch validity if desired, but sticking to trusted config
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7, google_api_key=gemini_key)
    else:
        print("Batch Editor Error: No GEMINI_API_KEY found.")
        return {"draft_storyboards": []}

    prompt_template = """
    You are a professional News Editor and Director. 
    Your task is to transform the provided news article into a video storyboard (JSON format).

    Input: A news article text.
    Output: A JSON object matching the following structure:
    {
      "scenes": [
        {
          "id": 1,
          "subtitle_text": "First sentence of the script...", 
          "image_search_query": "English search query for Google Images"
        },
        ...
      ],
      "title": "Video Title"
    }

    Guidelines:
    1. **Script (subtitle_text)**:
       - Language: Chinese (Mandarin).
       - Tone: Professional, engaging, and authoritative.
       - **Narrative Flow**: Ensure logical transitions between scenes. Avoid jumpy or fragmented sentences. 
       - **Structure**:
         - Scene 1: Hook & Source citation (e.g. "据路透社报道，今天发生了一件大事...").
         - Middle Scenes: Explain the 'Why' and 'How'. Connect the facts into a story.
         - Final Scene: Implication or future outlook.
       - Max 5-8 scenes total.
       - Each scene is one spoken sentence. 
       - NO trailing punctuation (strip '。').
    
    2. **Visuals**:
       - **image_search_query**: SPECIFIC English search query for Google Images.
         - **Focus**: Identify the core SUBJECT and ACTION in the current sentence.
         - **Ignore Citations**: IGNORE phrases like "According to [Source]", "Reported by", "As stated by". 
           - *Example*: If text is "WSJ reports retail sales rose", query should be "people shopping retail mall", NOT "WSJ logo" or "news anchor".
         - **Strict Constraint**: AVOID "news anchor", "news studio", "broadcasting room", "newsroom", "TV presenter" or "reporter".
         - **Negative Constraints**: AVOID charts, diagrams, vectors, generic icons, text slides.
         - **Keywords**: Use terms like "real life photography", "press photo", "high quality photo".
         - Ensure it is a valid search term.
       
    3. **General**:
       - Return ONLY valid JSON.

    4. **CRITICAL GOAL**
       - Create a COHERENT, NARRATIVE-DRIVEN story, not just a list of facts. 
       - The script should flow smoothly from one sentence to the next like a documentary or a feature news segment.

    5. **CRITICAL FACTUAL CORRECTIONS**
       - Current time is 2026.
       - Donald Trump is the current President of the United States. Use the short form "Trump", not the full name "President Donald Trump".
       - Mark Carney is the current Prime Minister of Canada, not Trudeau.
       - Keir Starmer is the current Prime Minister of the United Kingdom.
    """

    generated_storyboards = []

    for idx, article in enumerate(articles):
        url = article["url"]
        text = article["raw_text"]
        print(f"  - Editing Article {idx+1}/{len(articles)} (Source: {url[:30]}...)...")
        
        messages = [
            SystemMessage(content=prompt_template),
            HumanMessage(content=f"Source URL: {url}\n\nContent:\n{text[:15000]}") # Truncate if too huge
        ]
        
        try:
            # Invocation
            response = llm.invoke(messages)
            content = response.content
            
            # Parsing
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match: 
                content = json_match.group(0)
            
            data = json.loads(content)
            if "scenes" not in data and "storyboard" in data:
                data = data["storyboard"]
                
            sb = Storyboard(**data)
            generated_storyboards.append(sb)
            
            # Save Debug Copy
            os.makedirs("output/storyboard", exist_ok=True)
            # Use index + 1 for filename consistency 1-based
            with open(f"output/storyboard/storyboard_{idx+1}.json", "w", encoding='utf-8') as f:
                f.write(sb.model_dump_json(indent=2))
                
            print(f"    -> Generated Storyboard: {sb.title}")

        except Exception as e:
            print(f"    -> Editor Failed for {url}: {e}")
            # Don't append invalid content

    print(f"Batch Editor: Finished. {len(generated_storyboards)} drafts ready.")
    return {"draft_storyboards": generated_storyboards}
