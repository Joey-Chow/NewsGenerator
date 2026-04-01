import os
import json
import re
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.state import AgentState

MAX_RETRIES = 2
PASS_THRESHOLD = 4.0

CRITIC_SYSTEM_PROMPT = """You are a professional news script quality critic. You will be given:
1. The ORIGINAL SOURCE ARTICLE that the storyboard was generated from.
2. A news video STORYBOARD (title + scenes with spoken subtitles).

Your job: evaluate the storyboard against the source article. Focus ONLY on problems that would
noticeably hurt the viewer experience. Do NOT nitpick minor wording choices or flag scenes
that are already good enough.

Respond ONLY with a valid JSON object in this exact format:
{
  "accuracy": <integer 1-5>,
  "coherence": <integer 1-5>,
  "engagement": <integer 1-5>,
  "scene_feedback": [
    {
      "scene_id": <int>,
      "dimension": "<which dimension this fixes: accuracy | coherence | engagement>",
      "issue": "<what is wrong — be specific>",
      "suggestion": "<concrete rewrite of the full scene subtitle_text>"
    }
  ],
  "overall_critique": "<1-2 sentence summary of the main problems>"
}

Scoring rubric:
- accuracy (1-5): Are the facts faithful to the source article? Flag ONLY: factual errors,
  misquotes, fabricated claims, or critical omissions that change the story's meaning.
  Do NOT flag: minor simplifications, paraphrasing, or omitting non-essential details.
- coherence (1-5): Do the scenes flow logically? Is there a clear narrative arc
  (hook -> explanation -> outlook)? Flag ONLY: missing transitions that confuse the viewer,
  scenes in the wrong order, or a missing conclusion.
  Do NOT flag: transitions that work but could theoretically be smoother.
- engagement (1-5): Is the language compelling and broadcast-ready? Flag ONLY: flat/robotic
  openings that fail to hook, or scenes that read like a dry bullet-point list.
  Do NOT flag: scenes that are clear and professional but not maximally dramatic.

IMPORTANT scoring guidelines:
- A score of 4 means "good, broadcast-ready." Most competent scripts should score 4.
  Only give 3 or below if there is a CLEAR, SPECIFIC problem you can point to.
- Do NOT give a low engagement score and then only provide accuracy/coherence suggestions.
  If you score engagement below 4, your scene_feedback MUST include at least one entry
  with "dimension": "engagement" that provides an engaging rewrite.
- A 5 means exceptional. A 4 is the normal "good" score. Do not treat 4 as mediocre.

scene_feedback rules:
- ONLY include scenes with problems that would noticeably hurt the final video.
- Maximum 3 scenes per storyboard — focus on the worst offenders, not everything.
- Each "suggestion" must be a COMPLETE rewritten subtitle_text, ready to drop in.
- The "dimension" field must match why the scene was flagged.
- If the storyboard is solid, return an empty array [].
"""


def _evaluate_storyboard(llm, storyboard, source_article: str | None, retry_count: int = 0) -> dict:
    """Send one storyboard + its source article to the LLM and return parsed scores."""
    scenes_text = "\n".join(
        [f"Scene {s.id}: {s.subtitle_text}" for s in storyboard.scenes]
    )

    parts = []
    if source_article:
        parts.append(f"=== ORIGINAL SOURCE ARTICLE ===\n{source_article[:10000]}\n")
    parts.append(f"=== STORYBOARD ===\nTitle: {storyboard.title}\n\nScenes:\n{scenes_text}")

    if retry_count > 0:
        parts.append(
            f"\n=== NOTE ===\n"
            f"This is revision #{retry_count}. The storyboard has already been revised based on "
            f"previous feedback. Evaluate it fresh — do NOT re-flag issues that have been fixed. "
            f"Only flag remaining problems that are genuinely bad."
        )

    messages = [
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content="\n".join(parts)),
    ]

    response = llm.invoke(messages)
    content = response.content

    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)

    return json.loads(content)


