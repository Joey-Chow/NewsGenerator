import os
import subprocess
import asyncio
import json
import shutil
import random
import glob
from src.state import Storyboard, Scene

async def batch_video_renderer_node(state: dict):
    def sync_renderer():
        print("Renderer: Starting batch generation...")
        storyboards = state.get("ready_to_render_storyboards", [])
        if not storyboards:
            storyboards = state.get("draft_storyboards", [])
            if not storyboards:
                return {}
            
        generated_segments = []
        for idx, storyboard in enumerate(storyboards):
            output_video_path = f"output/clip/video_{idx+1}.mp4"
            cwd = os.path.join(os.getcwd(), "remotion_project")
            public_dir = os.path.join(cwd, "public")
            os.makedirs(public_dir, exist_ok=True)
            
            render_scenes = []
            created_files = []
            bg_source = os.path.join(os.getcwd(), "assets", "bg.mp4")
            if not os.path.exists(bg_source):
                bg_files = []
                for ext in ["mp4", "mov", "webm"]:
                    bg_files.extend(glob.glob(f"assets/background/*.{ext}"))
                bg_source = random.choice(bg_files) if bg_files else None

            bg_public_name = None
            if bg_source and os.path.exists(bg_source):
                bg_filename = f"background_{os.urandom(4).hex()}.mp4"
                dest_bg = os.path.join(public_dir, bg_filename)
                shutil.copy(bg_source, dest_bg)
                bg_public_name = bg_filename
                created_files.append(dest_bg)

            # Copy standard assets
            for asset_name in ["logo2.png", "swoosh.mp3"]:
                src = os.path.join(os.getcwd(), "assets", asset_name)
                if os.path.exists(src):
                    dest = os.path.join(public_dir, asset_name)
                    shutil.copy(src, dest)
                    created_files.append(dest)

            # Snapshot
            snapshot_source = os.path.join("output", "snapshot", f"snapshot_{idx+1}.png")
            snapshot_public_name = ""
            if os.path.exists(snapshot_source):
                snapshot_filename = f"snapshot_{idx+1}.png"
                dest_snapshot = os.path.join(public_dir, snapshot_filename)
                shutil.copy(snapshot_source, dest_snapshot)
                snapshot_public_name = snapshot_filename
                created_files.append(dest_snapshot)

            for scene in storyboard.scenes:
                img_name, aud_name = "", ""
                if scene.final_asset_path and os.path.exists(scene.final_asset_path):
                    img_name = f"scene_{scene.id}_{os.path.basename(scene.final_asset_path)}"
                    dest = os.path.join(public_dir, img_name)
                    shutil.copy(scene.final_asset_path, dest)
                    created_files.append(dest)
                if scene.audio_path and os.path.exists(scene.audio_path):
                    aud_name = f"scene_{scene.id}_{os.path.basename(scene.audio_path)}"
                    dest = os.path.join(public_dir, aud_name)
                    shutil.copy(scene.audio_path, dest)
                    created_files.append(dest)
                render_scenes.append({"id": scene.id, "text": scene.subtitle_text, "image": img_name, "audio": aud_name, "duration": scene.duration})

            props = json.dumps({"scenes": render_scenes, "title": storyboard.title, "backgroundVideo": bg_public_name})
            cmd = ["npx", "remotion", "render", "src/index.tsx", "NewsVideo", os.path.abspath(output_video_path), "--props", props, "--log", "info"]
            
            if not os.path.exists(os.path.join(cwd, "node_modules")):
                subprocess.run(["npm", "install"], cwd=cwd, check=True)
            
            try:
                subprocess.run(cmd, cwd=cwd, check=True)
                generated_segments.append(output_video_path)
            except Exception as e:
                print(f"Render Error: {e}")
            finally:
                for f in created_files:
                    if os.path.exists(f): os.remove(f)
        return {"generated_segments": generated_segments}

    return await asyncio.to_thread(sync_renderer)
