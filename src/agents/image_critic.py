# src/agents/image_critic.py
import os
import json
import re
import base64
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import AgentState

MAX_RETRIES = 2
PASS_THRESHOLD = 4

MULTIMODAL_CRITIC_PROMPT = """You are an Image Relevance Critic for a news video pipeline.

You will receive scenes from a news storyboard. For each scene you get:
- scene_id: integer
- subtitle_text: the spoken narration for that scene
- The actual image that will be displayed during the narration (if available)
- image_search_query: the query used to find the image

Your job: evaluate whether each image is RELEVANT to its narration text.

Score each scene's relevance from 1 to 5:
- 5: Perfect — image directly depicts what the narration describes
- 4: Good — clearly related, minor mismatch
- 3: Acceptable — loosely related
- 2: Poor — misleading or too generic
- 1: Irrelevant — no visual connection to narration

If ANY scene scores below 4, set "passed" to false.
For failed scenes, provide a "refined_query" — a better Google Images search query.

Return ONLY valid JSON:
{
  "evaluations": [
    {
      "scene_id": <int>,
      "relevance": <int 1-5>,
      "reasoning": "<short explanation>",
      "refined_query": "<new query string, only if relevance < 4>"
    }
  ],
  "passed": <bool>
}
"""

TEXT_ONLY_CRITIC_PROMPT = """You are an Image Relevance Critic for a news video pipeline.

You will receive scenes where no image was downloaded yet. Evaluate whether the search query
is likely to produce a relevant image for the narration.

For each scene you get:
- scene_id: integer
- subtitle_text: the spoken narration
- image_search_query: the query that will be used to search Google Images

Score each scene's query relevance from 1 to 5:
- 5: Perfect — query will find exactly what the narration describes
- 4: Good — reasonable query, minor mismatch
- 3: Acceptable — somewhat related
- 2: Poor — too generic or misleading
- 1: Irrelevant — query has no relation to narration

If ANY scene scores below 4, set "passed" to false.
For failed scenes, provide a "refined_query".

Return ONLY valid JSON:
{
  "evaluations": [
    {
      "scene_id": <int>,
      "relevance": <int 1-5>,
      "reasoning": "<short explanation>",
      "refined_query": "<new query string, only if relevance < 4>"
    }
  ],
  "passed": <bool>
}
"""


def _encode_image_safe(path: str) -> str | None:
    """Encode an image to base64, returning None if the file doesn't exist or is too large."""
    if not path or not os.path.exists(path):
        return None
    size = os.path.getsize(path)
    if size > 4 * 1024 * 1024:  # Skip images > 4MB (Gemini limit)
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


def _parse_evaluations(content: str) -> dict:
    """Extract JSON evaluations from LLM response."""
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)
    return json.loads(content)


def _apply_evaluations(result: dict, sb, total_scenes: int, failed_scenes: int, any_failed: bool):
    """Apply evaluation results to storyboard scenes, updating queries for failures."""
    evaluations = result.get("evaluations", [])

    for ev in evaluations:
        scene_id = ev.get("scene_id")
        relevance = ev.get("relevance", 5)
        reasoning = ev.get("reasoning", "")
        refined = ev.get("refined_query")
        total_scenes += 1

        passed = relevance >= PASS_THRESHOLD
        status = "PASS" if passed else "FAIL"

        if not passed:
            failed_scenes += 1
            any_failed = True
            print(f"    Scene {scene_id}: {relevance}/5  {status}  — {reasoning}")
            if refined:
                for scene in sb.scenes:
                    if scene.id == scene_id:
                        print(f"      Old query: '{scene.image_search_query}'")
                        print(f"      New query: '{refined}'")
                        scene.image_search_query = refined
                        scene.final_asset_path = None  # Force re-fetch
                        break
        else:
            print(f"    Scene {scene_id}: {relevance}/5  {status}")

    return total_scenes, failed_scenes, any_failed


