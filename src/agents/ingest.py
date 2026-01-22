import os
import glob
import subprocess
from src.state import AgentState, Storyboard

def get_media_duration(file_path):
    # Try using ffprobe to get duration for video/audio
    try:
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except:
        return 0.0

def human_asset_ingest_node(state: AgentState):
    """
    Scans 'output/assets_final' for files matching 'scene_{id}.*' convention.
    Updates the storyboard with final_asset_path.
    """
    print("Human Ingest: Scanning for user-provided assets...")
    storyboard = state.get("storyboard")
    if not storyboard:
        print("Human Ingest: No storyboard found.")
        return {}
        
    assets_dir = "output/assets_final"
    os.makedirs(assets_dir, exist_ok=True)
    
    # 1. Show instructions if empty (though this runs after interrupt, so user should have done it)
    files = os.listdir(assets_dir)
    print(f"Human Ingest: Found {len(files)} files in {assets_dir}.")
    
    updated_scenes = []
    
    for scene in storyboard.scenes:
        # Check for matching file
        # Rules: scene_{id}.jpg, scene_{id}.png, scene_{id}.mp4, scene_0{id}.jpg etc.
        # Let's simple-match 'scene_{id}.' or 'scene_{pad_id}.'
        
        candidates = []
        pattern = f"scene_{scene.id}.*"
        candidates.extend(glob.glob(os.path.join(assets_dir, pattern)))
        # Try padded 01
        pattern_padded = f"scene_{scene.id:02d}.*"
        candidates.extend(glob.glob(os.path.join(assets_dir, pattern_padded)))
        
        # Unique
        candidates = list(set(candidates))
        
        if candidates:
            # Pick first
            asset_path = candidates[0]
            print(f"Human Ingest: Matched Scene {scene.id} to {asset_path}")
            scene.final_asset_path = asset_path
            # scene.image_path removed from model
            
            # Check if video
            if asset_path.lower().endswith(('.mp4', '.mov', '.webm')):
                dur = get_media_duration(asset_path)
                if dur > 0:
                    scene.duration = dur 
            
        else:
             print(f"Human Ingest: No user asset found for Scene {scene.id}.")
             # Fallback logic removed as image_path is gone from model
             # Use placeholder if explicit fallback needed in renderer, 
             # or we can check logic later. For now, leave empty.
        
        updated_scenes.append(scene)
        
    storyboard.scenes = updated_scenes
    return {"storyboard": storyboard}
