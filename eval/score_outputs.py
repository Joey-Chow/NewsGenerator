# eval/score_outputs.py
"""
LLM-as-Judge evaluation module.
  - Script quality: Claude (accuracy, coherence, engagement) with source grounding
  - Image relevance: GPT-4o (multimodal vision)

Uses different model providers than the generation pipeline (Gemini) to avoid
self-evaluation bias.
"""
import os
import re
import json
import csv
import base64
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.state import Storyboard


SCRIPT_JUDGE_PROMPT = """You are evaluating a news video script for quality.
You will receive:
1. A storyboard (title + scenes with spoken narration)
2. The ORIGINAL SOURCE ARTICLE the script was based on

Evaluate on three dimensions:
- accuracy (1-5): Does the script faithfully represent the source article? Are there fabricated claims, misquoted figures, or contradictions with the source?
- coherence (1-5): Do scenes flow logically? Is there a clear narrative arc (hook -> body -> outlook)?
- engagement (1-5): Is the language compelling and viewer-appropriate for a news broadcast?

Scoring calibration (apply consistently across all scripts):
- 5: Exceptional. Publishable as-is with no changes needed.
- 4: Good and broadcast-ready. Minor imperfections that would not hurt viewers.
     This is the expected score for a competent, professional script.
- 3: Acceptable but has a clear, specific problem (one factual error, weak opening, etc.).
- 2: Multiple problems that would noticeably hurt the viewer experience.
- 1: Fundamentally broken — fabricated claims, incoherent narrative, or no engagement.

Do NOT score 3 or below unless you can point to a specific, concrete problem in your reasoning.

Return ONLY valid JSON:
{
  "accuracy": <int 1-5>,
  "coherence": <int 1-5>,
  "engagement": <int 1-5>,
  "reasoning": "<2-3 sentences explaining the scores, citing specific evidence from the script>"
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


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return key


def _get_llm(temperature=0.2):
    return ChatOpenAI(
        model="anthropic/claude-sonnet-4-5",
        temperature=temperature,
        api_key=_openrouter_key(),
        base_url=OPENROUTER_BASE_URL,
    )


def _get_vision_llm(temperature=0.1):
    return ChatOpenAI(
        model="openai/gpt-4o",
        temperature=temperature,
        api_key=_openrouter_key(),
        base_url=OPENROUTER_BASE_URL,
    )


def _parse_json(text: str) -> dict:
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


MAX_IMAGE_BYTES = 4_500_000  # stay under Claude's 5MB limit


def _encode_image(path: str) -> str:
    """Read an image and return base64. Resizes if over MAX_IMAGE_BYTES."""
    from PIL import Image
    import io

    with open(path, "rb") as f:
        data = f.read()

    # Check if it's a standard JPEG/PNG that's small enough
    if len(data) <= MAX_IMAGE_BYTES and path.lower().endswith((".jpg", ".jpeg", ".png")):
        return base64.b64encode(data).decode()

    # Resize to fit under the limit
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    quality = 85
    while quality >= 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= MAX_IMAGE_BYTES:
            return base64.b64encode(buf.getvalue()).decode()
        quality -= 15

    # Last resort: scale down
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return base64.b64encode(buf.getvalue()).decode()


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
    """Score an image's relevance to its scene narration using GPT-4o Vision."""
    llm = _get_vision_llm(temperature=0.1)

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
        source_title = articles[idx].get("title", "Unknown") if idx < len(articles) else "N/A"

        print(f"\nScoring storyboard {idx}: '{sb.title}'")
        print(f"  Against source article: '{source_title}'")

        # Script scoring
        script_scores = score_script(sb, source)

        # Image scoring per scene
        image_scores = []
        for scene in sb.scenes:
            if scene.final_asset_path and os.path.exists(scene.final_asset_path):
                try:
                    img_score = score_image(scene.subtitle_text, scene.final_asset_path)
                    image_scores.append(img_score["relevance"])
                except Exception as e:
                    print(f"    WARNING: Image scoring failed for scene {scene.id}: {e}")
                    image_scores.append(None)
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
