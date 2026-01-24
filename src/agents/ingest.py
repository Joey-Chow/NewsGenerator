import os
import glob
import subprocess
from src.state import AgentState

def get_media_duration(file_path):
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

import json
from src.state import Storyboard

def batch_human_script_review_node(state: AgentState):
    """
    Breakpoint Node.
    Allows user to manually edit the storyboard JSON files in 'output/storyboard/'.
    Reloads them back into state before proceeding to Asset Scraper.
    """
    print("Batch Script Review: Reloading storyboards from disk...")
    
    drafts = state.get("draft_storyboards", [])
    if not drafts:
        print("Batch Script Review: No drafts in state. Checking disk anyway...")
        
    storyboard_dir = "output/storyboard"
    if not os.path.exists(storyboard_dir):
        print("Batch Script Review: output/storyboard directory missing.")
        return {"draft_storyboards": []}
        
    reloaded_storyboards = []
    
    # We rely on the order or filename indices. 
    # Let's try to match existing drafts or just reload all found json files.
    # Reloading ALL found is safer if user added/removed some.
    
    json_files = glob.glob(os.path.join(storyboard_dir, "storyboard_*.json"))
    # Sort by number in filename to maintain order
    # scene_X.json -> extract X
    def extract_id(f):
        try:
            return int(os.path.splitext(os.path.basename(f))[0].split('_')[1])
        except:
            return 999
            
    json_files.sort(key=extract_id)
    
    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                sb = Storyboard(**data)
                reloaded_storyboards.append(sb)
                print(f"  - Reloaded {os.path.basename(fpath)}: {sb.title}")
        except Exception as e:
            print(f"  - Error reloading {fpath}: {e}")
            
    print(f"Batch Script Review: {len(reloaded_storyboards)} storyboards loaded.")
    return {"draft_storyboards": reloaded_storyboards}

def batch_human_asset_ingest_node(state: AgentState):
    """
    Breakpoint node. 
    1. Scans 'output/assets_final' for files matching 'scene_{vid}_{sid}.*'
    2. Updates ALL 'draft_storyboards' with final_asset_path.
    3. Promotes them to 'ready_to_render_storyboards'.
    """
    print("Batch Human Ingest: Scanning for verified assets...")
    
    drafts = state.get("draft_storyboards", [])
    if not drafts:
        print("Batch Human Ingest: No draft storyboards found.")
        return {"ready_to_render_storyboards": []}
        
    assets_dir = "output/assets_final"
    os.makedirs(assets_dir, exist_ok=True)
    
    # Optional: Logic to find matching snapshot per video?
    # Snapshots are handled by reporter or renderer traditionally, but let's assume they exist.
    
    finalized_storyboards = []
    
    for video_idx_0, storyboard in enumerate(drafts):
        video_id = video_idx_0 + 1
        print(f"  - Ingesting Video {video_id} ('{storyboard.title}')...")
        
        updated_scenes = []
        for scene in storyboard.scenes:
            # Pattern: scene_{vid}_{sid}.*
            # e.g. scene_1_1.jpg
            
            candidates = []
            pattern = f"scene_{video_id}_{scene.id}.*"
            candidates.extend(glob.glob(os.path.join(assets_dir, pattern)))
            
            # Legacy/Fallback pattern if needed? (scene_{sid}.*) -> Avoid to prevent collision
            
            if candidates:
                asset_path = candidates[0] # Pick first match
                scene.final_asset_path = os.path.abspath(asset_path)
                print(f"    -> Matched Scene {scene.id} to {os.path.basename(asset_path)}")
                
                # Update duration if video
                if asset_path.lower().endswith(('.mp4', '.mov', '.webm')):
                    d = get_media_duration(asset_path)
                    if d > 0:
                        scene.duration = d
            else:
                print(f"    -> WARNING: No asset found for Scene {scene.id} (Expected {pattern})")
                
            updated_scenes.append(scene)
        
        storyboard.scenes = updated_scenes
        storyboard.is_approved = True # Auto-approve after this step? Or user manual check implied.
        finalized_storyboards.append(storyboard)
        
    print(f"Batch Human Ingest: Ready to render {len(finalized_storyboards)} videos.")
    return {
        "ready_to_render_storyboards": finalized_storyboards,
        # Clear drafts to save space? Optional.
    }
