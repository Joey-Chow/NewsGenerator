import os
import requests
import mimetypes
from src.state import AgentState

# --- Batch Asset Scraper ---
def batch_asset_scraper_node(state: AgentState):
    """
    Iterates through 'draft_storyboards' and fetches images for ALL scenes.
    Output: draft_storyboards (Updated with asset paths)
    """
    storyboards = state.get("draft_storyboards", [])
    print(f"Batch Asset Scraper: Processing {len(storyboards)} storyboards...")
    
    # 1. Get API Key
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        print("Batch Asset Scraper Error: Missing SERPAPI_API_KEY.")
        return {"draft_storyboards": storyboards} # Return unmodified

    output_dir = "output/assets_final"
    os.makedirs(output_dir, exist_ok=True)
    
    updated_storyboards = []
    
    for video_idx_0, storyboard in enumerate(storyboards):
        video_id = video_idx_0 + 1
        print(f"  - Scraper: Processing Storyboard {video_id} ('{storyboard.title}')...")
        
        updated_scenes = []
        for scene in storyboard.scenes:
            query = scene.image_search_query or "news"
            
            # Skip if already has asset (maybe from manual override?)
            if scene.final_asset_path and os.path.exists(scene.final_asset_path):
                updated_scenes.append(scene)
                continue
                
            print(f"    - Scene {scene.id}: Search '{query}'...")
            
            image_found = False
            try:
                # 2. Call SerpApi
                params = {
                    "engine": "google_images",
                    "q": f"{query} -gettyimages -shutterstock -stock -alamy",
                    "api_key": api_key,
                    "num": 3,
                    "tbs": "itp:photo"
                }
                
                resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("images_results", [])
                    
                    for result in results:
                        image_url = result.get("original") or result.get("thumbnail")
                        if not image_url: continue
                        
                        try:
                            # 3. Download
                            img_resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                            if img_resp.status_code == 200:
                                content_type = img_resp.headers.get("content-type", "").lower()
                                if not content_type.startswith("image/"): continue
                                
                                ext = mimetypes.guess_extension(content_type.split(';')[0]) or ".jpg"
                                if ext in [".html", ".htm"]: continue
                                
                                # Unique Filename: scene_{vid}_{sid}.ext
                                filename = f"scene_{video_id}_{scene.id}{ext}"
                                filepath = os.path.join(output_dir, filename)
                                
                                with open(filepath, "wb") as f:
                                    f.write(img_resp.content)
                                    
                                scene.final_asset_path = os.path.abspath(filepath)
                                print(f"      -> Saved {filename}")
                                image_found = True
                                break 
                        except:
                            pass
                    
                    if not image_found:
                        print(f"      -> No valid images found.")
                else:
                    print(f"      -> SerpApi Error {resp.status_code}")

            except Exception as e:
                print(f"      -> Error: {e}")
                
            updated_scenes.append(scene)
        
        storyboard.scenes = updated_scenes
        updated_storyboards.append(storyboard)

    print("Batch Asset Scraper: Finished.")
    return {"draft_storyboards": updated_storyboards}
