import os
import subprocess
import asyncio
import edge_tts
import json

async def video_renderer_node(state: dict):
    print("Renderer: Starting generation...")
    script = state.get("script_draft", "")
    screenshots = state.get("screenshot_paths", [])
    
    if not script:
        print("Renderer: No script found.")
        return {}

    # 1. Generate Audio (MP3)
    output_audio_path = f"output/clip/audio_{os.urandom(4).hex()}.mp3"
    os.makedirs("output/clip", exist_ok=True)
    
    # We use a standard English voice for now, or detect Chinese if needed.
    # User asked for Chinese script, so let's use a Chinese voice.
    voice = "zh-CN-YunxiNeural" 
    
    print(f"Renderer: Generating TTS to {output_audio_path}...")
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(output_audio_path)
    
    # 2. Render Video (Remotion)
    print("Renderer: Calling Remotion...")
    output_video_path = f"output/clip/video_{os.urandom(4).hex()}.mp4"
    
    # Prepare Inputs
    # Get absolute paths to be safe for Remotion
    abs_audio = os.path.abspath(output_audio_path)
    abs_screenshot = os.path.abspath(screenshots[0]) if screenshots else "https://via.placeholder.com/1280x720"
    
    props = {
        "audioPath": abs_audio,
        "screenshotPath": abs_screenshot,
        "text": script
    }
    props_json = json.dumps(props)
    
    # Prepare working directory
    cwd = os.path.join(os.getcwd(), "remotion_project")

    # Command to render
    cmd = [
        "npx", "remotion", "render",
        "src/index.tsx", "NewsVideo",
        os.path.abspath(output_video_path),
        "--props", props_json,
        "--gl", "swangle"
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
