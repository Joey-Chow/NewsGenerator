import os
import json
import base64
import uuid
import requests
import asyncio
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
    Iterates through 'ready_to_render_storyboards'
    Generates TTS audio for ALL scenes in ALL storyboards.
    """
    def sync_reporter():
        print("Reporter: Generating Audio for batch...")
        
        storyboards = state.get("ready_to_render_storyboards", [])
        if not storyboards:
            storyboards = state.get("draft_storyboards", [])
            if not storyboards:
                print("Reporter: No storyboards ready.")
                return {"reporter_storyboards": []}

        # Load credentials
        AZURE_KEY = os.getenv("AZURE_TTS_KEY")
        AZURE_REGION = os.getenv("AZURE_TTS_REGION")
        AZURE_VOICE = os.getenv("AZURE_TTS_VOICE", "en-US-AndrewMultilingualNeural")

        if not AZURE_KEY or not AZURE_REGION:
            print("Reporter Error: Missing AZURE_TTS_KEY or AZURE_TTS_REGION.")
            return {"reporter_storyboards": storyboards}

        api_url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
            "User-Agent": "NewsGenerator"
        }

        output_dir = "output/audio"
        os.makedirs(output_dir, exist_ok=True)
        
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
                
                # Escape XML special characters in text
                xml_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&apos;")
                
                ssml = f"""<speak version='1.0' xml:lang='en-US'>
                    <voice xml:lang='en-US' xml:gender='Male' name='{AZURE_VOICE}'>
                        {xml_text}
                    </voice>
                </speak>"""

                try:
                    resp = requests.post(api_url, data=ssml.encode('utf-8'), headers=headers)
                    if resp.status_code == 200:
                        audio_data = resp.content
                        audio_path = os.path.join(output_dir, f"scene_{video_id}_{scene.id}.mp3")
                        
                        with open(audio_path, "wb") as f:
                            f.write(audio_data)
                        
                        scene.audio_path = os.path.abspath(audio_path)
                        scene.duration = get_audio_duration_mutagen(audio_path)
                        print(f"      -> Saved Audio ({scene.duration:.2f}s)")
                    else:
                        print(f"      -> API Error {resp.status_code}")
                except Exception as e:
                    print(f"      -> Error: {e}")
                
                updated_scenes.append(scene)
            
            updated_storyboards.append(storyboard)

        print("Reporter: Finished.")
        return {"reporter_storyboards": updated_storyboards}

    # Run the blocking logic in a thread
    return await asyncio.to_thread(sync_reporter)
