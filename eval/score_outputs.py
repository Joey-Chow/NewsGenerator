# eval/score_outputs.py
"""
LLM-as-Judge evaluation module.
Scores pipeline outputs using Claude (Anthropic) as an independent judge for:
  - Script quality (accuracy, coherence, engagement) with source grounding
  - Image relevance (multimodal: actual image vs. scene narration)

Uses a different model provider than the generation pipeline (Gemini) to avoid
self-evaluation bias.
"""
import os
import re
import json
import csv
import base64
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic
from src.state import Storyboard


SCRIPT_JUDGE_PROMPT = """You are evaluating a news video script for quality.
You will receive:
1. A storyboard (title + scenes with spoken narration)
2. The ORIGINAL SOURCE ARTICLE the script was based on

Evaluate on three dimensions:
- accuracy (1-5): Does the script faithfully represent the source article? Are there fabricated claims, misquoted figures, or contradictions with the source?
- coherence (1-5): Do scenes flow logically? Is there a clear narrative arc (hook -> body -> outlook)?
- engagement (1-5): Is the language compelling and viewer-appropriate for a news broadcast?

Return ONLY valid JSON:
{
  "accuracy": <int 1-5>,
  "coherence": <int 1-5>,
  "engagement": <int 1-5>,
  "reasoning": "<2-3 sentences explaining the scores>"
}
"""

IMAGE_JUDGE_PROMPT = """You are evaluating whether an image is relevant to a news narration line.

The narration text is provided along with the image.
Score the image's relevance to the narration:
- 5: Perfect visual match -- image directly depicts the narration subject
- 4: Good -- clearly related, minor mismatch
- 3: Acceptable -- loosely related
- 2: Poor -- misleading or too generic
- 1: Irrelevant -- no connection

Return ONLY valid JSON:
{
  "relevance": <int 1-5>,
  "reasoning": "<one sentence>"
}
"""


def _get_llm(temperature=0.2):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        temperature=temperature,
        anthropic_api_key=key,
    )


def _parse_json(text: str) -> dict:
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def score_script(storyboard: Storyboard, source_article: str) -> dict:
    """Score a storyboard's script quality against its source article."""
    llm = _get_llm(temperature=0.2)

    scenes_text = "\n".join(
        [f"Scene {s.id}: {s.subtitle_text}" for s in storyboard.scenes]
    )

    user_content = (
        f"STORYBOARD TITLE: {storyboard.title}\n\n"
        f"SCENES:\n{scenes_text}\n\n"
        f"ORIGINAL SOURCE ARTICLE:\n{source_article[:8000]}"
    )

    messages = [
        SystemMessage(content=SCRIPT_JUDGE_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    result = _parse_json(response.content)

    return {
        "accuracy": int(result.get("accuracy", 3)),
        "coherence": int(result.get("coherence", 3)),
        "engagement": int(result.get("engagement", 3)),
        "reasoning": result.get("reasoning", ""),
    }


def score_image(scene_text: str, image_path: str) -> dict:
    """Score an image's relevance to its scene narration using Gemini Vision."""
    llm = _get_llm(temperature=0.1)

    image_b64 = _encode_image(image_path)

    messages = [
        SystemMessage(content=IMAGE_JUDGE_PROMPT),
        HumanMessage(content=[
            {"type": "text", "text": f"Narration: \"{scene_text}\""},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]),
    ]

    response = llm.invoke(messages)
    result = _parse_json(response.content)

    return {
        "relevance": int(result.get("relevance", 3)),
        "reasoning": result.get("reasoning", ""),
    }


def score_full_run(storyboards: list, articles: list, output_csv: str):
    """Score all storyboards and images from a pipeline run. Write results to CSV."""
    rows = []

    for idx, sb in enumerate(storyboards):
        source = articles[idx]["raw_news"] if idx < len(articles) else ""

        # Script scoring
        script_scores = score_script(sb, source)

        # Image scoring per scene
        image_scores = []
        for scene in sb.scenes:
            if scene.final_asset_path and os.path.exists(scene.final_asset_path):
                img_score = score_image(scene.subtitle_text, scene.final_asset_path)
                image_scores.append(img_score["relevance"])
            else:
                image_scores.append(None)

        valid_scores = [s for s in image_scores if s is not None]
        avg_image = sum(valid_scores) / len(valid_scores) if valid_scores else 0

        rows.append({
            "storyboard_idx": idx,
            "title": sb.title,
            "accuracy": script_scores["accuracy"],
            "coherence": script_scores["coherence"],
            "engagement": script_scores["engagement"],
            "script_reasoning": script_scores["reasoning"],
            "avg_image_relevance": round(avg_image, 2),
            "image_scores": json.dumps(image_scores),
            "num_scenes": len(sb.scenes),
            "num_images_found": len(valid_scores),
        })

    if not storyboards:
        return rows

    fieldnames = [
        "storyboard_idx", "title", "accuracy", "coherence", "engagement",
        "script_reasoning", "avg_image_relevance", "image_scores",
        "num_scenes", "num_images_found",
    ]
    dirname = os.path.dirname(output_csv)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Scores written to {output_csv}")
    return rows
