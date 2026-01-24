import os
import json
import base64
import uuid
import requests
from mutagen import File
from src.state import AgentState

def get_audio_duration_mutagen(file_path):
    try:
        audio = File(file_path)
        if audio is not None and audio.info:
            return float(audio.info.length)
        return 0.0
    except Exception as e:
        print(f"Reporter Warning: Could not get duration for {file_path}: {e}")
        return 0.0

async def batch_reporter_node(state: AgentState):
    """
    Iterates through 'ready_to_render_storyboards' (pop'd from ingest)
    Generates TTS audio for ALL scenes in ALL storyboards.
    Also handles Snapshot Logic (Placeholder: using scene image as snapshot or separate asset?)
    User asked for website snapshot logic - traditionally this was separate, 
    but let's stick to the current flow where 'snapshot' is often just the main image or a specific asset.
    """
    print("Batch Reporter: Generating Audio for batch...")
    
    storyboards = state.get("ready_to_render_storyboards", [])
    if not storyboards:
        print("Batch Reporter: No storyboards ready.")
        return {"ready_to_render_storyboards": []}

    # Load credentials
    APPID = os.getenv("VOLC_APPID")
    TOKEN = os.getenv("VOLC_ACCESS_TOKEN")
    VOICE_TYPE = os.getenv("VOLC_VOICE_TYPE", "BV001_streaming") 
    CLUSTER = "volcano_tts"

    if not APPID or not TOKEN:
        print("Batch Reporter Error: Missing VOLC_APPID or VOLC_ACCESS_TOKEN.")
        return {"ready_to_render_storyboards": storyboards} # Return as is (failed audio)

    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    header = {"Authorization": f"Bearer;{TOKEN}"}

    output_dir = "output/audio"
    os.makedirs(output_dir, exist_ok=True)
    
    # Snapshot Logic: traditionally screenshot_paths were generated separately. 
    # For now, let's assume we proceed with just the audio generation part here.
    # If snapshot logic is needed (30/70 layout), it usually comes from scraping the page screenshot.
    # Let's add basic snapshot logic if we have URLs? 
    # Actually, in batch flow, we lost the 1:1 mapping if we don't store URL in storyboard.
    # But Storyboard doesn't have URL field in current model? 
    # Actually `Batch Editor` didn't save URL into Storyboard model.
    # We might need to rely on the user provided assets or skip the "Website Snapshot" feature if not critical,
    # OR we assume the "Asset Scraper" fetched relevant images.
    # The user request mentioned "snapshot layout", so we should ensure we have a snapshot.
    # Let's check if we can reuse the first image as snapshot if no specific snapshot exists.
    
    snapshot_dir = "output/snapshot"
    os.makedirs(snapshot_dir, exist_ok=True)

    updated_storyboards = []

    for video_idx_0, storyboard in enumerate(storyboards):
        video_id = video_idx_0 + 1
        print(f"  - Reporter: Processing Video {video_id} ('{storyboard.title}')...")
        
        updated_scenes = []
        for scene in storyboard.scenes:
            text = scene.subtitle_text
            
            # Skip if audio already exists
            if scene.audio_path and os.path.exists(scene.audio_path):
                updated_scenes.append(scene)
                continue
                
            print(f"    - Scene {scene.id} TTS...")
            
            request_json = {
                "app": {"appid": APPID, "token": "access_token", "cluster": CLUSTER},
                "user": {"uid": "news_generator_user"},
                "audio": {
                    "voice_type": VOICE_TYPE,
                    "encoding": "mp3",
                    "speed_ratio": 1.15,
                    "volume_ratio": 1.0,
                    "pitch_ratio": 1.0,
                },
                "request": {
                    "reqid": str(uuid.uuid4()),
                    "text": text,
                    "text_type": "plain",
                    "operation": "query",
                    "with_timestamp": 0 
                },
            }

            try:
                resp = requests.post(api_url, json=request_json, headers=header)
                if resp.status_code == 200:
                    resp_data = resp.json()
                    if "data" in resp_data:
                        audio_data = base64.b64decode(resp_data["data"])
                        # Unique filename: scene_{vid}_{sid}.mp3
                        audio_path = f"{output_dir}/scene_{video_id}_{scene.id}.mp3"
                        
                        with open(audio_path, "wb") as f:
                            f.write(audio_data)
                        
                        scene.audio_path = os.path.abspath(audio_path)
                        scene.duration = get_audio_duration_mutagen(audio_path)
                        print(f"      -> Saved Audio ({scene.duration:.2f}s)")
                    else:
                        print(f"      -> No data in response")
                else:
                    print(f"      -> API Error {resp.status_code}")
            except Exception as e:
                print(f"      -> Error: {e}")
            
            updated_scenes.append(scene)
        
        storyboard.scenes = updated_scenes
        
        # Snapshot Placeholder Generation (if missing)
        # We need a snapshot for the 30% layout.
        # Let's duplicate the first scene's image as the snapshot if not present.
        snapshot_path = os.path.join(snapshot_dir, f"snapshot_{video_id}.png")
        if not os.path.exists(snapshot_path):
            # Try finding first valid image in scenes
            first_img = next((s.final_asset_path for s in storyboard.scenes if s.final_asset_path), None)
            if first_img and os.path.exists(first_img):
                import shutil
                shutil.copy(first_img, snapshot_path)
                print(f"    -> Created Snapshot from Scene 1 asset")
            else:
                print(f"    -> Warning: No asset found to create snapshot.")
        
        updated_storyboards.append(storyboard)

    print("Batch Reporter: Finished.")
    return {"ready_to_render_storyboards": updated_storyboards}
