import os
import requests
from playwright.async_api import async_playwright
import mimetypes
import uuid
from src.state import AgentState

async def asset_scraper_node(state: AgentState):
    """
    Scrapes all images from the news URL and saves them to 'output/assets_raw'.
    This helper allows the human editor to pick assets easily.
    """
    print("Asset Scraper: Starting raw image collection...")
    url = state.get("news_url")
    if not url:
        print("Asset Scraper: No URL found.")
        return {}
    
    output_dir = "output/assets_raw"
    os.makedirs(output_dir, exist_ok=True)
    
    downloaded_paths = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print(f"Asset Scraper: Visiting {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Find all image elements
            # We filter for reasonable size to avoid icons
            images = await page.evaluate('''() => {
                return Array.from(document.images)
                    .filter(img => img.naturalWidth > 200 && img.naturalHeight > 200)
                    .map(img => img.src);
            }''')
            
            print(f"Asset Scraper: Found {len(images)} candidate images.")
            
            # Download images
            for i, img_url in enumerate(images):
                try:
                    # Handle base64 or relative
                    if img_url.startswith("data:image"):
                        # Skip base64 for now or handle simple ones
                        continue
                        
                    ext = mimetypes.guess_extension(requests.head(img_url, timeout=5).headers.get('content-type', '')) or ".jpg"
                    if ext == ".jpe": ext = ".jpg"
                    
                    filename = f"raw_{i}_{uuid.uuid4().hex[:4]}{ext}"
                    filepath = os.path.join(output_dir, filename)
                    
                    # Download
                    content = requests.get(img_url, timeout=10).content
                    with open(filepath, "wb") as f:
                        f.write(content)
                        
                    downloaded_paths.append(filepath)
                    print(f"Asset Scraper: Downloaded {filepath}")
                    
                    if len(downloaded_paths) >= 20: # Limit to 20
                        break
                except Exception as e:
                    print(f"Asset Scraper Warning: Failed to download {img_url}: {e}")
                    
        except Exception as e:
             print(f"Asset Scraper Error: {e}")
        finally:
             await browser.close()
             
    print(f"Asset Scraper: Finished. {len(downloaded_paths)} images saved to {output_dir}")
    # We don't necessarily need to put this in state, but we can verify it exists.
    # The user instruction says Human Loop follows this.
    return {}
