import asyncio
import os
from src.agents.renderer import video_renderer_node

# Mock State for testing
mock_state = {
    "script_draft": "这是一段测试音频。我们正在验证视频渲染器是否能够正常工作。如果成功，您应该能看到视频生成。",
    "screenshot_paths": ["output/screenshot/screenshot_972b4e0e.png"], # Use a recent screenshot if available
    "audio_path": "output/audio/test_audio.mp3" # Synthetic path, we might need to verify if reporter needs to run or we mock audio
}

async def test_renderer():
    print("🧪 Testing Video Renderer Node...")
    
    # Check if we need to generate audio first? 
    # Since we separated reporter, renderer EXPECTS audio_path to exist.
    # So we should probably either mock a file or run reporter first.
    # Let's run reporter first to be safe, or just mock a file if one exists.
    
    # For this test, let's reuse a previous audio file if it exists, or generate one quickly.
    # Actually, simpler to just run reporter then renderer to test that flow without LLM.
    
    from src.agents.reporter import reporter_node
    
    print("1. Running Reporter (TTS)...")
    reporter_out = await reporter_node(mock_state)
    print(f"Reporter Output: {reporter_out}")
    
    # Update state with reporter output
    mock_state.update(reporter_out)
    
    print("2. Running Renderer (Remotion)...")
    # Make sure we have a valid screenshot path, else create a placeholder
    if not os.path.exists(mock_state["screenshot_paths"][0]):
        print("Warning: Screenshot not found, using placeholder logic in renderer.")
        # But renderer might fail if we don't have a real file to copy.
        # Let's create a dummy file if needed.
        os.makedirs("output/screenshot", exist_ok=True)
        with open(mock_state["screenshot_paths"][0], "w") as f:
            f.write("dummy image") # This won't render well in video but avoids crash on copy
            
    result = await video_renderer_node(mock_state)
    print(f"✅ Renderer Output: {result}")

if __name__ == "__main__":
    asyncio.run(test_renderer())
