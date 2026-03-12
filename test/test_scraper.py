import sys
import os
import json

# Add project root to path so src modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.scraper import batch_scraper_node

def run_isolated_test():
    print("🚀 Starting Isolated Scraper Test...")
    
    # Mock state
    state = {
        "news_urls": [], # Now handled by RSS if empty
        "scraped_articles": []
    }
    
    try:
        # Run the node
        result = batch_scraper_node(state)
        
        articles = result.get("scraped_articles", [])
        print(f"\n✅ Test Completed. Scraped {len(articles)} articles.")
        
        # Verify structure
        if articles:
            sample = articles[0]
            print("\nSample Article Structure:")
            print(f"- Headline: {sample.get('headline')}")
            print(f"- Raw News Length: {len(sample.get('raw_news', ''))} chars")
            print(f"- Summary exists: {'summary' in sample} (Should be False)")
            
            # Save to output for manual inspection
            os.makedirs("output/raw_news", exist_ok=True)
            save_path = "output/raw_news/test_scraper_results.json"
            with open(save_path, "w", encoding='utf-8') as f:
                json.dump(articles, f, indent=2, ensure_ascii=False)
            print(f"\n📄 Results saved to {save_path}")
        else:
            print("\n⚠️ No articles were scraped.")
            
    except Exception as e:
        print(f"\n❌ Test Failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_isolated_test()
