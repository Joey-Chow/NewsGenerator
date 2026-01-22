import os
import json
import base64
import uuid
import requests
import subprocess
from src.state import Storyboard, Scene

from mutagen import File

def get_audio_duration_mutagen(file_path):
    """Get duration of audio file using mutagen."""
    try:
        audio = File(file_path)
        if audio is not None and audio.info:
            return float(audio.info.length)
        return 0.0
    except Exception as e:
        print(f"Reporter Warning: Could not get duration for {file_path}: {e}")
        return 0.0

async def reporter_node(state: dict):
    print("Reporter: Generating Audio (Per Scene) using Volcano Engine...")
    storyboard = state.get("storyboard")
    
    if not storyboard:
        print("Reporter: No storyboard found.")
        return {}

    # Load credentials
    APPID = os.getenv("VOLC_APPID")
    TOKEN = os.getenv("VOLC_ACCESS_TOKEN")
    VOICE_TYPE = os.getenv("VOLC_VOICE_TYPE", "BV001_streaming") 
    CLUSTER = "volcano_tts"

    if not APPID or not TOKEN:
        print("Reporter: Error - Missing VOLC_APPID or VOLC_ACCESS_TOKEN.")
        return {}

    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    header = {"Authorization": f"Bearer;{TOKEN}"}

    output_dir = "output/audio"
    os.makedirs(output_dir, exist_ok=True)

    updated_scenes = []

    for scene in storyboard.scenes:
        text = scene.subtitle_text
        print(f"Reporter: Processing Scene {scene.id} - '{text[:20]}...'")
        
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
            if resp.status_code != 200:
                print(f"Reporter: API Error {resp.status_code} - {resp.text}")
                continue

            resp_data = resp.json()
            if "data" in resp_data:
                audio_data = base64.b64decode(resp_data["data"])
                file_id = os.urandom(4).hex()
                audio_path = f"{output_dir}/scene_{scene.id}_{file_id}.mp3"
                
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                
                scene.audio_path = audio_path
                
                # Get Duration
                duration = get_audio_duration_mutagen(audio_path)
                scene.duration = duration
                
                print(f"Reporter: Saved {audio_path} (Duration: {duration:.2f}s)")
            else:
                 print(f"Reporter: No data in response: {resp_data}")

        except Exception as e:
            print(f"Reporter: Error generating audio for scene {scene.id}: {e}")

        updated_scenes.append(scene)

    storyboard.scenes = updated_scenes
    # Return updated storyboard directly (Sequential Flow)
    return {"storyboard": storyboard}
