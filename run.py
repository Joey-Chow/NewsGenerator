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
    
    # Run the graph
    final_state = await app.ainvoke(inputs)
    
    print("\n✅ Workflow Finished!")


if __name__ == "__main__":
    asyncio.run(main())

# python run.py "https://www.bbc.com/news/articles/cx2yppj4lg4o"