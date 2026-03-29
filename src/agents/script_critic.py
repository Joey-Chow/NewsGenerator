import os
import json
import re
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import AgentState

MAX_RETRIES = 2
PASS_THRESHOLD = 4.0

CRITIC_SYSTEM_PROMPT = """
You are a professional news script quality critic. You will be given a news video storyboard
(a title and a list of scenes with spoken subtitles) and must evaluate it on three criteria.

Respond ONLY with a valid JSON object in this exact format:
{
  "accuracy": <integer 1-5>,
  "coherence": <integer 1-5>,
  "engagement": <integer 1-5>,
  "critique": "<one or two sentences explaining any weaknesses>"
}

Scoring rubric:
- accuracy (1-5): Are the facts plausible and internally consistent? Does the script avoid obvious errors or contradictions?
- coherence (1-5): Do the scenes flow logically from one to the next? Is there a clear narrative arc?
- engagement (1-5): Is the language compelling? Does it hook the viewer and maintain interest?

A score of 5 means excellent; 1 means very poor. If all criteria are strong, keep the critique brief and positive.
"""


def _evaluate_storyboard(llm, storyboard) -> dict:
    """Send one storyboard to the LLM and return parsed scores."""
    scenes_text = "\n".join(
        [f"Scene {s.id}: {s.subtitle_text}" for s in storyboard.scenes]
    )
    user_content = f"Title: {storyboard.title}\n\nScenes:\n{scenes_text}"

    messages = [
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    content = response.content

    # Extract JSON from the response
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)

    return json.loads(content)


async def script_critic_node(state: AgentState):
    """
    Critic agent that scores each draft storyboard on accuracy, coherence, and engagement.
    - If retry_count >= MAX_RETRIES, force-passes (returns feedback=None).
    - If any storyboard < PASS_THRESHOLD, sets script_critic_feedback and increments retry_count.
    - If all storyboards >= PASS_THRESHOLD, clears feedback (None) and passes through.
    """

    def sync_critic():
        retry_count = state.get("script_critic_retry_count", 0)
        draft_storyboards = state.get("draft_storyboards", [])

        print("\n" + "=" * 60)
        print(f"  SCRIPT CRITIC  |  Attempt {retry_count + 1}/{MAX_RETRIES + 1}  |  Threshold: {PASS_THRESHOLD}")
        print("=" * 60)

        # Force-pass if we've already retried the maximum number of times
        if retry_count >= MAX_RETRIES:
            print(f"  Max retries ({MAX_RETRIES}) reached. FORCE-PASSING.")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": None,
                "script_critic_retry_count": retry_count,
            }

        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            print("  ERROR: No GEMINI_API_KEY found. Skipping.")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": None,
                "script_critic_retry_count": retry_count,
            }

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.2,
            google_api_key=gemini_key,
        )

        all_scores = []
        all_critiques = []

        for idx, storyboard in enumerate(draft_storyboards):
            print(f"\n  [{idx + 1}/{len(draft_storyboards)}] '{storyboard.title}'")
            try:
                result = _evaluate_storyboard(llm, storyboard)
                accuracy = result.get("accuracy", 3)
                coherence = result.get("coherence", 3)
                engagement = result.get("engagement", 3)
                critique = result.get("critique", "")

                avg = (accuracy + coherence + engagement) / 3.0
                passed = avg >= PASS_THRESHOLD
                status = "PASS" if passed else "FAIL"

                all_scores.append(avg)
                all_critiques.append(
                    f"[{status}] '{storyboard.title}': accuracy={accuracy}, "
                    f"coherence={coherence}, engagement={engagement} (avg={avg:.2f}). {critique}"
                )

                print(f"    Accuracy:   {accuracy}/5")
                print(f"    Coherence:  {coherence}/5")
                print(f"    Engagement: {engagement}/5")
                print(f"    Average:    {avg:.2f}  →  {status}")
                if not passed and critique:
                    print(f"    Critique:   {critique}")

            except Exception as e:
                print(f"    ERROR: {e}")
                all_scores.append(3.0)
                all_critiques.append(f"[ERROR] '{storyboard.title}': evaluation failed ({e}).")

        if not all_scores:
            print("\n  No storyboards to evaluate. Force-passing.")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": None,
                "script_critic_retry_count": retry_count,
            }

        # Per-storyboard enforcement: fail if ANY storyboard scores below threshold
        failed_indices = [i for i, score in enumerate(all_scores) if score < PASS_THRESHOLD]
        failed_critiques = [all_critiques[i] for i in failed_indices]
        passed_count = len(all_scores) - len(failed_indices)

        print(f"\n  {'─' * 40}")
        print(f"  RESULT: {passed_count}/{len(all_scores)} passed  |  {len(failed_indices)} failed")

        if failed_indices:
            combined_critique = "\n".join(failed_critiques)
            min_score = min(all_scores)
            feedback = (
                f"{len(failed_indices)} storyboard(s) below threshold (lowest={min_score:.2f}/{PASS_THRESHOLD}).\n"
                f"Please revise based on the following critique:\n{combined_critique}"
            )
            print(f"  Failed indices: {failed_indices}")
            print(f"  ACTION: Routing back to Editor to regenerate only failed storyboards (retry {retry_count + 1}/{MAX_RETRIES})")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": feedback,
                "script_critic_retry_count": retry_count + 1,
                "script_critic_failed_indices": failed_indices,
            }
        else:
            print(f"  ACTION: All storyboards approved. Proceeding to Human Review.")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": None,
                "script_critic_retry_count": retry_count,
                "script_critic_failed_indices": None,
            }

    return await asyncio.to_thread(sync_critic)
