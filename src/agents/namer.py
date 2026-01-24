import os
import datetime
from src.state import AgentState

def namer_node(state: AgentState):
    """
    Collects full titles from storyboards and generates a final video title by joining them.
    Saves the title to output/title.txt.
    """
    print("--- Namer Node (Direct) ---")
    
    # Extract full titles from approved storyboards
    storyboards = state.get("ready_to_render_storyboards", [])
    full_titles = [sb.title for sb in storyboards if sb.title]
    
    if not full_titles:
        print("Namer: No titles found to process.")
        return {}

    date_str = datetime.datetime.now().strftime("%-m月%-d日")
    # Concatenate all titles with separator
    combined = " | ".join(full_titles)
    final_title = f"{date_str}要闻：{combined}"
    
    # Save output
    os.makedirs("output", exist_ok=True)
    output_path = "output/title.txt"
    
    char_count = len(final_title)
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(final_title)
        
    print(f"Namer: Created title: {final_title}")
    print(f"Namer: Character count: {char_count}")
    print(f"Namer: Saved to {output_path}")
    
    return {"final_video_path": state.get("final_video_path")} # Just pass-through
