import os
import glob
import subprocess
import json
import asyncio
from src.state import AgentState, Storyboard

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

async def batch_human_script_review_node(state: AgentState):
    """
    Breakpoint Node.
    Allows user to manually edit the storyboard JSON files in 'output/storyboard/'.
    """
    def sync_review():
        print("Script Review: Reloading storyboards from disk...")
        storyboard_dir = "output/storyboard"
        if not os.path.exists(storyboard_dir):
            return {"draft_storyboards": state.get("draft_storyboards", [])}
            
        reloaded_storyboards = []
        json_files = glob.glob(os.path.join(storyboard_dir, "storyboard_*.json"))
        
        def extract_id(f):
            try: return int(os.path.splitext(os.path.basename(f))[0].split('_')[1])
            except: return 999
                
        json_files.sort(key=extract_id)
        
        for fpath in json_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sb = Storyboard(**data)
                    reloaded_storyboards.append(sb)
            except Exception as e:
                print(f"Error reloading {fpath}: {e}")
        return {"draft_storyboards": reloaded_storyboards}

    return await asyncio.to_thread(sync_review)

async def batch_human_asset_ingest_node(state: AgentState):
    """
    Breakpoint node. 
    Updates ALL 'storyboards' with final_asset_path from disk.
    """
    def sync_ingest():
        print("Human Ingest: Scanning for verified assets...")
        drafts = state.get("draft_storyboards", [])
        if not drafts:
            return {"ready_to_render_storyboards": []}
            
        assets_dir = "output/assets_final"
        os.makedirs(assets_dir, exist_ok=True)
        
        finalized_storyboards = []
        for video_idx_0, storyboard in enumerate(drafts):
            video_id = video_idx_0 + 1
            updated_scenes = []
            for scene in storyboard.scenes:
                pattern = f"scene_{video_id}_{scene.id}.*"
                candidates = glob.glob(os.path.join(assets_dir, pattern))
                
                if candidates:
                    asset_path = candidates[0]
                    scene.final_asset_path = os.path.abspath(asset_path)
                    if asset_path.lower().endswith(('.mp4', '.mov', '.webm')):
                        d = get_media_duration(asset_path)
                        if d > 0: scene.duration = d
                updated_scenes.append(scene)
            storyboard.scenes = updated_scenes
            storyboard.is_approved = True
            finalized_storyboards.append(storyboard)
        return {"ready_to_render_storyboards": finalized_storyboards}

    return await asyncio.to_thread(sync_ingest)
