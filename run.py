import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.graph import build_graph

import sys
import json

async def main():
    print("🚀 Starting Serious News Automation System...")
    app = build_graph()
    
    # Visualization (Non-critical)
    try:
        print(app.get_graph().draw_ascii())
    except (ImportError, ValueError) as e:
        print(f"Graph visualization skipped: {e}")

    # Execution
    # Execution
    # ---------------------------------------------------------
    # 📝 CONFIGURATION: Paste your URLs below (one per line)
    # ---------------------------------------------------------
    URLS_TEXT = """
    https://www.bbc.com/news/articles/c3wz2x7ppz7o
    https://www.theglobeandmail.com/world/article-trump-minneapolis-protests-ice-immigration/
    https://www.bbc.com/news/articles/cly5pd459gko
    https://www.bbc.com/news/articles/cevnppplkjjo
    https://nationalpost.com/news/canada/carney-working-on-trip-to-india-and-possible-trade-deal
    https://www.wsj.com/finance/gold-hits-new-high-oil-rises-as-iran-tensions-rekindle-fc112871
    """
    # ---------------------------------------------------------
    
    # Parse URLs from text block
    urls = [line.strip() for line in URLS_TEXT.strip().splitlines() if line.strip()]
    
    print(f"\n▶️ Running workflow for: {urls}")
    inputs = {
        "news_urls": urls,
        "generated_segments": [],
        "news_url": None
    }
    
    # Config for state persistence
    config = {"configurable": {"thread_id": "news_gen_thread_1"}}
    
    # 1. Start the graph (will run until interrupt)
    print("running...")
    
    # Initial run
    # Use astream to see progress or just ainvoke
    # We use ainvoke(None, config) for resumes
    
    current_input = inputs
    
    while True:
        try:
            # Run until next interrupt or end
            await app.ainvoke(current_input, config=config)
            
            # Check state
            snapshot = app.get_state(config)
            next_steps = snapshot.next
            
            if not next_steps:
                print("\n✅ Workflow Finished!")
                break
            
            # Handle Interrupts
            if "batch_script_review" in next_steps:
                print("\n" + "="*60)
                print("⏸️  INTERRUPT 1: SCRIPT REVIEW")
                print("="*60)
                print("1. Please check 'output/storyboard/' for generated JSON files.")
                print("2. Edit the subtitles or visual instructions if needed.")
                print("3. Save your changes.")
                input("\n⌨️  Press ENTER to confirm edits and continue to Asset Scraping...")
                print("\n▶️ Resuming workflow...")
                current_input = None # Resume
                
            elif "batch_editor" in next_steps:
                print("\n" + "="*60)
                print("⏸️  INTERRUPT 0: SCRAPER REVIEW")
                print("="*60)
                print("1. Please check 'output/scraped_data.json' for scraped content.")
                print("2. Edit the headlines or text if needed.")
                print("3. Save your changes.")
                input("\n⌨️  Press ENTER to confirm data and continue to Editor...")
                
                # Reload data from file
                try:
                    with open("output/scraped_data.json", "r", encoding='utf-8') as f:
                        updated_articles = json.load(f)
                    
                    # Update state
                    app.update_state(config, {"scraped_articles": updated_articles})
                    print("✅ Scraped data reloaded from file.")
                except Exception as e:
                    print(f"⚠️ Failed to reload scraped data: {e}. Using original data.")

                print("\n▶️ Resuming workflow...")
                current_input = None # Resume

            elif "batch_human_ingest" in next_steps:
                print("\n" + "="*60)
                print("⏸️  INTERRUPT 2: ASSET REVIEW")
                print("="*60)
                print("1. Please check 'output/assets_final/' for downloaded images.")
                print("2. Replace or delete images as needed (ensure filenames match scene_X_Y).")
                input("\n⌨️  Press ENTER to confirm assets and continue to Audio/Rendering...")
                print("\n▶️ Resuming workflow...")
                current_input = None # Resume
                
            else:
                print(f"Workflow paused at unexpected step: {next_steps}")
                break
                
        except Exception as e:
            print(f"Error during execution: {e}")
            break

if __name__ == "__main__":
    asyncio.run(main())

# source .venv/bin/activate