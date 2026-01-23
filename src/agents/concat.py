import os
import subprocess
from src.state import AgentState

def concat_node(state: AgentState):
    """
    Stitches the generated video segments into a final video.
    Uses a simple FFmpeg concat demuxer.
    """
    print("--- Concat Node ---")
    
    segments = state.get("generated_segments", [])
    
    if not segments:
        print("Concat: No segments to stitch.")
        return {}

    # Define output path
    output_dir = "output/final_broadcasts"
    os.makedirs(output_dir, exist_ok=True)
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"broadcast_{timestamp}.mp4")
    
    # Create FFmpeg concat file
    # file '/path/to/file1.mp4'
    # file '/path/to/file2.mp4'
    
    concat_list_path = os.path.abspath("concat_list.txt")
    
    valid_segments = []
    print("Concat: Verifying segments...")
    for seg in segments:
        if os.path.exists(seg):
            valid_segments.append(seg)
        else:
            print(f"Concat: Warning - Segment not found: {seg}")
            
    if not valid_segments:
        print("Concat: No valid segments found.")
        return {}
        
    with open(concat_list_path, "w") as f:
        for seg in valid_segments:
            # Escape single quotes in path just in case
            safe_path = seg.replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
            
    print(f"Concat: Created list at {concat_list_path} with {len(valid_segments)} files.")
    
    # Run FFmpeg
    # ffmpeg -f concat -safe 0 -i mylist.txt -c copy output.mp4
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        "-y", # Overwrite
        output_path
    ]
    
    try:
        print(f"Concat: Running FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Concat: FFmpeg finished successfully.")
        
        # Cleanup list
        os.remove(concat_list_path)
        
        return {"final_video_path": output_path}
        
    except subprocess.CalledProcessError as e:
        print(f"Concat: FFmpeg failed: {e}")
        print(f"Stderr: {e.stderr.decode()}")
        return {}