async def image_critic_node(state: AgentState):
    """
    Evaluates photographer_storyboards using Gemini.
    - If images exist: uses Gemini Vision (multimodal) to evaluate actual images.
    - If no images: falls back to text-only query evaluation.
    - If relevance < PASS_THRESHOLD for any scene: updates queries for photographer retry.
    """
    def sync_critic():
        storyboards = state.get("photographer_storyboards", [])
        retry_count = state.get("image_critic_retry_count", 0)

        print("\n" + "=" * 60)
        print(f"  IMAGE CRITIC (MULTIMODAL)  |  Attempt {retry_count + 1}/{MAX_RETRIES + 1}  |  Threshold: {PASS_THRESHOLD}/5")
        print("=" * 60)

        if not storyboards:
            print("  No storyboards to evaluate. Skipping.")
            print("=" * 60 + "\n")
            return {
                "image_critic_feedback": None,
                "image_critic_retry_count": 0,
                "photographer_storyboards": storyboards,
            }

        if retry_count >= MAX_RETRIES:
            print(f"  Max retries ({MAX_RETRIES}) reached. FORCE-PASSING.")
            print("=" * 60 + "\n")
            return {
                "image_critic_feedback": None,
                "image_critic_retry_count": retry_count,
                "photographer_storyboards": storyboards,
            }

        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            print("  ERROR: No GEMINI_API_KEY. Skipping.")
            print("=" * 60 + "\n")
            return {
                "image_critic_feedback": None,
                "image_critic_retry_count": retry_count,
                "photographer_storyboards": storyboards,
            }

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.1, google_api_key=gemini_key
        )

        any_failed = False
        total_scenes = 0
        failed_scenes = 0

        for sb_idx, sb in enumerate(storyboards):
            print(f"\n  [{sb_idx + 1}/{len(storyboards)}] '{sb.title}'")

            # Separate scenes into those with images and those without
            scenes_with_images = []
            scenes_without_images = []

            for scene in sb.scenes:
                encoded = _encode_image_safe(scene.final_asset_path)
                if encoded:
                    scenes_with_images.append((scene, encoded))
                else:
                    scenes_without_images.append(scene)

            # --- Multimodal evaluation for scenes WITH images ---
            if scenes_with_images:
                print(f"    Evaluating {len(scenes_with_images)} scene(s) with VISION (multimodal)...")
                content_parts = [
                    {"type": "text", "text": "Evaluate these scenes. Each scene includes its narration text and the actual image:\n\n"}
                ]
                for scene, encoded in scenes_with_images:
                    content_parts.append({
                        "type": "text",
                        "text": f"--- Scene {scene.id} ---\nNarration: \"{scene.subtitle_text}\"\nSearch query used: \"{scene.image_search_query}\"\nImage:"
                    })
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}
                    })

                messages = [
                    SystemMessage(content=MULTIMODAL_CRITIC_PROMPT),
                    HumanMessage(content=content_parts),
                ]

                try:
                    response = llm.invoke(messages)
                    result = _parse_evaluations(response.content)
                    total_scenes, failed_scenes, any_failed = _apply_evaluations(
                        result, sb, total_scenes, failed_scenes, any_failed
                    )
                except Exception as e:
                    print(f"    VISION ERROR: {e}. Falling back to text-only for these scenes.")
                    scenes_without_images.extend([s for s, _ in scenes_with_images])
                    scenes_with_images = []

            # --- Text-only evaluation for scenes WITHOUT images ---
            if scenes_without_images:
                print(f"    Evaluating {len(scenes_without_images)} scene(s) with TEXT-ONLY (no image downloaded)...")
                scene_descriptions = []
                for scene in scenes_without_images:
                    scene_descriptions.append({
                        "scene_id": scene.id,
                        "subtitle_text": scene.subtitle_text,
                        "image_search_query": scene.image_search_query or "news",
                    })

                messages = [
                    SystemMessage(content=TEXT_ONLY_CRITIC_PROMPT),
                    HumanMessage(content=f"Scenes to evaluate:\n{json.dumps(scene_descriptions, indent=2)}"),
                ]

                try:
                    response = llm.invoke(messages)
                    result = _parse_evaluations(response.content)
                    total_scenes, failed_scenes, any_failed = _apply_evaluations(
                        result, sb, total_scenes, failed_scenes, any_failed
                    )
                except Exception as e:
                    print(f"    TEXT ERROR: {e}. Passing by default.")

        print(f"\n  {'─' * 40}")
        print(f"  RESULT: {total_scenes - failed_scenes}/{total_scenes} scenes passed  |  {failed_scenes} failed")

        if any_failed:
            print(f"  ACTION: Routing back to Photographer (retry {retry_count + 1}/{MAX_RETRIES})")
            print("=" * 60 + "\n")
            return {
                "image_critic_feedback": "Some images were irrelevant. Queries updated.",
                "image_critic_retry_count": retry_count + 1,
                "photographer_storyboards": storyboards,
            }

        print(f"  ACTION: All scenes approved. Proceeding to Join Assets.")
        print("=" * 60 + "\n")
        return {
            "image_critic_feedback": None,
            "image_critic_retry_count": retry_count,
            "photographer_storyboards": storyboards,
        }

    return await asyncio.to_thread(sync_critic)
