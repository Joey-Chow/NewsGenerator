import json
import os
import asyncio
import glob
from src.state import Storyboard, Scene
from src.agents.renderer import video_renderer_node

async def main():
    print("--- 1. Locating Assets ---")
    
    # 1. Load Storyboard
    json_path = "output/storyboard/storyboard_b9d994f5.json"
    if not os.path.exists(json_path):
        # Fallback to finding newest
        jsons = glob.glob("output/storyboard/*.json")
        if jsons:
            json_path = sorted(jsons, key=os.path.getmtime)[-1]
            print(f"File b9d994f5 not found. Using newest storyboard: {json_path}")
        else:
            print("Error: No storyboard JSON found in output/storyboard/")
            return

    print(f"Loading storyboard from: {json_path}")
    with open(json_path, "r") as f:
        data = json.load(f)
    
    # Handle both raw list and dict wrapper
    if isinstance(data, list):
         storyboard = Storyboard(scenes=data, title="Unknown Title", background_music_mood="unknown")
    else:
         storyboard = Storyboard(**data)
         
    print(f"Loaded {len(storyboard.scenes)} scenes.")

    # 2. Map Assets (Audio and Visual)
    print("\n--- 2. Mapping Local Assets ---")
    for scene in storyboard.scenes:
        # Audio: output/audio/scene_{id}_*.mp3
        # Match roughly by ID
        audio_pattern = f"output/audio/scene_{scene.id}_*.mp3"
        audios = glob.glob(audio_pattern)
        if audios:
            scene.audio_path = os.path.abspath(audios[0])
            # Default fallback
            scene.duration = 5.0
            try:
                from mutagen import File
                audio_info = File(scene.audio_path)
                if audio_info is not None and audio_info.info:
                    scene.duration = float(audio_info.info.length)
            except Exception as e:
                print(f"Warning: Failed to get duration for {scene.audio_path}: {e}")
            
            print(f"Scene {scene.id}: Audio -> {os.path.basename(scene.audio_path)} ({scene.duration:.2f}s)")
        else:
            print(f"Scene {scene.id}: No audio found.")

        # Visual: output/assets_final/scene_{id}.*
        visual_pattern = f"output/assets_final/scene_{scene.id}.*"
        visuals = glob.glob(visual_pattern)
        if visuals:
            scene.final_asset_path = os.path.abspath(visuals[0])
            print(f"Scene {scene.id}: Visual -> {os.path.basename(scene.final_asset_path)}")
        else:
            # Fallback for testing: use raw assets or just placeholder
            # Try raw assets
            raw_pattern = f"output/assets_raw/image_{scene.id}_*.jpg" # Just a guess on naming
            # Or just warn
            print(f"Scene {scene.id}: No visual asset found in output/assets_final.")

    # 3. Invoke Renderer
    state = {
        "storyboard": storyboard,
        "script_draft": "Test Run",
        "audio_path": "",
        "screenshot_paths": []
    }
    
    print("\n--- 3. Invoking Video Renderer ---")
    print("Note: This uses src/agents/renderer.py which calls Remotion.")
    print("Check output/clip/ for the result.")
    
    result = await video_renderer_node(state)
    print("\nRenderer Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
