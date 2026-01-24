import os
import requests
import mimetypes
from src.state import AgentState

async def asset_scraper_node(state: AgentState):
    """
    Fetches images using Google Custom Search JSON API based on 'image_search_query'.
    Saves results to 'output/assets_final'.
    """
    print("Asset Scraper: Starting Google Image Search...")
    
    storyboard = state.get("storyboard")
    if not storyboard:
        print("Asset Scraper: Missing storyboard.")
        return {}

    # 1. Get API Key
    api_key = os.environ.get("SERPAPI_API_KEY")
    
    if not api_key:
        print("Asset Scraper Error: Missing SERPAPI_API_KEY in environment variables.")
        return {}

    output_dir = "output/assets_final"
    os.makedirs(output_dir, exist_ok=True)
    
    updated_scenes = []
    
    video_idx = state.get("current_video_index", 1) # Default to 1 if missing
    
    for scene in storyboard.scenes:
        query = scene.image_search_query or scene.visual_instruction or "news"
        print(f"Asset Scraper: Searching SerpApi for Scene {scene.id}: '{query}'...")
        
        try:
            # 2. Call SerpApi (Google Images Engine)
            params = {
                "engine": "google_images",
                "q": query,
                "api_key": api_key,
                "num": 3,  # Fetch up to 3 results for fallback
                "tbs": "itp:photo" # Photos only (Filters out clips/charts), Medium/Large allowed
            }
            
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("images_results", [])
                
                image_found = False
                for result in results:
                    image_url = result.get("original") or result.get("thumbnail")
                    if not image_url:
                        continue
                        
                    print(f"Asset Scraper: Trying image URL: {image_url}")
                    
                    try:
                        # 3. Download Image
                        img_resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                        
                        if img_resp.status_code == 200:
                            content_type = img_resp.headers.get("content-type", "").lower()
                            
                            # STRICT VALIDATION: Must be an image
                            if not content_type.startswith("image/"):
                                print(f"Asset Scraper: Skipped non-image content type: {content_type}")
                                continue
                                
                            ext = mimetypes.guess_extension(content_type.split(';')[0]) or ".jpg"
                            if ext == ".html" or ext == ".htm":
                                print("Asset Scraper: Skipped HTML file masquerading as image.")
                                continue
                            
                            # Unique filename: scene_{video_idx}_{scene_id}.ext
                            filename = f"scene_{video_idx}_{scene.id}{ext}"
                            filepath = os.path.join(output_dir, filename)
                            
                            with open(filepath, "wb") as f:
                                f.write(img_resp.content)
                                
                            scene.final_asset_path = os.path.abspath(filepath)
                            print(f"Asset Scraper: Saved {filename}")
                            image_found = True
                            break # Success, stop looking for this scene
                        else:
                            print(f"Asset Scraper: Download failed ({img_resp.status_code})")
                    except Exception as download_err:
                        print(f"Asset Scraper: Download error: {download_err}")
                
                if not image_found:
                     print(f"Asset Scraper: No valid images found for '{query}' after trying {len(results)} results.")
            else:
                print(f"Asset Scraper: SerpApi Error {resp.status_code}: {resp.text}")

        except Exception as e:
            print(f"Asset Scraper: Error processing Scene {scene.id}: {e}")
            
        updated_scenes.append(scene)

    return {"storyboard": storyboard}
