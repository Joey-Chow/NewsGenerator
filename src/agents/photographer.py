import os
import requests
import mimetypes
from src.state import AgentState

import asyncio

# --- Batch Photographer ---
async def batch_photographer_node(state: AgentState):
    """
    Iterates through 'draft_storyboards' and fetches images for ALL scenes.
    Output: photographer_storyboards (Updated with asset paths)
    """
    def sync_photographer():
        storyboards = state.get("draft_storyboards", [])
        print(f"Photographer: Processing {len(storyboards)} storyboards...")
        
        api_key = os.environ.get("SERPAPI_API_KEY")
        if not api_key:
            return {"photographer_storyboards": storyboards}

        output_dir = "output/assets_final"
        os.makedirs(output_dir, exist_ok=True)
        
        updated_storyboards = []
        for video_idx_0, storyboard in enumerate(storyboards):
            video_id = video_idx_0 + 1
            updated_scenes = []
            for scene in storyboard.scenes:
                query = scene.image_search_query or "news"
                if scene.final_asset_path and os.path.exists(scene.final_asset_path):
                    updated_scenes.append(scene)
                    continue
                    
                image_found = False
                try:
                    params = {
                        "engine": "google_images",
                        "q": f"{query} -gettyimages -shutterstock -stock -alamy",
                        "api_key": api_key,
                        "num": 3,
                        "tbs": "itp:photo"
                    }
                    resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
                    if resp.status_code == 200:
                        results = resp.json().get("images_results", [])
                        for result in results:
                            image_url = result.get("original") or result.get("thumbnail")
                            if not image_url: continue
                            try:
                                img_resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                                if img_resp.status_code == 200:
                                    content_type = img_resp.headers.get("content-type", "").lower()
                                    if not content_type.startswith("image/"): continue
                                    ext = mimetypes.guess_extension(content_type.split(';')[0]) or ".jpg"
                                    filename = f"scene_{video_id}_{scene.id}{ext}"
                                    filepath = os.path.join(output_dir, filename)
                                    with open(filepath, "wb") as f:
                                        f.write(img_resp.content)
                                    scene.final_asset_path = os.path.abspath(filepath)
                                    image_found = True
                                    break 
                            except: pass
                    if not image_found: print(f"      -> No valid images found.")
                except Exception as e: print(f"      -> Error: {e}")
                updated_scenes.append(scene)
            storyboard.scenes = updated_scenes
            updated_storyboards.append(storyboard)
        return {"photographer_storyboards": updated_storyboards}

    # Execute sync logic in a separate thread
    return await asyncio.to_thread(sync_photographer)
