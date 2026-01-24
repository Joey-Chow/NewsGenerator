import os
import subprocess
import shutil
import datetime
from src.state import AgentState

def concat_node(state: AgentState):
    """
    Stitches the generated video segments into a final video.
    Uses a simple FFmpeg concat demuxer.
    """
    print("--- Concat Node (Advanced) ---")
    segments = state.get("generated_segments", [])
    if not segments:
        print("Concat: No segments to stitch.")
        return {}

    # Paths
    work_dir = "output/temp_concat"
    os.makedirs(work_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "output/final_broadcasts"
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"broadcast_{timestamp}.mp4")

    # Assets
    intro_src = os.path.abspath("assets/intro.mov")
    outro_src = os.path.abspath("assets/outro.mov")
    bgm_src = os.path.abspath("assets/bgm.wav")

    # --- Helper ---
    def run_ffmpeg(args, desc):
        print(f"Concat: Running {desc}...")
        try:
            subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Concat Error ({desc}): {e}")
            return False

    # --- Step 1: Stitch generated segments (Body) ---
    # Use concat demuxer for speed/reliability on identical formats
    inputs_txt_path = os.path.join(work_dir, "inputs.txt")
    with open(inputs_txt_path, "w") as f:
        for seg in segments:
            # Escape paths for ffmpeg concat file
            path_str = os.path.abspath(seg).replace("'", "'\\''")
            f.write(f"file '{path_str}'\n")
    
    body_raw_path = os.path.join(work_dir, "body_raw.mp4")
    cmd_stitch = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", inputs_txt_path,
        "-c", "copy", "-y", body_raw_path
    ]
    if not run_ffmpeg(cmd_stitch, "Stitch Body"):
        return {}

    # --- Step 2: Add BGM to Body ---
    body_final_path = os.path.join(work_dir, "body_final.mp4")
    
    if os.path.exists(bgm_src):
        # Mix BGM: Loop BGM, Volume 0.2, Stop when video ends
        # Filter: [1:a]volume=0.2,aloop=loop=-1:size=2e+9[bgm];[0:a][bgm]amix=inputs=2:duration=first[a_out]
        # Note: 'aloop' might behave differently on versions. simpler is -stream_loop -1 before input
        cmd_bgm = [
            "ffmpeg",
            "-i", body_raw_path,
            "-stream_loop", "-1", "-i", bgm_src,
            "-filter_complex", "[1:a]volume=0.2[bgm];[0:a][bgm]amix=inputs=2:duration=first[a_out]",
            "-map", "0:v", "-map", "[a_out]",
            "-c:v", "copy", "-c:a", "aac", "-y", body_final_path
        ]
        if not run_ffmpeg(cmd_bgm, "Mix BGM"):
            body_final_path = body_raw_path # Fallback
    else:
        print("Concat: No BGM found. Skipping mix.")
        shutil.copy(body_raw_path, body_final_path)

    # --- Step 3: Prepare Intro/Outro (Standardize) ---
    # We re-encode intro/outro to match the standard Remotion format (720p 30fps) to ensure safe concat
    
    def standardize(input_path, output_name):
        out_path = os.path.join(work_dir, output_name)
        cmd = [
            "ffmpeg", "-i", input_path,
            "-vf", "scale=2560:1440,fps=30,format=yuv420p",
            "-c:v", "libx264", "-c:a", "aac", "-ar", "48000", "-ac", "2",
            "-y", out_path
        ]
        if run_ffmpeg(cmd, f"Standardize {output_name}"):
            return out_path
        return None

    final_segments = []

    # Intro
    if os.path.exists(intro_src):
        p = standardize(intro_src, "intro_std.mp4")
        if p: final_segments.append(p)
    
    # Body
    final_segments.append(body_final_path)
    
    # Outro
    if os.path.exists(outro_src):
        p = standardize(outro_src, "outro_std.mp4")
        if p: final_segments.append(p)

    # --- Step 4: Final Assembly ---
    print(f"Concat: Assembling {len(final_segments)} parts...")
    
    # Using filter_complex concat for robustness
    ffmpeg_cmd = ["ffmpeg"]
    filter_parts = []
    
    for i, inp in enumerate(final_segments):
        ffmpeg_cmd.extend(["-i", inp])
        filter_parts.append(f"[{i}:v][{i}:a]")
        
    filter_str = "".join(filter_parts) + f"concat=n={len(final_segments)}:v=1:a=1[v][a]"
    
    ffmpeg_cmd.extend([
        "-filter_complex", filter_str,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "48000",
        "-y", final_output_path
    ])
    
    if run_ffmpeg(ffmpeg_cmd, "Final Assembly"):
        print(f"Concat: Success! Output: {final_output_path}")
        # Cleanup
        try: shutil.rmtree(work_dir)
        except: pass
        return {"final_video_path": final_output_path}
    else:
        return {}
