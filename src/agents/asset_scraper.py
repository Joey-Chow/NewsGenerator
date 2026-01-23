import os
import requests
from playwright.async_api import async_playwright
import mimetypes
import uuid
from src.state import AgentState

async def asset_scraper_node(state: AgentState):
    """
    Screenshots paragraph elements from the news URL better matching the storyboard scenes
    and saves them directly to 'output/assets_final'.
    """
    print("Asset Scraper: Starting paragraph screenshotting...")
    url = state.get("news_url")
    storyboard = state.get("storyboard")
    
    if not url or not storyboard:
        print("Asset Scraper: Missing URL or Storyboard.")
        return {}
    
    # Switch to assets_final directly
    output_dir = "output/assets_final"
    os.makedirs(output_dir, exist_ok=True)
    
    updated_scenes = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use dimensions matching the Floating Frame Container (calculated from Composition 1280x720)
        # 1280 * 100% * 90% = 1152 width
        # 720 * 90% * 90% = 583 height
        context = await browser.new_context(
            viewport={"width": 1152, "height": 480},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print(f"Asset Scraper: Visiting {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 1. Force remove common overlays/modals using JS
            await page.evaluate("""() => {
                const selectors = ['#onetrust-banner-sdk', '.cookie-banner', '.modal', '[id*="cookie"]', '[class*="popup"]'];
                selectors.forEach(s => {
                    const els = document.querySelectorAll(s);
                    els.forEach(e => e.remove());
                });
            }""")
            
            # 2. Inject CSS to style paragraphs for readability
            # defined .highlight-target for the active paragraph
            await page.add_style_tag(content="""
                body { background: #f0f0f0 !important; }
                p { 
                    font-family: 'Georgia', serif !important; 
                    font-size: 24px !important; 
                    line-height: 1.8 !important;
                    color: #333 !important; /* Default context color */
                    background: transparent !important;
                    padding: 10px 0 !important;
                    margin: 20px auto !important;
                    max-width: 800px !important;
                    display: block !important;
                    opacity: 1 !important;
                    visibility: visible !important;
                    border: none !important;
                    box-shadow: none !important;
                }
                .highlight-target {
                    color: #d00 !important; /* Red highlight */
                    font-weight: bold !important;
                    background: #fff !important;
                    padding: 20px !important;
                    border-radius: 8px !important;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
                }
            """)
            
            # Find candidate paragraphs
            paragraphs = await page.locator('p').all()
            candidates = []
            for p_loc in paragraphs:
                try:
                    if await p_loc.is_visible():
                        txt = await p_loc.text_content()
                        if txt and len(txt.strip()) > 60:
                            candidates.append(p_loc)
                except:
                    continue
            
            print(f"Asset Scraper: Found {len(candidates)} visible candidate paragraphs.")
            
            # Map Scenes to Paragraphs
            for i, scene in enumerate(storyboard.scenes):
                if candidates:
                    target_p = candidates[i % len(candidates)]
                    
                    filename = f"scene_{scene.id}.png"
                    filepath = os.path.abspath(os.path.join(output_dir, filename))
                    
                    try:
                        # 1. Highlight target
                        await target_p.evaluate("el => el.classList.add('highlight-target')")
                        
                        # 2. Scroll to center
                        # Calculate position to center the element
                        box = await target_p.bounding_box()
                        if box:
                            viewport = page.viewport_size
                            target_y = box['y'] + box['height'] / 2
                            scroll_y = target_y - (viewport['height'] / 2)
                            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
                        
                        # Add a delay for scroll and render
                        await page.wait_for_timeout(300) 
                        
                        # 3. Capture Viewport Screenshot (Fixed Size)
                        await page.screenshot(path=filepath)
                        scene.final_asset_path = filepath
                        print(f"Asset Scraper: Saved {filename} for Scene {scene.id}")
                        
                        # 4. Remove highlight for next iteration
                        await target_p.evaluate("el => el.classList.remove('highlight-target')")
                        
                    except Exception as e:
                        print(f"Asset Scraper: Failed to screenshot for Scene {scene.id}: {e}")
                else:
                    print(f"Asset Scraper: No candidates for Scene {scene.id}")
                
                updated_scenes.append(scene)

        except Exception as e:
             print(f"Asset Scraper Error: {e}")
        finally:
             await browser.close()
             
    # Cleanup raw folder if requested
    raw_dir = "output/assets_raw"
    if os.path.exists(raw_dir):
        import shutil
        shutil.rmtree(raw_dir)
        print("Asset Scraper: Removed output/assets_raw")

    return {"storyboard": storyboard}
