import os
import datetime
import json
import glob
import subprocess
from src.state import AgentState, Storyboard

# --- YouTube API Imports ---
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def authenticate_youtube():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secret_file = "client_secrets.json"
            if not os.path.exists(client_secret_file):
                if os.path.exists("client_secret.json"):
                    client_secret_file = "client_secret.json"
                else:
                    print("====================================")
                    print("❌ Youtuber Error: Missing 'client_secrets.json'.")
                    print("Please download it from Google Cloud Console and place it in the project root to enable actual YouTube uploads.")
                    print("====================================")
                    return None
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
    return build("youtube", "v3", credentials=creds)

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
    date_str = datetime.datetime.now().strftime("%B %-d")
    combined_titles = " | ".join(full_titles)
    final_title = f"{date_str} News Update: {combined_titles}"

    # --- 2. Chapter & Description Generation ---
    intro_path = "assets/intro.mov"
    current_time = 0.0
    
    chapter_lines = []
    description_paragraphs = []
    
    # 00:00 Intro
    chapter_lines.append(f"{format_timestamp(current_time)} Intro")
    
    # Get intro duration (usually ~4.5s)
    intro_dur = get_media_duration(intro_path) or 4.5
    current_time += intro_dur
    
    for sb in storyboards:
        # Chapter Line
        timestamp = format_timestamp(current_time)
        chapter_lines.append(f"{timestamp} {sb.title}")
        
        # Description Paragraph (Join all script sentences)
        paragraph = " ".join([s.subtitle_text for s in sb.scenes])
        # Add period if missing for visual separation in description
        if not paragraph.endswith('.'): paragraph += '.'
        description_paragraphs.append(paragraph)
        
        # Increment time
        sb_dur = sum(s.duration for s in sb.scenes if s.duration)
        current_time += sb_dur
        
    # Final Outro
    chapter_lines.append(f"{format_timestamp(current_time)} Outro")
    
    # --- Assemble Final Metadata ---
    metadata_content = []
    metadata_content.append("[Video Title]")
    metadata_content.append(final_title)
    metadata_content.append("\n" + "="*20 + "\n")
    
    metadata_content.append("[Chapters]")
    metadata_content.append("\n".join(chapter_lines))
    metadata_content.append("\n" + "="*20 + "\n")
    
    metadata_content.append("[Description]")
    metadata_content.append("\n\n".join(description_paragraphs))
    
    final_text = "\n".join(metadata_content)
    
    # Save to file
    os.makedirs("output", exist_ok=True)
    output_path = "output/youtube_metadata.txt"
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(final_text)
        
    print(f"Youtuber: Metadata generated and saved to {output_path}")
    print(f"Youtuber: Title: {final_title}")
    
    # --- 3. Actual YouTube API Upload ---
    final_video_path = state.get("final_video_path")
    
    # Format actual YouTube description based on limits
    upload_desc = f"{combined_titles}\n\n[Chapters]\n" + "\n".join(chapter_lines) + "\n\n" + "\n\n".join(description_paragraphs)
    upload_title = final_title if len(final_title) <= 100 else final_title[:97] + "..."
    
    if final_video_path and os.path.exists(final_video_path):
        youtube_client = authenticate_youtube()
        if youtube_client:
            try:
                print(f"Youtuber: Uploading {final_video_path} to YouTube... (This may take a while)")
                request = youtube_client.videos().insert(
                    part="snippet,status",
                    body={
                      "snippet": {
                        "categoryId": "25", # News & Politics
                        "description": upload_desc[:4900], # Safety max 5000
                        "title": upload_title,
                        "tags": ["News", "AI News", "Current Events", "Update"]
                      },
                      "status": {
                        "privacyStatus": "public", # Publish immediately as requested
                        "selfDeclaredMadeForKids": False, 
                      }
                    },
                    media_body=MediaFileUpload(final_video_path, chunksize=-1, resumable=True)
                )
                response = request.execute()
                yt_url = f"https://youtu.be/{response['id']}"
                print(f"✅ Youtuber: Upload Successful! Video URL: {yt_url}")
                return {"final_video_path": final_video_path, "youtube_url": yt_url}
            except Exception as e:
                print(f"❌ Youtuber Upload Error: {e}")
        else:
            print("Youtuber: Skipping automated YouTube upload due to missing credentials.")
    else:
        print("Youtuber: 'final_video_path' not found or does not exist. Cannot upload video.")
    
    return {"final_video_path": final_video_path}

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
