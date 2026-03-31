# eval/run_eval.py
"""
Evaluation runner.
Loads benchmark articles, injects them into the pipeline (bypassing scraper),
runs the graph, and saves outputs + scores.

Usage:
    python -m eval.run_eval --version advanced --articles eval/benchmark_articles.json
"""
import os
import sys
import json
import time
import argparse
import asyncio
from datetime import datetime
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph import build_graph
from eval.score_outputs import score_full_run


def load_benchmark(path: str) -> list:
    with open(path) as f:
        articles = json.load(f)
    print(f"Loaded {len(articles)} benchmark articles from {path}")
    return articles


async def run_pipeline(articles: list, version: str) -> dict:
    """Run the pipeline with benchmark articles injected as scraped_articles."""
    checkpointer = MemorySaver()
    app = build_graph(checkpointer=checkpointer)

    initial_state = {
        "news_urls": [a["url"] for a in articles],
        "scraped_articles": articles,
        "draft_storyboards": [],
        "photographer_storyboards": [],
        "reporter_storyboards": [],
        "ready_to_render_storyboards": [],
        "generated_segments": [],
        "final_video_path": None,
        "youtube_url": None,
        "script_critic_retry_count": 0,
        "image_critic_retry_count": 0,
        "script_critic_feedback": None,
        "image_critic_feedback": None,
        "script_critic_failed_indices": None,
        "user_feedback": None,
        "is_approved": False,
    }

    config = {"configurable": {"thread_id": f"eval_{version}_{int(time.time())}"}}

    start_time = time.time()

    async for event in app.astream(initial_state, config):
        for node_name, node_output in event.items():
            print(f"  [{version}] Node completed: {node_name}")

    elapsed = time.time() - start_time

    snapshot = app.get_state(config)
    state = snapshot.values

    return {
        "version": version,
        "storyboards": state.get("ready_to_render_storyboards", []) or state.get("draft_storyboards", []),
        "elapsed_seconds": round(elapsed, 2),
        "state": state,
    }


def save_results(result: dict, articles: list, output_dir: str):
    """Save storyboards as JSON and score them."""
    os.makedirs(output_dir, exist_ok=True)

    for idx, sb in enumerate(result["storyboards"]):
        path = os.path.join(output_dir, f"storyboard_{idx + 1}.json")
        with open(path, "w") as f:
            f.write(sb.model_dump_json(indent=2))

    state = result.get("state", {})
    meta = {
        "version": result["version"],
        "elapsed_seconds": result["elapsed_seconds"],
        "num_storyboards": len(result["storyboards"]),
        "script_critic_retry_count": state.get("script_critic_retry_count", 0),
        "image_critic_retry_count": state.get("image_critic_retry_count", 0),
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    csv_path = os.path.join(output_dir, "scores.csv")
    scores = score_full_run(result["storyboards"], articles, csv_path)

    print(f"\n{'='*50}")
    print(f"  {result['version'].upper()} RESULTS")
    print(f"{'='*50}")
    print(f"  Time: {result['elapsed_seconds']}s")
    print(f"  Storyboards: {len(result['storyboards'])}")
    for row in scores:
        print(f"  [{row['title']}]")
        print(f"    Accuracy={row['accuracy']} Coherence={row['coherence']} Engagement={row['engagement']}")
        print(f"    Avg Image Relevance={row['avg_image_relevance']}")
    print(f"{'='*50}\n")

    return scores


def main():
    parser = argparse.ArgumentParser(description="Run evaluation pipeline")
    parser.add_argument("--version", choices=["baseline", "advanced"], required=True)
    parser.add_argument("--articles", default="eval/benchmark_articles.json")
    args = parser.parse_args()

    articles = load_benchmark(args.articles)
    result = asyncio.run(run_pipeline(articles, args.version))
    output_dir = f"eval/results/{args.version}"
    save_results(result, articles, output_dir)


if __name__ == "__main__":
    main()
