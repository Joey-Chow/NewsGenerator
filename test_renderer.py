import asyncio
import os
import sys

# Ensure src is in pythonpath
sys.path.append(os.getcwd())

from src.agents.renderer import video_renderer_node

async def main():
    # Assets provided by user
    script_file = "output/script/script_0dcc05f5.txt"
    screenshot_file = "output/screenshot/screenshot_9e7f8519.png"
    audio_file = "output/audio/audio_effa76bd.mp3"
    
    # Derive captions path (assuming standard naming convention)
    # output/audio/captions_{file_id}.json
    # parsing audio filename to get ID
    audio_basename = os.path.basename(audio_file) # audio_effa76bd.mp3
    file_id = audio_basename.replace("audio_", "").replace(".mp3", "")
    captions_file = f"output/audio/captions_{file_id}.json"
    
    if not os.path.exists(captions_file):
        print(f"Warning: Captions file {captions_file} not found. Video will be rendered without captions.")
        captions_file = None
    else:
        print(f"Found captions file: {captions_file}")

    # Read Script (Support JSON or TXT)
    script_sentences = []
    
    # Check for JSON version first or if filename is .json
    if script_file.endswith(".json"):
        if os.path.exists(script_file):
             import json
             with open(script_file, "r", encoding="utf-8") as f:
                 data = json.load(f)
                 script_sentences = data.get("sentences", [])
                 script_content = "。".join(script_sentences) + "。"
        else:
             print(f"Error: Script JSON {script_file} not found.")
             return
    elif os.path.exists(script_file):
         # TXT Fallback
         with open(script_file, "r", encoding="utf-8") as f:
             script_content = f.read()
         # Mock sentences for testing old txt files
         import re
         # Split by punctuation
         raw = re.split(r'([。！？!?\n])', script_content)
         for i in range(0, len(raw), 2):
             s = raw[i].strip()
             if s:
                 script_sentences.append(s)
    else:
        print(f"Error: Script file {script_file} not found.")
        return

    # Mock State
    state = {
        "script_draft": script_content,
        "screenshot_paths": [screenshot_file],
        "audio_path": audio_file,
        "captions_path": captions_file,
        "sentences": script_sentences
    }

    print("--- Starting Renderer Test ---")
    print(f"Script: {script_file}")
    print(f"Screenshot: {screenshot_file}")
    print(f"Audio: {audio_file}")
    print(f"Captions: {captions_file}")
    
    result = await video_renderer_node(state)
    
    print("--- Test Complete ---")
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
