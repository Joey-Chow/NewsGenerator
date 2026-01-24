from src.state import AgentState

def scheduler_node(state: AgentState):
    """
    Manages the batch processing of news URLs.
    - If there are URLs in the queue, pops one and sets it as the current 'news_url'.
    - Clears previous single-video state (storyboard, script, etc.) to ensure a fresh run.
    - If queue is empty, directs the flow to concatenation (handled by conditional edge).
    """
    print("--- Scheduler Node ---")
    
    queue = state.get("news_urls", []) or []
    current_segments = state.get("generated_segments", []) or []
    current_idx = state.get("current_video_index", 0) or 0
    
    # ... (existing segment collection logic) ...
    # BATCH MODE UPDATE: 
    # We no longer collect segments here because rendering happens at the very end.
    # The 'video_path' field will likely be empty during the preparation loop.
    new_segments = []

    # BATCH MODE: Do NOT pop. Just pass the full list to the scraper.
    if not queue:
        print("Scheduler: Queue empty. Nothing to process.")
        return {"news_urls": []}

    print(f"Scheduler: Batch Mode - Passing {len(queue)} URLs to Scraper.")

    # Return update to state (Pass-through)
    return {
        "news_urls": queue, # Keep full list
        "current_video_index": 0, # Start at 0? Or 1? Let's say 0 and loop uses index+1
        
        # Reset single-video state (to be safe, though batch nodes overwrite)
        "storyboard": None,
        "script_draft": None,
        "audio_path": None,
        "video_path": None,
        "screenshot_paths": [],
        "audios_map": {}, 
        "images_map": {}, 
        "is_approved": False, 
        "user_feedback": None
    }