def _format_feedback_for_editor(storyboard, result: dict) -> str:
    """Format critic output into structured feedback the editor can act on."""
    lines = []
    lines.append(f"Storyboard: '{storyboard.title}'")
    lines.append(f"Scores: accuracy={result.get('accuracy')}, coherence={result.get('coherence')}, engagement={result.get('engagement')}")

    overall = result.get("overall_critique", "")
    if overall:
        lines.append(f"Overall: {overall}")

    scene_feedback = result.get("scene_feedback", [])
    if scene_feedback:
        lines.append("\nScene-level issues:")
        for sf in scene_feedback:
            sid = sf.get("scene_id", "?")
            issue = sf.get("issue", "")
            suggestion = sf.get("suggestion", "")
            lines.append(f"  Scene {sid}:")
            lines.append(f"    Problem: {issue}")
            lines.append(f"    Fix: {suggestion}")

    return "\n".join(lines)


async def script_critic_node(state: AgentState):
    """
    Critic agent that scores each draft storyboard on accuracy, coherence, and engagement.
    Receives the original source article for fact-checking.
    Returns per-scene, actionable feedback for the editor to revise.
    """

    def sync_critic():
        retry_count = state.get("script_critic_retry_count", 0)
        draft_storyboards = state.get("draft_storyboards", [])
        scraped_articles = state.get("scraped_articles", [])

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
        all_feedback = []

        for idx, storyboard in enumerate(draft_storyboards):
            print(f"\n  [{idx + 1}/{len(draft_storyboards)}] '{storyboard.title}'")

            # Get the source article for this storyboard (matched by index)
            source_text = None
            if idx < len(scraped_articles):
                article = scraped_articles[idx]
                source_text = article.get("raw_news", "")

            try:
                result = _evaluate_storyboard(llm, storyboard, source_text, retry_count)
                accuracy = result.get("accuracy", 3)
                coherence = result.get("coherence", 3)
                engagement = result.get("engagement", 3)
                overall_critique = result.get("overall_critique", "")
                scene_feedback = result.get("scene_feedback", [])

                avg = (accuracy + coherence + engagement) / 3.0
                passed = avg >= PASS_THRESHOLD
                status = "PASS" if passed else "FAIL"

                all_scores.append(avg)

                print(f"    Accuracy:   {accuracy}/5")
                print(f"    Coherence:  {coherence}/5")
                print(f"    Engagement: {engagement}/5")
                print(f"    Average:    {avg:.2f}  →  {status}")

                if not passed:
                    print(f"    Critique:   {overall_critique}")
                    if scene_feedback:
                        for sf in scene_feedback:
                            print(f"    Scene {sf.get('scene_id', '?')}: {sf.get('issue', '')}")
                            print(f"      → {sf.get('suggestion', '')}")

                    all_feedback.append(_format_feedback_for_editor(storyboard, result))
                else:
                    all_feedback.append(None)

            except Exception as e:
                print(f"    ERROR: {e}")
                all_scores.append(3.0)
                all_feedback.append(None)

        if not all_scores:
            print("\n  No storyboards to evaluate. Force-passing.")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": None,
                "script_critic_retry_count": retry_count,
            }

        # Per-storyboard enforcement: fail if ANY storyboard scores below threshold
        failed_indices = [i for i, score in enumerate(all_scores) if score < PASS_THRESHOLD]
        passed_count = len(all_scores) - len(failed_indices)

        print(f"\n  {'─' * 40}")
        print(f"  RESULT: {passed_count}/{len(all_scores)} passed  |  {len(failed_indices)} failed")

        if failed_indices:
            # Combine only the feedback for failed storyboards
            combined_feedback = "\n\n---\n\n".join(
                fb for i, fb in enumerate(all_feedback) if i in failed_indices and fb
            )
            print(f"  Failed indices: {failed_indices}")
            print(f"  ACTION: Routing back to Editor to regenerate only failed storyboards (retry {retry_count + 1}/{MAX_RETRIES})")
            print("=" * 60 + "\n")
            return {
                "script_critic_feedback": combined_feedback,
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
