import asyncio
from playwright.async_api import async_playwright
import os

async def photographer_node(state: dict):
    """
    Takes a screenshot of the news article/headline using Playwright.
    """
    url = state.get("news_url")
    screenshot_paths = []
    
    if not url:
        return {"screenshot_paths": []}

    async with async_playwright() as p:
        # Launch browser in headless mode
        browser = await p.chromium.launch(headless=True)
        # Use a standard user agent to avoid being blocked
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print(f"Visiting {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Basic DOM cleaning (optional, extensible)
            # Remove cookie banners or ads if selectors are known
            # await page.add_style_tag(content="header, footer, .ad, .cookie-banner { display: none !important; }")
            
            # Attempt to find the main article or h1
            # We try a few common selectors
            target_selector = "article"
            if await page.locator(target_selector).count() == 0:
                target_selector = "h1"
            
            # Create output directory
            os.makedirs("output/screenshot", exist_ok=True)
            
            if await page.locator(target_selector).count() > 0:
                # Capture specific element
                element = page.locator(target_selector).first
                output_path = f"output/screenshot/screenshot_{os.urandom(4).hex()}.png"
                await element.screenshot(path=output_path)
                screenshot_paths.append(output_path)
                print(f"Screenshot saved to {output_path}")
            else:
                # Fallback to full page if no article found
                output_path = f"output/screenshot/screenshot_full_{os.urandom(4).hex()}.png"
                await page.screenshot(path=output_path)
                screenshot_paths.append(output_path)
                print(f"Full page screenshot saved to {output_path}")

        except Exception as e:
            print(f"Error taking screenshot: {e}")
        finally:
            await browser.close()
            
    return {"screenshot_paths": screenshot_paths}
