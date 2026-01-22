import os
import subprocess
import asyncio
import json

async def video_renderer_node(state: dict):
    print("Renderer: Starting generation...")
    script = state.get("script_draft", "")
    screenshots = state.get("screenshot_paths", [])
    output_audio_path = state.get("audio_path", "")
    
    if not script or not output_audio_path:
        print("Renderer: Missing script or audio.")
        return {}

    # 2. Render Video (Remotion)
    print("Renderer: Calling Remotion...")
    output_video_path = f"output/clip/video_{os.urandom(4).hex()}.mp4"
    
    # Prepare working directory
    cwd = os.path.join(os.getcwd(), "remotion_project")
    public_dir = os.path.join(cwd, "public")
    os.makedirs(public_dir, exist_ok=True)
    
    # Copy assets to public/ to avoid local file permission issues in Remotion
    import shutil
    
    # Audio
    audio_filename = os.path.basename(output_audio_path)
    if not os.path.exists(output_audio_path):
         print(f"Renderer Error: Audio file missing at {output_audio_path}")
         return {}
    
    dest_audio = os.path.join(public_dir, audio_filename)
    print(f"Renderer: Copying audio from {output_audio_path} to {dest_audio}")
    shutil.copy(output_audio_path, dest_audio)

    # Captions
    captions_path = state.get("captions_path")
    captions_filename = ""
    dest_captions = ""
    if captions_path and os.path.exists(captions_path):
        captions_filename = os.path.basename(captions_path)
        dest_captions = os.path.join(public_dir, captions_filename)
        print(f"Renderer: Copying captions from {captions_path} to {dest_captions}")
        shutil.copy(captions_path, dest_captions)
    
    # Screenshot
    screenshot_path = screenshots[0] if screenshots else "placeholder.png"
    screenshot_filename = os.path.basename(screenshot_path)
    if screenshots and os.path.exists(screenshot_path):
        dest_ss = os.path.join(public_dir, screenshot_filename)
        print(f"Renderer: Copying screenshot from {screenshot_path} to {dest_ss}")
        shutil.copy(screenshot_path, dest_ss)
    else:
        print(f"Renderer Warning: Screenshot missing at {screenshot_path}")

    print(f"Renderer: Contents of {public_dir}: {os.listdir(public_dir)}")
    
    args_audio_path = audio_filename 
    args_screenshot_path = screenshot_filename

    props = {
        "audioPath": args_audio_path,
        "screenshotPath": args_screenshot_path,
        "text": script,
        "captionsPath": captions_filename,
        "sentences": state.get("sentences", [])
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
    
    # Check if node_modules exists, if not install. 
    # Also check if @remotion/cli is installed by looking for the binary or just rely on npx to pull if needed (but faster to install)
    # Simple check: if node_modules missing OR forced update needed due to missing binary previously
    if not os.path.exists(os.path.join(cwd, "node_modules")):
        print("Renderer: Installing Remotion dependencies (first run)...")
        subprocess.run(["npm", "install"], cwd=cwd, check=True)
    
    # Run npm install if we suspect missing deps (e.g. cli)
    # For now, let's assume the previous run didn't have cli, so we run install again to pick up the new package.json change
    # We can detect if package.json changed? Or just run it. It's fast if up to date.
    subprocess.run(["npm", "install"], cwd=cwd, check=True)
    
    print(f"Renderer: Executing Remotion render to {output_video_path}...")
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        print(f"Renderer: Video saved to {output_video_path}")
        return {"video_path": output_video_path, "audio_path": output_audio_path}
    except subprocess.CalledProcessError as e:
        print(f"Renderer Error: {e}")
        return {"error": str(e)}
    finally:
        # Cleanup copied assets in public/
        print("Renderer: Cleaning up public assets...")
        try:
            if os.path.exists(dest_audio):
                os.remove(dest_audio)
            # Check if dest_ss was defined (it's inside an if block in original code)
            # We recreate the path to be safe or verify existence
            cleanup_ss = os.path.join(public_dir, screenshot_filename)
            if os.path.exists(cleanup_ss) and screenshot_filename != "placeholder.png":
                os.remove(cleanup_ss)
        except Exception as cleanup_err:
             print(f"Renderer Warning: Cleanup failed: {cleanup_err}")
