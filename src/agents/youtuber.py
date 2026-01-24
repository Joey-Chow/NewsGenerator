import os
import datetime
import json
import glob
import subprocess
from src.state import AgentState, Storyboard

def get_media_duration(file_path):
    try:
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except:
        return 0.0

def format_timestamp(seconds: float) -> str:
    td = datetime.timedelta(seconds=round(seconds))
    total_seconds = int(td.total_seconds())
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"

def youtuber_node(state: AgentState):
    """
    1. Generates a final video title.
    2. Generates YouTube Chapters/Timestamps.
    3. Concatenates subtitles into paragraphs for the description.
    All outputs are saved into a single TXT file: output/youtube_metadata.txt.
    """
    print("--- Youtuber Node ---")
    
    storyboards = state.get("ready_to_render_storyboards", [])
    if not storyboards:
        print("Youtuber: No storyboards found in state.")
        return {}

    # --- 1. Title Generation ---
    full_titles = [sb.title for sb in storyboards if sb.title]
    date_str = datetime.datetime.now().strftime("%-m月%-d日")
    combined_titles = " | ".join(full_titles)
    final_title = f"{date_str}要闻：{combined_titles}"

    # --- 2. Chapter & Description Generation ---
    intro_path = "assets/intro.mov"
    current_time = 0.0
    
    chapter_lines = []
    description_paragraphs = []
    
    # 00:00 Intro
    chapter_lines.append(f"{format_timestamp(current_time)} 开场 Intro")
    
    # Get intro duration (usually ~4.5s)
    intro_dur = get_media_duration(intro_path) or 4.5
    current_time += intro_dur
    
    for sb in storyboards:
        # Chapter Line
        timestamp = format_timestamp(current_time)
        chapter_lines.append(f"{timestamp} {sb.title}")
        
        # Description Paragraph (Join all script sentences)
        paragraph = "".join([s.subtitle_text for s in sb.scenes])
        # Add period if missing for visual separation in description
        if not paragraph.endswith('。'): paragraph += '。'
        description_paragraphs.append(paragraph)
        
        # Increment time
        sb_dur = sum(s.duration for s in sb.scenes if s.duration)
        current_time += sb_dur
        
    # Final Outro
    chapter_lines.append(f"{format_timestamp(current_time)} 结语 Outro")
    
    # --- Assemble Final Metadata ---
    metadata_content = []
    metadata_content.append("【视频标题】")
    metadata_content.append(final_title)
    metadata_content.append("\n" + "="*20 + "\n")
    
    metadata_content.append("【章节时间戳】")
    metadata_content.append("\n".join(chapter_lines))
    metadata_content.append("\n" + "="*20 + "\n")
    
    metadata_content.append("【视频简介】")
    metadata_content.append("\n\n".join(description_paragraphs))
    
    final_text = "\n".join(metadata_content)
    
    # Save to file
    os.makedirs("output", exist_ok=True)
    output_path = "output/youtube_metadata.txt"
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(final_text)
        
    print(f"Youtuber: Metadata generated and saved to {output_path}")
    print(f"Youtuber: Title: {final_title}")
    
    return {"final_video_path": state.get("final_video_path")}

# --- Standalone Test Block ---
if __name__ == "__main__":
    print("Testing Youtuber Node with local storyboard JSONs...")
    
    storyboard_dir = "output/storyboard"
    json_files = glob.glob(os.path.join(storyboard_dir, "storyboard_*.json"))
    
    def extract_id(f):
        try: return int(os.path.basename(f).split('_')[1].split('.')[0])
        except: return 999
    
    json_files.sort(key=extract_id)
    
    test_storyboards = []
    for fpath in json_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            sb = Storyboard(**data)
            for s in sb.scenes:
                if not s.duration: s.duration = 5.0 # Mock
            test_storyboards.append(sb)
            
    test_state = {
        "ready_to_render_storyboards": test_storyboards,
        "final_video_path": "output/final_broadcasts/test.mp4"
    }
    
    youtuber_node(test_state)
