# eval/run_eval.py
"""
Evaluation runner.
Loads benchmark articles, runs only the script + image stages of the pipeline
(skipping TTS, rendering, concatenation, and upload), then scores outputs.

Usage:
    python -m eval.run_eval --version baseline --articles eval/benchmark_articles.json
    python -m eval.run_eval --version advanced --articles eval/benchmark_articles.json
"""
import os
import sys
import json
import time
import argparse
import asyncio
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state import AgentState
from src.agents.scraper import batch_scraper_node
from src.agents.editor import batch_editor_node
from src.agents.photographer import batch_photographer_node
from eval.score_outputs import score_full_run


def _try_import_critics():
    """Import critic agents if available (advanced branch only)."""
    try:
        from src.agents.script_critic import script_critic_node
        from src.agents.image_critic import image_critic_node
        return script_critic_node, image_critic_node
    except ImportError:
        return None, None


def build_eval_graph(version="baseline", checkpointer=None):
    """Build an eval pipeline based on version.

    Baseline:  scraper → editor → photographer → END
    Advanced:  scraper → editor → script_critic ⇄ editor
               → photographer → image_critic ⇄ photographer → END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("scraper", batch_scraper_node)
    workflow.add_node("editor", batch_editor_node)
    workflow.add_node("photographer", batch_photographer_node)

    workflow.set_entry_point("scraper")
    workflow.add_edge("scraper", "editor")

    script_critic_node, image_critic_node = _try_import_critics()

    if version == "advanced" and script_critic_node and image_critic_node:
        workflow.add_node("script_critic", script_critic_node)
        workflow.add_node("image_critic", image_critic_node)

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
    else:
        # Baseline: no critics
        workflow.add_edge("editor", "photographer")
        workflow.add_edge("photographer", END)

    return workflow.compile(checkpointer=checkpointer)


def load_benchmark(path: str) -> list:
    with open(path) as f:
        articles = json.load(f)
    print(f"Loaded {len(articles)} benchmark articles from {path}")
    return articles


async def _run_single_pair(pair: list, version: str, pair_idx: int) -> dict:
    """Run one pair of articles through the eval pipeline."""
    checkpointer = MemorySaver()
    app = build_eval_graph(version=version, checkpointer=checkpointer)

    initial_state = {
        "news_urls": [a["url"] for a in pair],
        "scraped_articles": pair,
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

    config = {"configurable": {"thread_id": f"eval_{version}_{pair_idx}_{int(time.time())}"}}

    start_time = time.time()

    last_state = {}
    async for event in app.astream(initial_state, config):
        for node_name, node_output in event.items():
            print(f"  [{version}] Node completed: {node_name}")
            if isinstance(node_output, dict):
                last_state.update(node_output)

    elapsed = time.time() - start_time

    storyboards = last_state.get("photographer_storyboards", []) or last_state.get("draft_storyboards", [])

    # Fill in image paths from disk if checkpoint lost them
    image_dir = os.path.abspath("output/assets_final")
    for video_idx, sb in enumerate(storyboards):
        video_id = video_idx + 1
        for scene in sb.scenes:
            if scene.final_asset_path and os.path.exists(scene.final_asset_path):
                continue
            for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                candidate = os.path.join(image_dir, f"scene_{video_id}_{scene.id}{ext}")
                if os.path.exists(candidate):
                    scene.final_asset_path = candidate
                    break

    return {
        "storyboards": storyboards,
        "elapsed_seconds": round(elapsed, 2),
        "state": last_state,
    }


BATCH_SIZE = 2  # Editor processes 2 articles at a time


async def run_pipeline(articles: list, version: str) -> dict:
    """Run the eval pipeline on articles in pairs (editor handles 2 at a time)."""
    all_storyboards = []
    total_elapsed = 0
    total_script_retries = 0
    total_image_retries = 0

    for i in range(0, len(articles), BATCH_SIZE):
        pair = articles[i:i + BATCH_SIZE]
        pair_num = i // BATCH_SIZE + 1
        total_pairs = (len(articles) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n{'='*60}")
        print(f"  BATCH {pair_num}/{total_pairs}: articles {i}-{i+len(pair)-1}")
        print(f"{'='*60}")

        result = await _run_single_pair(pair, version, pair_num)

        all_storyboards.extend(result["storyboards"])
        total_elapsed += result["elapsed_seconds"]
        state = result.get("state", {})
        total_script_retries += state.get("script_critic_retry_count", 0)
        total_image_retries += state.get("image_critic_retry_count", 0)

    return {
        "version": version,
        "storyboards": all_storyboards,
        "elapsed_seconds": round(total_elapsed, 2),
        "state": {
            "script_critic_retry_count": total_script_retries,
            "image_critic_retry_count": total_image_retries,
        },
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
