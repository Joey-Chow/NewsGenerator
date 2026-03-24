import os
import sys
import subprocess

# Ensure absolute imports work smoothly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.youtuber import youtuber_node
from src.state import Storyboard, Scene

def create_mock_video(path):
    print(f"Generating a 1-second mock video for testing at {path}...")
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=1", 
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    os.makedirs("output", exist_ok=True)
    test_video_path = os.path.abspath("output/test_youtube_upload.mp4")
    
    # Create the fake video if we don't have one
    if not os.path.exists(test_video_path):
        create_mock_video(test_video_path)
        
    # Mock data to simulate the preceding nodes
    scene = Scene(id=1, subtitle_text="This is an automated YouTube API testing video to ensure credentials are correct.", duration=5.0)
    sb = Storyboard(title="Automated YouTube API Integration Test", scenes=[scene])
    
    mock_state = {
        "ready_to_render_storyboards": [sb],
        "final_video_path": test_video_path
    }
    
    print("\n=== Triggering Youtuber Node ===")
    res = youtuber_node(mock_state)
    
    print("\n=== Result ===")
    print(res)

if __name__ == "__main__":
    main()
