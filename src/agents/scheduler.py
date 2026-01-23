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

    if not queue:
        print("Scheduler: Queue empty. Proceeding to Batch Renderer.")
        return {
            "news_urls": [], 
            "news_url": None, 
            # We don't return generated_segments here anymore, 
            # as the batch renderer will produce them.
        }

    # Pop next URL
    next_url = queue[0]
    remaining_urls = queue[1:]
    
    # Increment Index
    next_idx = current_idx + 1
    
    print(f"Scheduler: Starting next URL ({next_idx}): {next_url}")
    print(f"Scheduler: Remaining in queue: {len(remaining_urls)}")

    # Return update to state
    return {
        "news_urls": remaining_urls,
        "news_url": next_url,
        "current_video_index": next_idx,
        "generated_segments": new_segments,
        
        # Reset single-video state
        "storyboard": None,
        "script_draft": None,
        "audio_path": None,
        "video_path": None,
        "screenshot_paths": [],
        "audios_map": {}, # Reset map if it exists
        "images_map": {}, 
        "is_approved": False, # Reset approval
        "user_feedback": None
    }
