import os
import subprocess
import asyncio
import json
import shutil
import random
import glob
from src.state import Storyboard, Scene

async def batch_video_renderer_node(state: dict):
    print("Batch Renderer: Starting batch generation...")
    storyboards = state.get("ready_to_render_storyboards", [])
    
    if not storyboards:
        print("Batch Renderer: No storyboards ready to render.")
        return {}
        
    generated_segments = []
    
    # Iterate through all accumulated storyboards
    for idx, storyboard in enumerate(storyboards):
        print(f"\nBatch Renderer: Processing Storyboard {idx+1}/{len(storyboards)} - Title: {storyboard.title}")
        
        # -------------------------------------------------------------
        # Existing Rendering Logic (Adapted for Loop)
        # -------------------------------------------------------------
        
        # 2. Render Video (Remotion)
        output_video_path = f"output/clip/video_{idx+1}.mp4"
        
        # Prepare working directory
        cwd = os.path.join(os.getcwd(), "remotion_project")
        public_dir = os.path.join(cwd, "public")
        os.makedirs(public_dir, exist_ok=True)
        
        render_scenes = []
        created_files = [] # Track for cleanup
    
        print(f"Batch Renderer ({idx+1}): Copying assets...")
    
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
        else:
            print("Batch Renderer: No background videos found in assets/background/")
    
        # Sort scenes by ID just in case
        storyboard.scenes.sort(key=lambda s: s.id)

        # Copy logo
        logo_source = os.path.join(os.getcwd(), "assets", "logo2.png")
        if os.path.exists(logo_source):
             dest_logo = os.path.join(public_dir, "logo2.png")
             shutil.copy(logo_source, dest_logo)
             created_files.append(dest_logo)
        else:
             print("Batch Renderer Warning: assets/logo2.png not found.")

        # Copy swoosh sound effect
        swoosh_source = os.path.join(os.getcwd(), "assets", "swoosh.MP3")
        if os.path.exists(swoosh_source):
             dest_swoosh = os.path.join(public_dir, "swoosh.mp3")
             shutil.copy(swoosh_source, dest_swoosh)
             created_files.append(dest_swoosh)
        else:
             print("Batch Renderer Warning: assets/swoosh.MP3 not found.")
        
        # ------------------------------------------------------------------
        # Snapshot Logic (Persistent per Storyboard/Video)
        # ------------------------------------------------------------------
        snapshot_public_name = ""
        # Assume snapshot naming matches video index (1-based)
        # Try both `snapshot_1.png` and maybe `snapshot_idx.png` variants if needed
        snapshot_source = os.path.join("output", "snapshot", f"snapshot_{idx+1}.png")
        
        if os.path.exists(snapshot_source):
             print(f"Batch Renderer ({idx+1}): Found persistent snapshot {snapshot_source}")
             snapshot_filename = f"snapshot_{idx+1}.png"
             dest_snapshot = os.path.join(public_dir, snapshot_filename)
             shutil.copy(snapshot_source, dest_snapshot)
             snapshot_public_name = snapshot_filename
             created_files.append(dest_snapshot)
        else:
             print(f"Batch Renderer ({idx+1}): No persistent snapshot found (checked {snapshot_source}).")

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
                print(f"Batch Renderer Warning: Missing asset for Scene {scene.id}")
    
            # Process Audio
            audio_public_name = ""
            if scene.audio_path and os.path.exists(scene.audio_path):
                audio_filename = f"scene_{scene.id}_{os.path.basename(scene.audio_path)}"
                dest_audio = os.path.join(public_dir, audio_filename)
                shutil.copy(scene.audio_path, dest_audio)
                audio_public_name = audio_filename
                created_files.append(dest_audio)
            else:
                print(f"Batch Renderer Warning: Missing audio for Scene {scene.id}")
    
            # NOTE: Per-scene snapshot check removed in favor of persistent storyboard snapshot above.

            render_scenes.append({
                "id": scene.id,
                "text": scene.subtitle_text,
                "image": img_public_name, # Can be video or image
                "audio": audio_public_name,
                "duration": scene.duration,
                "snapshot": snapshot_public_name # Pass persistent snapshot to every scene
            })
    
        props = {
            "scenes": render_scenes,
            "title": storyboard.title,
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
        
        print(f"Batch Renderer ({idx+1}): Executing Remotion render...")
        try:
            subprocess.run(cmd, cwd=cwd, check=True)
            print(f"Batch Renderer ({idx+1}): Video saved to {output_video_path}")
            generated_segments.append(output_video_path)
        except subprocess.CalledProcessError as e:
            print(f"Batch Renderer Error ({idx+1}): {e}")
        finally:
            # Cleanup
            print(f"Batch Renderer ({idx+1}): Cleaning up public assets...")
            for f in created_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
                        
    # End Loop
    
    print(f"Batch Renderer: Finished. Generated {len(generated_segments)} videos.")
    return {
        "generated_segments": generated_segments, 
        "video_path": None, # Clear legacy field
    }
