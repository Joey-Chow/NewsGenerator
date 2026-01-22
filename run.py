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
    url = "https://www.bbc.com/news/business-68000000" # Default or placeholder
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    print(f"\n▶️ Running workflow for: {url}")
    inputs = {"news_url": url}
    
    # Config for state persistence
    config = {"configurable": {"thread_id": "news_gen_thread_1"}}
    
    # 1. Start the graph (will run until interrupt)
    print("running...")
    result = await app.ainvoke(inputs, config=config)
    
    # 2. Check current state to see if valid interrupt happened
    snapshot = app.get_state(config)
    next_step = snapshot.next
    
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
        result = await app.ainvoke(None, config=config)
    
    print("\n✅ Workflow Finished!")
    # print(result) # Debug output

if __name__ == "__main__":
    asyncio.run(main())

# source .venv/bin/activate
# python run.py "https://www.bbc.com/news/articles/cx2yppj4lg4o"