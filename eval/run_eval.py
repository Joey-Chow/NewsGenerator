# eval/run_eval.py
"""
Evaluation runner.
Loads benchmark articles, runs only the script + image stages of the pipeline
(skipping TTS, rendering, concatenation, and upload), then scores outputs.

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
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state import AgentState
from src.agents.scraper import batch_scraper_node
from src.agents.editor import batch_editor_node
from src.agents.script_critic import script_critic_node
from src.agents.photographer import batch_photographer_node
from src.agents.image_critic import image_critic_node
from eval.score_outputs import score_full_run


def build_eval_graph(checkpointer=None):
    """Build a trimmed pipeline for evaluation: editor + photographer only.

    Flow: scraper → editor → script_critic ⇄ editor (retry loop)
          → photographer → image_critic ⇄ photographer (retry loop) → END
    Skips: HITL review, TTS (reporter), join_assets, renderer, concat, youtuber.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("scraper", batch_scraper_node)
    workflow.add_node("editor", batch_editor_node)
    workflow.add_node("script_critic", script_critic_node)
    workflow.add_node("photographer", batch_photographer_node)
    workflow.add_node("image_critic", image_critic_node)

    workflow.set_entry_point("scraper")
    workflow.add_edge("scraper", "editor")
    workflow.add_edge("editor", "script_critic")

    def route_after_script_critic(state: AgentState):
        if state.get("script_critic_feedback"):
            return "editor"
        return "photographer"

    workflow.add_conditional_edges(
        "script_critic",
        route_after_script_critic,
        {"editor": "editor", "photographer": "photographer"},
    )

    workflow.add_edge("photographer", "image_critic")

    def route_after_image_critic(state: AgentState):
        if state.get("image_critic_feedback"):
            return "photographer"
        return END

    workflow.add_conditional_edges(
        "image_critic",
        route_after_image_critic,
        {"photographer": "photographer", END: END},
    )

    return workflow.compile(checkpointer=checkpointer)


def load_benchmark(path: str) -> list:
    with open(path) as f:
        articles = json.load(f)
    print(f"Loaded {len(articles)} benchmark articles from {path}")
    return articles


async def run_pipeline(articles: list, version: str) -> dict:
    """Run the eval pipeline with benchmark articles injected as scraped_articles."""
    checkpointer = MemorySaver()
    app = build_eval_graph(checkpointer=checkpointer)

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
        "storyboards": state.get("photographer_storyboards", []) or state.get("draft_storyboards", []),
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
