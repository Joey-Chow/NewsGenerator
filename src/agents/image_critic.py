import os
import json
import re
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import AgentState

MAX_RETRIES = 2
PASS_THRESHOLD = 4

CRITIC_PROMPT = """You are an Image Relevance Critic for a news video pipeline.

You will receive a list of scenes. Each scene has:
- scene_id: integer
- subtitle_text: the spoken narration for that scene
- image_search_query: the query used to find the image
- has_image: whether an image was actually downloaded

For each scene that has an image, evaluate whether the image_search_query is likely to produce an image that is RELEVANT to the subtitle_text.

Score each scene's relevance from 1 to 5:
- 5: Perfect match — query will find exactly what the narration describes
- 4: Good — query is reasonable, minor mismatch
- 3: Acceptable — somewhat related
- 2: Poor — query is too generic or misleading
- 1: Irrelevant — query has no relation to narration

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


async def image_critic_node(state: AgentState):
    """
    Evaluates photographer_storyboards image queries using Gemini.
    If relevance < PASS_THRESHOLD for any scene, updates the search query and sets feedback for photographer retry.
    """
    def sync_critic():
        storyboards = state.get("photographer_storyboards", [])
        retry_count = state.get("image_critic_retry_count", 0)

        print("\n" + "=" * 60)
        print(f"  IMAGE CRITIC  |  Attempt {retry_count + 1}/{MAX_RETRIES + 1}  |  Threshold: {PASS_THRESHOLD}/5")
        print("=" * 60)

        if not storyboards:
            print("  No storyboards to evaluate. Skipping.")
            print("=" * 60 + "\n")
            return {
                "image_critic_feedback": None,
                "image_critic_retry_count": 0,
                "photographer_storyboards": storyboards,
            }

        # Force pass if max retries reached
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
            # Build scene descriptions for the LLM
            scene_descriptions = []
            for scene in sb.scenes:
                scene_descriptions.append({
                    "scene_id": scene.id,
                    "subtitle_text": scene.subtitle_text,
                    "image_search_query": scene.image_search_query or "news",
                    "has_image": bool(scene.final_asset_path),
                })

            print(f"\n  [{sb_idx + 1}/{len(storyboards)}] '{sb.title}'")

            messages = [
                SystemMessage(content=CRITIC_PROMPT),
                HumanMessage(content=f"Scenes to evaluate:\n{json.dumps(scene_descriptions, indent=2)}"),
            ]

            try:
                response = llm.invoke(messages)
                content = response.content

                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

                result = json.loads(content)
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
                                    print(f"      Query:   '{scene.image_search_query}'")
                                    print(f"      Refined: '{refined}'")
                                    scene.image_search_query = refined
                                    scene.final_asset_path = None
                                    break
                    else:
                        print(f"    Scene {scene_id}: {relevance}/5  {status}")

            except Exception as e:
                print(f"    ERROR: {e}. Passing by default.")

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
