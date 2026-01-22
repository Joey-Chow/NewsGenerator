import os
import subprocess
import asyncio
import json
import shutil
import random
import glob
from src.state import Storyboard, Scene

async def video_renderer_node(state: dict):
    print("Renderer: Starting generation...")
    storyboard = state.get("storyboard")
    
    if not storyboard:
        print("Renderer: Missing storyboard.")
        return {}

    # 2. Render Video (Remotion)
    print("Renderer: Calling Remotion...")
    output_video_path = f"output/clip/video_{os.urandom(4).hex()}.mp4"
    
    # Prepare working directory
    cwd = os.path.join(os.getcwd(), "remotion_project")
    public_dir = os.path.join(cwd, "public")
    os.makedirs(public_dir, exist_ok=True)
    
    render_scenes = []
    created_files = [] # Track for cleanup

    print("Renderer: Copying assets to public/...")

    # Process Background Video
    bg_public_name = None
    # Support multiple extensions
    bg_files = []
    for ext in ["mp4", "mov", "webm"]:
         bg_files.extend(glob.glob(f"assets/background/*.{ext}"))
         
    if bg_files:
        bg_source = random.choice(bg_files)
        bg_filename = f"background_{os.urandom(4).hex()}.mp4"
        dest_bg = os.path.join(public_dir, bg_filename)
        shutil.copy(bg_source, dest_bg)
        bg_public_name = bg_filename
        created_files.append(dest_bg)
        print(f"Renderer: Using background video: {os.path.basename(bg_source)}")
    else:
        print("Renderer: No background videos found in assets/background/")

    # Sort scenes by ID just in case
    storyboard.scenes.sort(key=lambda s: s.id)
    
    for scene in storyboard.scenes:
        # Process Visual Asset (Image or Video)
        img_public_name = ""
        # We rely on final_asset_path from human ingest
        asset_path = scene.final_asset_path
        
        if asset_path and os.path.exists(asset_path):
            filename = f"scene_{scene.id}_{os.path.basename(asset_path)}"
            dest_asset = os.path.join(public_dir, filename)
            shutil.copy(asset_path, dest_asset)
            img_public_name = filename
            created_files.append(dest_asset)
        else:
            print(f"Renderer Warning: Missing asset for Scene {scene.id}")

        # Process Audio
        audio_public_name = ""
        if scene.audio_path and os.path.exists(scene.audio_path):
            audio_filename = f"scene_{scene.id}_{os.path.basename(scene.audio_path)}"
            dest_audio = os.path.join(public_dir, audio_filename)
            shutil.copy(scene.audio_path, dest_audio)
            audio_public_name = audio_filename
            created_files.append(dest_audio)
        else:
            print(f"Renderer Warning: Missing audio for Scene {scene.id}")

        render_scenes.append({
            "id": scene.id,
            "text": scene.subtitle_text,
            "image": img_public_name, # Can be video or image
            "audio": audio_public_name,
            "duration": scene.duration
        })

    props = {
        "scenes": render_scenes,
        "title": storyboard.title,
        "musicMood": storyboard.background_music_mood,
        "backgroundVideo": bg_public_name
    }
    props_json = json.dumps(props)

    # Command to render
    cmd = [
        "npx", "remotion", "render",
        "src/index.tsx", "NewsVideo",
        os.path.abspath(output_video_path),
        "--props", props_json,
        "--log", "verbose"
    ]
    
    # Check node_modules
    if not os.path.exists(os.path.join(cwd, "node_modules")):
        subprocess.run(["npm", "install"], cwd=cwd, check=True)
    
    print(f"Renderer: Executing Remotion render to {output_video_path}...")
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        print(f"Renderer: Video saved to {output_video_path}")
        return {"video_path": output_video_path}
    except subprocess.CalledProcessError as e:
        print(f"Renderer Error: {e}")
        return {"error": str(e)}
    finally:
        # Cleanup
        print("Renderer: Cleaning up public assets...")
        for f in created_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
