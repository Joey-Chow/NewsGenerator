import os
import shutil
import asyncio
from src.state import AgentState

async def join_assets_node(state: AgentState):
    """
    Joins the outputs from 'photographer' and 'reporter' parallel nodes.
    Merges audio_path, duration, and final_asset_path into ready_to_render_storyboards.
    Also handles global Video Snapshot generation.
    """
    def sync_join():
        print("Join Assets: Merging parallel outputs...")
        
        # 1. Get reloaded drafts (base structure)
        drafts = state.get("draft_storyboards", [])
        
        # 2. Get parallel outputs
        photographer_sbs = state.get("photographer_storyboards", [])
        reporter_sbs = state.get("reporter_storyboards", [])
        
        if not photographer_sbs and not reporter_sbs:
            print("Join Assets Warning: No parallel outputs found. Falling back to drafts.")
            return {"ready_to_render_storyboards": drafts}

        finalized_storyboards = []
        snapshot_dir = "output/snapshot"
        os.makedirs(snapshot_dir, exist_ok=True)

        for i in range(len(drafts)):
            base_sb = drafts[i]
            p_sb = photographer_sbs[i] if i < len(photographer_sbs) else None
            r_sb = reporter_sbs[i] if i < len(reporter_sbs) else None
            
            video_id = i + 1
            print(f"  - Joining Video {video_id} ('{base_sb.title}')...")
            
            # Merge Scene data
            for j in range(len(base_sb.scenes)):
                scene = base_sb.scenes[j]
                
                # Add Image from photographer
                if p_sb and j < len(p_sb.scenes):
                    scene.final_asset_path = p_sb.scenes[j].final_asset_path
                
                # Add Audio from reporter
                if r_sb and j < len(r_sb.scenes):
                    scene.audio_path = r_sb.scenes[j].audio_path
                    scene.duration = r_sb.scenes[j].duration

            # --- Snapshot Logic ---
            snapshot_path = os.path.join(snapshot_dir, f"snapshot_{video_id}.png")
            if not os.path.exists(snapshot_path):
                first_img = next((s.final_asset_path for s in base_sb.scenes if s.final_asset_path), None)
                if first_img and os.path.exists(first_img):
                    try:
                        shutil.copy(first_img, snapshot_path)
                        print(f"    -> Generated Snapshot from Scene 1")
                    except Exception as e:
                        print(f"    -> Snapshot Error: {e}")
                else:
                    print(f"    -> Warning: No image found for snapshot.")
            
            base_sb.is_approved = True
            finalized_storyboards.append(base_sb)

        print(f"Join Assets: Finished. {len(finalized_storyboards)} storyboards ready for render.")
        return {"ready_to_render_storyboards": finalized_storyboards}

    return await asyncio.to_thread(sync_join)
