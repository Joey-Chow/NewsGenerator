import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.graph import build_graph

import sys

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
    https://www.theglobeandmail.com/business/economy/article-us-economy-gdp-growth-third-quarter-2025/
    https://www.cbc.ca/news/world/board-of-peace-gaza-trump-list-of-countries-9.7055866
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
    await app.ainvoke(inputs, config=config)
    
    # 2. Loop to handle multiple interrupts (one per video)
    while True:
        snapshot = app.get_state(config)
        next_step = snapshot.next
        
        if not next_step:
            # Workflow finished (reached END)
            break
            
        if "human_asset_ingest" in next_step:
            print("\n" + "="*50)
            print("⏸️  WORKFLOW PAUSED: Human Input Required")
            print("="*50)
            print("Scraper and Editor have finished.")
            print("1. Please check 'output/assets_raw' for downloaded images.")
            print("2. Select and rename assets to 'output/assets_final/part_{id}.jpg' or 'scene_{id}.mp4' etc.")
            print("3. When done, press ENTER to resume ingestion and rendering.")
            input("Press Enter to continue...")
            
            print("\n▶️ Resuming workflow...")
            # Dictionary input of None means resume with current state
            await app.ainvoke(None, config=config)
        else:
            # Stopped at some other point unexpectedly
            print(f"Workflow paused at unexpected step: {next_step}")
            break
    
    print("\n✅ Workflow Finished!")
    # print(result) # Debug output

if __name__ == "__main__":
    asyncio.run(main())

# source .venv/bin/activate