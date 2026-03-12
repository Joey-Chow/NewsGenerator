from langchain_core.messages import SystemMessage, HumanMessage
import os
import json
import re
from src.state import AgentState, Storyboard
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
        text = article["raw_news"]
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
