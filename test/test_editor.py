import os
import json
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from src.agents.editor import batch_editor_node

def test_editor():
    print("🚀 Starting Isolated Editor Test...")
    
    # Check if scraped data exists
    scraped_data_path = "output/raw_news/scraped_data.json"
    if not os.path.exists(scraped_data_path):
        print(f"❌ Error: {scraped_data_path} not found. Please run scraper test first.")
        return

    # Load sample data
    with open(scraped_data_path, "r", encoding='utf-8') as f:
        articles = json.load(f)
    
    # Limit to 1 article for quick test if needed, or process all
    # articles = articles[:1]
    
    print(f"Loaded {len(articles)} articles from {scraped_data_path}")

    # Prepare mock state
    state = {
        "scraped_articles": articles,
        "draft_storyboards": []
    }

    # Run Editor Node
    try:
        result = batch_editor_node(state)
        storyboards = result.get("draft_storyboards", [])
        
        print(f"\n✅ Editor Test Completed. Generated {len(storyboards)} storyboards.")
        
        if storyboards:
            sample = storyboards[0]
            # Storyboard is a Pydantic model (from src.state)
            print("\nSample Storyboard Structure:")
            print(f"- Title: {sample.title}")
            print(f"- Scenes Count: {len(sample.scenes)}")
            if sample.scenes:
                print(f"- First Scene Text: {sample.scenes[0].subtitle_text}")
                print(f"- First Scene Query: {sample.scenes[0].image_search_query}")
    
    except Exception as e:
        print(f"❌ Editor Test Failed: {e}")

if __name__ == "__main__":
    # Ensure we are in the project root
    if not os.path.exists("src"):
        print("Please run this script from the project root.")
    else:
        # Load environment variables (mostly for GEMINI_API_KEY)
        # Assuming user has it set in their environment or .env
        test_editor()
