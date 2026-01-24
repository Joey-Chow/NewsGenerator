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
    https://www.cbc.ca/news/world/board-of-peace-gaza-trump-list-of-countries-9.7055866
    https://www.theglobeandmail.com/business/economy/article-us-economy-gdp-growth-third-quarter-2025/
    https://www.kitco.com/news/article/2026-01-22/inflation-remains-sticky-gold-prices-hold-support-above-4800
    https://finance.yahoo.com/news/dollar-set-worst-week-since-083446295.html?guccounter=1&guce_referrer=aHR0cHM6Ly9uZXdzLmdvb2dsZS5jb20v&guce_referrer_sig=AQAAANQOu1SQNPEYR-6OO4ER0yxZirlM_0HNuTA0qPSbYFZ49Cc9xNy_rBMSqZgFWkaju1zsnxn0r3ITPXNJjE0BSMTZ4H9w3XSB1U0FcQ6cHtoAhlFR5TI8qWvxrz8UCS8T5ikJoorZ6tRO6e9d_qDXmY5xx0sxk5stGr0-47oyqwqz
    https://www.economist.com/business/2026/01/22/chinese-ai-models-are-popular-but-can-they-make-money
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