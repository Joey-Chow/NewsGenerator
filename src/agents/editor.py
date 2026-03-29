import os
import json
import re
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, Storyboard

# --- Batch Editor Step ---
async def batch_editor_node(state: AgentState):
    """
    Iterates through 'scraped_articles' and generates storyboards for the first 2 articles.
    Output: draft_storyboards (List[Storyboard])
    """
    def sync_editor():
        all_articles = state.get("scraped_articles", [])
        user_feedback = state.get("user_feedback")
        critic_feedback = state.get("script_critic_feedback")
        failed_indices = state.get("script_critic_failed_indices")
        existing_storyboards = state.get("draft_storyboards", [])

        # Merge critic feedback into user_feedback so the same revision logic applies
        if critic_feedback and not user_feedback:
            user_feedback = f"[Auto-Critic Feedback] {critic_feedback}"

        # --- Selective regeneration mode ---
        # If the script critic flagged specific storyboards, only regenerate those
        if failed_indices is not None and existing_storyboards:
            print(f"Batch Editor: Selective mode — only regenerating failed storyboards at indices {failed_indices}")
            print(f"  Keeping {len(existing_storyboards) - len(failed_indices)} approved storyboard(s) unchanged.")
            articles = all_articles[:2]  # Use same article set
        # --- Human feedback mode: full re-selection ---
        elif user_feedback and len(all_articles) > 0:
            failed_indices = None  # Reset — human feedback regenerates everything
            print(f"Batch Editor: LLM is dynamically selecting articles based on feedback: '{user_feedback}'")
            # Prepare list of titles
            title_list_str = "\n".join([f"[{i}] {a.get('title', 'Unknown Title')}" for i, a in enumerate(all_articles)])

            selection_prompt = f"""
            The user rejected the previous draft and wants to change the news articles based on this feedback:
            "{user_feedback}"

            Available scraped articles:
            {title_list_str}

            Please select EXACTLY 2 articles from the list above that best match the user's new request.
            If the user's feedback is just about style (e.g. "make it funny") and doesn't dictate a topic change, just return the first 2 indices: [0, 1].

            Return ONLY a JSON array of the 2 integer indices. Example: [2, 5]
            """
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if gemini_key:
                from langchain_google_genai import ChatGoogleGenerativeAI
                try:
                    sel_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1, google_api_key=gemini_key)
                    sel_response = sel_llm.invoke([HumanMessage(content=selection_prompt)])
                    match = re.search(r'\[\s*\d+\s*,\s*\d+\s*\]', sel_response.content)
                    if match:
                        selected_indices = json.loads(match.group(0))
                        print(f"Batch Editor: LLM dynamically selected indices: {selected_indices}")
                        articles = [all_articles[i] for i in selected_indices if i < len(all_articles)]
                    else:
                        print("Batch Editor: Failure to parse LLM array. Falling back to default.")
                        articles = all_articles[:2]
                except Exception as e:
                    print(f"Batch Editor: Selection failed: {e}")
                    articles = all_articles[:2]
            else:
                articles = all_articles[:2]
        else:
            # Default behavior — first run
            failed_indices = None
            articles = all_articles[:2]

        print(f"Batch Editor: Processing {len(failed_indices) if failed_indices is not None else len(articles)} article(s)...")
        
        gemini_key = os.environ.get("GEMINI_API_KEY")
        llm = None
        if gemini_key:
            from langchain_google_genai import ChatGoogleGenerativeAI
            # Using a slightly faster/cheaper model for batch validity if desired, but sticking to trusted config
            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7, google_api_key=gemini_key)
        else:
            print("Batch Editor Error: No GEMINI_API_KEY found.")
            return {"draft_storyboards": []}
            
        feedback_instruction = ""
        if user_feedback:
            print(f"Batch Editor: Applying Global User Feedback: {user_feedback}")
            feedback_instruction = f"\n\nCRITICAL USER FEEDBACK FOR REVISION:\nThe user rejected the previous draft and requested the following changes:\n\"{user_feedback}\"\nYou MUST strictly follow this feedback when generating the new storyboard!"

        prompt_template = """
        You are a professional News Editor and Director. 
        Your task is to transform the provided news article into a video storyboard (JSON format).

        Input: A news article text.
        Output: A JSON object matching the following structure:
        {
          "title": "Video Title",
          "scenes": [
            {
              "id": 1,
              "subtitle_text": "First sentence of the script...", 
              "image_search_query": "English search query for Google Images"
            },
            ...
          ]
        }

        Guidelines:
        1. **Script (subtitle_text)**:
           - Language: English.
           - Tone: Professional, engaging, and authoritative.
           - **Narrative Flow**: Ensure logical transitions between scenes. Avoid jumpy or fragmented sentences. 
           - **Structure**:
             - Scene 1: Hook & Source citation (e.g. "According to Reuters, a major event occurred today...").
             - Middle Scenes: Explain the 'Why' and 'How'. Connect the facts into a story.
             - Final Scene: Implication or future outlook.
           - Max 5-8 scenes total.
           - Each scene is one spoken sentence. 
           - NO trailing punctuation (strip '.').
        
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
        """ + feedback_instruction

        # Determine which articles to regenerate
        if failed_indices is not None:
            indices_to_generate = failed_indices
        else:
            indices_to_generate = list(range(len(articles)))

        generated_storyboards = list(existing_storyboards) if failed_indices is not None else []

        for idx in indices_to_generate:
            if idx >= len(articles):
                print(f"  - Skipping index {idx} (out of range)")
                continue

            article = articles[idx]
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

                # In selective mode, replace in-place; otherwise append
                if failed_indices is not None and idx < len(generated_storyboards):
                    old_title = generated_storyboards[idx].title
                    generated_storyboards[idx] = sb
                    print(f"    -> Replaced storyboard {idx+1}: '{old_title}' → '{sb.title}'")
                else:
                    generated_storyboards.append(sb)
                    print(f"    -> Generated Storyboard: {sb.title}")

                # Save Debug Copy
                os.makedirs("output/storyboard", exist_ok=True)
                with open(f"output/storyboard/storyboard_{idx+1}.json", "w", encoding='utf-8') as f:
                    f.write(sb.model_dump_json(indent=2))

            except Exception as e:
                print(f"    -> Editor Failed for {url}: {e}")
                # Don't replace — keep existing storyboard if in selective mode

        print(f"Batch Editor: Finished. {len(generated_storyboards)} drafts ready.")

        # Clear feedback fields after processing so they don't loop indefinitely
        return {
            "draft_storyboards": generated_storyboards,
            "user_feedback": None,
            "script_critic_failed_indices": None,
        }

    return await asyncio.to_thread(sync_editor)
