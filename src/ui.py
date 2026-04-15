
import gradio as gr
import asyncio
import os
import sys
import json
import csv
import contextlib
import inspect
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from langgraph.types import Command
from src.graph import build_graph

load_dotenv()

# --- Globals ---
class UIState:
    def __init__(self):
        self.logs = "--- Serious News Automation Dashboard Ready ---\n"
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        serde = JsonPlusSerializer(allowed_msgpack_modules=[("src.state", "Storyboard")])
        self.app = build_graph(checkpointer=MemorySaver(serde=serde))
        self.config = {"configurable": {"thread_id": "gradio_thread"}}

ui_state = UIState()

# --- Logging (Zero-Loading) ---
class StreamToGradio:
    def write(self, data):
        if data:
            ui_state.logs += str(data)
            if len(ui_state.logs) > 50000:
                ui_state.logs = ui_state.logs[-50000:]
    def flush(self): pass

log_stream = StreamToGradio()

@contextlib.contextmanager
def capture_output():
    old_stdout = sys.stdout
    sys.stdout = log_stream
    try:
        yield
    finally:
        sys.stdout = old_stdout

def get_logs():
    """Gradio polling function for text output.
    Crucially, any component using this via 'every' will NOT show a loading spinner.
    """
    return ui_state.logs

# --- Data Fetching ---
def get_storyboard_list():
    """Helper to detect available storyboard files on disk."""
    story_dir = "output/storyboard"
    if not os.path.exists(story_dir):
        return []
    files = [f for f in os.listdir(story_dir) if f.endswith(".json")]
    # Ensure natural sorting (e.g., storyboard_1.json, storyboard_2.json)
    files.sort(key=lambda x: int(''.join(filter(str.isdigit, x))) if any(c.isdigit() for c in x) else 0)
    return files

def load_selected_storyboard(filename):
    """Loads a specific storyboard JSON file for display."""
    if not filename or filename == "Refresh list...":
        return {}
    path = os.path.join("output/storyboard", filename)
    try:
        with open(path, "r", encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"error": "Failed to load file"}

def get_scene_media_choices():
    snapshot = ui_state.app.get_state(ui_state.config)
    state = snapshot.values if snapshot else {}
    storyboards = state.get("ready_to_render_storyboards", []) or state.get("draft_storyboards", [])
    
    choices = []
    for sb_idx, sb in enumerate(storyboards):
        for scene in sb.scenes:
            choices.append(f"Storyboard {sb_idx+1} - Scene {scene.id}")
    return choices

def load_scene_media(choice):
    if not choice:
        return None, None
    snapshot = ui_state.app.get_state(ui_state.config)
    state = snapshot.values if snapshot else {}
    storyboards = state.get("ready_to_render_storyboards", []) or state.get("draft_storyboards", [])
    
    for sb_idx, sb in enumerate(storyboards):
        for scene in sb.scenes:
            label = f"Storyboard {sb_idx+1} - Scene {scene.id}"
            if label == choice:
                audio_path = scene.audio_path if scene.audio_path and os.path.exists(scene.audio_path) else None
                img_path = scene.final_asset_path if scene.final_asset_path and os.path.exists(scene.final_asset_path) else None
                return audio_path, img_path
    return None, None

def fetch_media_state():
    """Fetches text, lists, and the default auto-selected media."""
    snapshot = ui_state.app.get_state(ui_state.config)
    state = snapshot.values if snapshot else {}
    
    choices = get_scene_media_choices()
    val = choices[0] if choices else None
    audio, image = load_scene_media(val)
    
    video_file = state.get("generated_segments", [])[-1] if state.get("generated_segments") else None
    
    raw_news = ""
    if "scraped_articles" in state and state["scraped_articles"]:
        raw_news = "\n\n".join([f"Source: {a.get('url')}\nContent: {a.get('raw_news')[:1000]}..." for a in state["scraped_articles"]])

    youtube_url = state.get("youtube_url", "")
    return raw_news, gr.update(choices=choices, value=val), audio, image, video_file, youtube_url

# --- Evaluation Helpers ---
def load_eval_scores(version: str) -> list:
    """Load scores CSV for a given version (baseline or advanced)."""
    csv_path = f"eval/results/{version}/scores.csv"
    if not os.path.exists(csv_path):
        return []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_eval_metadata(version: str) -> str:
    """Load evaluation run metadata as formatted markdown."""
    meta_path = f"eval/results/{version}/metadata.json"
    if not os.path.exists(meta_path):
        return "No run metadata found."
    with open(meta_path) as f:
        meta = json.load(f)
    return (
        f"**Version:** {meta.get('version', 'N/A')}\n\n"
        f"**Runtime:** {meta.get('elapsed_seconds', 'N/A')}s\n\n"
        f"**Storyboards:** {meta.get('num_storyboards', 'N/A')}\n\n"
        f"**Script Critic Retries:** {meta.get('script_critic_retry_count', 'N/A')}\n\n"
        f"**Image Critic Retries:** {meta.get('image_critic_retry_count', 'N/A')}\n\n"
        f"**Timestamp:** {meta.get('timestamp', 'N/A')}"
    )


def build_comparison_table() -> str:
    """Build a markdown table comparing baseline vs advanced scores."""
    baseline = load_eval_scores("baseline")
    advanced = load_eval_scores("advanced")

    if not baseline and not advanced:
        return (
            "No evaluation results found yet.\n\nRun the evaluation first:\n"
            "```\npython -m eval.run_eval --version baseline\n"
            "python -m eval.run_eval --version advanced\n```"
        )

    n_b = len(baseline)
    n_a = len(advanced)
    summary = f"**Sample size:** Baseline={n_b}, Advanced={n_a} articles\n\n"

    header = "| Metric | Baseline | Advanced | Delta |\n|--------|----------|----------|-------|\n"
    rows = []
    for label, key in [
        ("Accuracy", "accuracy"),
        ("Coherence", "coherence"),
        ("Engagement", "engagement"),
        ("Image Relevance", "avg_image_relevance"),
    ]:
        b_vals = [float(r[key]) for r in baseline if key in r] if baseline else []
        a_vals = [float(r[key]) for r in advanced if key in r] if advanced else []
        b_avg = sum(b_vals) / len(b_vals) if b_vals else 0
        a_avg = sum(a_vals) / len(a_vals) if a_vals else 0
        delta = a_avg - b_avg
        sign = "+" if delta > 0 else ""
        rows.append(f"| {label} | {b_avg:.2f} | {a_avg:.2f} | {sign}{delta:.2f} |")

    return summary + header + "\n".join(rows)


def build_score_chart():
    """Grouped bar chart comparing baseline vs advanced on all quality dimensions."""
    baseline = load_eval_scores("baseline")
    advanced = load_eval_scores("advanced")

    metrics = [
        ("Accuracy", "accuracy"),
        ("Coherence", "coherence"),
        ("Engagement", "engagement"),
        ("Image Relevance", "avg_image_relevance"),
    ]

    labels, b_avgs, a_avgs = [], [], []
    for label, key in metrics:
        b_vals = [float(r[key]) for r in baseline if key in r] if baseline else []
        a_vals = [float(r[key]) for r in advanced if key in r] if advanced else []
        labels.append(label)
        b_avgs.append(sum(b_vals) / len(b_vals) if b_vals else 0)
        a_avgs.append(sum(a_vals) / len(a_vals) if a_vals else 0)

    fig = go.Figure(data=[
        go.Bar(name="Baseline", x=labels, y=b_avgs, marker_color="#636EFA"),
        go.Bar(name="Advanced", x=labels, y=a_avgs, marker_color="#EF553B"),
    ])
    fig.update_layout(
        barmode="group",
        title="Script & Image Quality: Baseline vs Advanced",
        yaxis=dict(range=[0, 5], title="Score (1–5)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )
    return fig


def build_retry_chart():
    """Bar chart comparing critic retry counts between versions."""
    b_script = b_image = a_script = a_image = 0

    b_path = "eval/results/baseline/metadata.json"
    a_path = "eval/results/advanced/metadata.json"

    if os.path.exists(b_path):
        with open(b_path) as f:
            m = json.load(f)
            b_script = m.get("script_critic_retry_count", 0)
            b_image = m.get("image_critic_retry_count", 0)

    if os.path.exists(a_path):
        with open(a_path) as f:
            m = json.load(f)
            a_script = m.get("script_critic_retry_count", 0)
            a_image = m.get("image_critic_retry_count", 0)

    fig = go.Figure(data=[
        go.Bar(name="Baseline", x=["Script Retries", "Image Retries"],
               y=[b_script, b_image], marker_color="#636EFA"),
        go.Bar(name="Advanced", x=["Script Retries", "Image Retries"],
               y=[a_script, a_image], marker_color="#EF553B"),
    ])
    fig.update_layout(
        barmode="group",
        title="Critic Agent Retry Counts",
        yaxis=dict(title="Retries"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350,
    )
    return fig


def build_runtime_chart():
    """Bar chart comparing total pipeline runtime."""
    b_time = a_time = 0

    b_path = "eval/results/baseline/metadata.json"
    a_path = "eval/results/advanced/metadata.json"

    if os.path.exists(b_path):
        with open(b_path) as f:
            b_time = json.load(f).get("elapsed_seconds", 0)

    if os.path.exists(a_path):
        with open(a_path) as f:
            a_time = json.load(f).get("elapsed_seconds", 0)

    fig = go.Figure(data=[
        go.Bar(
            x=["Baseline", "Advanced"],
            y=[b_time, a_time],
            marker_color=["#636EFA", "#EF553B"],
        )
    ])
    fig.update_layout(
        title="Pipeline Runtime (seconds)",
        yaxis=dict(title="Seconds"),
        height=350,
    )
    return fig


def _short_title(title: str, max_len: int = 28) -> str:
    return title if len(title) <= max_len else title[:max_len].rstrip() + "…"


def build_per_storyboard_chart():
    """2×2 subplot grid: one panel per metric, each showing baseline vs advanced per article."""
    baseline = load_eval_scores("baseline")
    advanced = load_eval_scores("advanced")

    if not baseline and not advanced:
        fig = go.Figure()
        fig.add_annotation(text="No results yet", showarrow=False, font=dict(size=16))
        return fig

    metrics = [
        ("Accuracy", "accuracy"),
        ("Coherence", "coherence"),
        ("Engagement", "engagement"),
        ("Image Relevance", "avg_image_relevance"),
    ]

    n_articles = max(len(baseline), len(advanced))

    b_ticks = [f"S{int(r['storyboard_idx']) + 1}" for r in baseline]
    a_ticks = [f"S{int(r['storyboard_idx']) + 1}" for r in advanced]
    b_hover = [r["title"] for r in baseline]
    a_hover = [r["title"] for r in advanced]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[m[0] for m in metrics],
        vertical_spacing=0.20,
        horizontal_spacing=0.12,
    )

    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
    show_legend = True

    for (label, key), (row, col) in zip(metrics, positions):
        b_vals = [float(r[key]) if key in r else 0 for r in baseline]
        a_vals = [float(r[key]) if key in r else 0 for r in advanced]

        fig.add_trace(go.Bar(
            name="Baseline", x=b_ticks, y=b_vals,
            customdata=b_hover,
            hovertemplate="%{customdata}<br>Score: %{y:.2f}<extra>Baseline</extra>",
            marker_color="#636EFA", showlegend=show_legend,
            legendgroup="baseline",
        ), row=row, col=col)

        fig.add_trace(go.Bar(
            name="Advanced", x=a_ticks, y=a_vals,
            customdata=a_hover,
            hovertemplate="%{customdata}<br>Score: %{y:.2f}<extra>Advanced</extra>",
            marker_color="#EF553B", showlegend=show_legend,
            legendgroup="advanced",
        ), row=row, col=col)

        show_legend = False
        fig.update_yaxes(range=[0, 5], row=row, col=col)
        fig.update_xaxes(tickangle=0, tickfont=dict(size=8), row=row, col=col)

    fig.update_layout(
        barmode="group",
        title="Per-Storyboard Scores: Baseline vs Advanced (hover for article title)",
        height=640,
        legend=dict(orientation="h", yanchor="bottom", y=1.04),
        margin=dict(b=30, t=60),
    )
    return fig


def get_storyboard_choices() -> list:
    """Return dropdown choices based on available scores."""
    baseline = load_eval_scores("baseline")
    advanced = load_eval_scores("advanced")
    rows = baseline if len(baseline) >= len(advanced) else advanced
    return [f"S{int(r['storyboard_idx'])+1}: {r['title']}" for r in rows]


def load_storyboard_detail(choice: str) -> tuple:
    """Return (baseline_md, advanced_md) for the selected storyboard choice."""
    if not choice:
        return "No selection.", "No selection."

    idx = int(choice.split(":")[0][1:]) - 1  # "S3: ..." → 2

    def fmt(rows, version):
        row = next((r for r in rows if int(r["storyboard_idx"]) == idx), None)
        if not row:
            return f"_{version} result not found for this storyboard._"
        img_scores = json.loads(row.get("image_scores", "[]"))
        img_str = ", ".join(str(s) if s is not None else "—" for s in img_scores)
        return (
            f"**Title:** {row['title']}\n\n"
            f"**Accuracy:** {row['accuracy']} / 5\n\n"
            f"**Coherence:** {row['coherence']} / 5\n\n"
            f"**Engagement:** {row['engagement']} / 5\n\n"
            f"**Avg Image Relevance:** {row['avg_image_relevance']}\n\n"
            f"**Image Scores (per scene):** {img_str}\n\n"
            f"**Scenes:** {row['num_scenes']}  |  **Images found:** {row['num_images_found']}\n\n"
            f"**Script Reasoning:**\n\n> {row.get('script_reasoning', '—')}"
        )

    b_rows = load_eval_scores("baseline")
    a_rows = load_eval_scores("advanced")
    return fmt(b_rows, "Baseline"), fmt(a_rows, "Advanced")


def _load_article_categories() -> dict:
    """Map storyboard index to category from benchmark article URLs."""
    bench_path = "eval/benchmark_articles.json"
    if not os.path.exists(bench_path):
        return {}
    with open(bench_path) as f:
        articles = json.load(f)
    cats = {}
    for i, a in enumerate(articles):
        url = a.get("url", "")
        parts = url.split("theglobeandmail.com/")
        if len(parts) > 1:
            cat = parts[1].split("/")[0].capitalize()
        else:
            cat = "Other"
        cats[i] = cat
    return cats


def build_per_storyboard_table() -> str:
    """Markdown table grouped by category with per-category and overall averages."""
    baseline = load_eval_scores("baseline")
    advanced = load_eval_scores("advanced")

    if not baseline and not advanced:
        return "_No results yet._"

    b_by_idx = {int(r["storyboard_idx"]): r for r in baseline}
    a_by_idx = {int(r["storyboard_idx"]): r for r in advanced}
    all_indices = sorted(set(b_by_idx) | set(a_by_idx))

    categories = _load_article_categories()
    n_articles = len(all_indices)
    title_len = 25 if n_articles > 10 else 30

    # Group indices by category
    from collections import OrderedDict
    groups = OrderedDict()
    for idx in all_indices:
        cat = categories.get(idx, "Other")
        groups.setdefault(cat, []).append(idx)

    header = (
        "| # | Article | B.Acc | A.Acc | B.Coh | A.Coh | B.Eng | A.Eng | B.Img | A.Img |\n"
        "|---|---------|-------|-------|-------|-------|-------|-------|-------|-------|\n"
    )

    def val(d, key):
        return f"{float(d[key]):.2f}" if d and key in d else "—"

    def avg_rows(b_list, a_list, label):
        """Compute average row from lists of score dicts."""
        def avg_v(lst, key):
            vals = [float(r[key]) for r in lst if r and key in r]
            return f"**{sum(vals)/len(vals):.2f}**" if vals else "—"
        return (
            f"| | **{label}** "
            f"| {avg_v(b_list,'accuracy')} | {avg_v(a_list,'accuracy')} "
            f"| {avg_v(b_list,'coherence')} | {avg_v(a_list,'coherence')} "
            f"| {avg_v(b_list,'engagement')} | {avg_v(a_list,'engagement')} "
            f"| {avg_v(b_list,'avg_image_relevance')} | {avg_v(a_list,'avg_image_relevance')} |"
        )

    rows = []
    for cat, indices in groups.items():
        rows.append(f"| | **{cat}** | | | | | | | | |")
        cat_b, cat_a = [], []
        for idx in indices:
            b = b_by_idx.get(idx)
            a = a_by_idx.get(idx)
            if b: cat_b.append(b)
            if a: cat_a.append(a)
            title = _short_title((b or a).get("title", "Unknown"), title_len)
            rows.append(
                f"| S{idx+1} | {title} "
                f"| {val(b,'accuracy')} | {val(a,'accuracy')} "
                f"| {val(b,'coherence')} | {val(a,'coherence')} "
                f"| {val(b,'engagement')} | {val(a,'engagement')} "
                f"| {val(b,'avg_image_relevance')} | {val(a,'avg_image_relevance')} |"
            )
        rows.append(avg_rows(cat_b, cat_a, f"{cat} Avg"))

    # Overall average
    rows.append(avg_rows(
        [b_by_idx[i] for i in all_indices if i in b_by_idx],
        [a_by_idx[i] for i in all_indices if i in a_by_idx],
        "Overall Avg",
    ))

    return header + "\n".join(rows)


# --- Operations ---
def execute_node_logic(node_name):
    from src.agents.photographer import batch_photographer_node
    from src.agents.reporter import batch_reporter_node
    from src.agents.editor import batch_editor_node
    from src.agents.scraper import batch_scraper_node
    from src.agents.batch_renderer import batch_video_renderer_node
    from src.agents.youtuber import youtuber_node
    from src.agents.ingest import batch_human_script_review_node

    mapping = {
        "Scraper": batch_scraper_node, 
        "Editor": batch_editor_node,
        "ScriptReview": batch_human_script_review_node,
        "Photographer": batch_photographer_node, 
        "Reporter": batch_reporter_node,
        "Renderer": batch_video_renderer_node, 
        "Youtuber": youtuber_node
    }

    with capture_output():
        try:
            print(f"▶️ Executing: {node_name}...")
            snapshot = ui_state.app.get_state(ui_state.config)
            node_func = mapping[node_name]
            
            if inspect.iscoroutinefunction(node_func):
                res = asyncio.run(node_func(snapshot.values))
            else:
                res = node_func(snapshot.values)
            
            ui_state.app.update_state(ui_state.config, res)
            print(f"✅ Node {node_name} finished.")
        except Exception as e:
            print(f"❌ Error in {node_name}: {e}")


# --- Targeted Handlers ---
def h_run_scraper():
    execute_node_logic("Scraper")
    news, _, _, _, _, _ = fetch_media_state()
    return news

def h_run_editor():
    execute_node_logic("Editor")
    choices = get_storyboard_list()
    val = choices[0] if choices else None
    json_data = load_selected_storyboard(val)
    return gr.update(choices=choices, value=val), json_data

def pipeline_generator(is_start=False, injected_state=None):
    with capture_output():
        snapshot = ui_state.app.get_state(ui_state.config)
        
        # Determine Input
        if not snapshot.next or is_start:
            if is_start:
                print("🚩 Starting Pipeline execution...")
            current_input = {"news_urls": [], "generated_segments": [], "news_url": None}
        else:
            print(f"▶️ Approving and Resuming pipeline (pending node: {snapshot.next})...")
            if injected_state:
                print(f"   -> Injecting state updates: {list(injected_state.keys())}")
                ui_state.app.update_state(ui_state.config, injected_state)
            # Use Command(resume=...) to get past interrupt() calls
            resume_value = injected_state if injected_state else True
            current_input = Command(resume=resume_value)
            
        def pull_ui_state(force_hide_popup=False):
            news, sel_media, aud, img, video, yt_url = fetch_media_state()
            choices_sb = get_storyboard_list()
            val_sb = choices_sb[0] if choices_sb else None
            json_data = load_selected_storyboard(val_sb)
            
            # Check if graph is stuck at a breakpoint pending human approval
            curr_snap = ui_state.app.get_state(ui_state.config)
            is_paused = bool(curr_snap and curr_snap.next)
            
            if force_hide_popup:
                is_paused = False
            
            return (
                news, gr.update(choices=choices_sb, value=val_sb), json_data, 
                sel_media, aud, img, video, yt_url,
                gr.update(visible=is_paused) # Visually toggle the approval banner
            )
            
        # First yield populates existing data instantly, breaking the "blank" loading effect
        # If we are resuming (is_start=False), forcefully hide the modal instantly so it feels responsive!
        yield pull_ui_state(force_hide_popup=not is_start)

        # Isolate Event Loop so LangGraph's async nodes can run without freezing Gradio's main thread
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        agen = ui_state.app.astream(current_input, config=ui_state.config)

        while True:
            # We pump the async generator synchronously in the worker thread
            async def get_next():
                try:
                    return await anext(agen)
                except StopAsyncIteration:
                    return None
                    
            output = loop.run_until_complete(get_next())
            if output is None:
                break

            for node_name, updates in output.items():
                if node_name == "__interrupt__":
                    continue
                print(f"✅ Flow completed node: {node_name}")
            
            # While we are actively iterating the execution stream, we are NEVER paused. 
            # We must aggressively hide the popup, because `snapshot.next` evaluates to True between node steps!
            yield pull_ui_state(force_hide_popup=True)
            
        snapshot = ui_state.app.get_state(ui_state.config)
        if snapshot.next:
            print(f"⏸️ Pipeline paused. Waiting for Manual Approval before: {snapshot.next}")
        else:
            print("🏁 Pipeline fully completed!")
            
        yield pull_ui_state()

def h_run_approve():
    yield from pipeline_generator(is_start=False)

def h_run_revise(prompt_text):
    if not prompt_text or not prompt_text.strip():
        # If they left it empty, just treat it as a normal approve or ignore
        pass
    yield from pipeline_generator(is_start=False, injected_state={"user_feedback": prompt_text.strip()})

def h_run_photographer():
    execute_node_logic("Photographer")
    _, sel, aud, img, _, _ = fetch_media_state()
    return sel, aud, img

def h_run_reporter():
    execute_node_logic("Reporter")
    _, sel, aud, img, _, _ = fetch_media_state()
    return sel, aud, img

def h_run_renderer():
    execute_node_logic("Renderer")
    _, _, _, _, video, _ = fetch_media_state()
    return video

def h_run_youtuber():
    execute_node_logic("Youtuber")
    pass

def h_run_all():
    yield from pipeline_generator(is_start=True)


# --- UI Definitions ---
with gr.Blocks(title="NewsGen Dashboard", theme=gr.themes.Soft()) as demo:
    with gr.Tab("Pipeline Dashboard"):
        gr.Markdown("# 🚀 News Automation Dashboard")

        with gr.Group(visible=False) as approval_panel:
            gr.Markdown("## 🚨 ACTION REQUIRED: Pipeline Paused for Review")
            gr.Markdown("The pipeline has automatically paused at a designated checkpoint. Please review the relevant files locally or adjust settings.")
            prompt_input = gr.Textbox(label="Revision Prompt (Optional)", placeholder="e.g. Change the first news to something else, or make the whole script much funnier...")
            b_revise_popup = gr.Button("🔄 Call LLM to Revise Script (With Changes)", variant="primary")
            gr.Markdown("---")
            b_approve_popup = gr.Button("✅ Confirm & Resume Pipeline (No Changes)", variant="stop")

        with gr.Row():
            with gr.Column(scale=1):
                btn_all = gr.Button("🔥 One-click Generate", variant="primary")
                with gr.Accordion("Step-by-Step Control", open=True):
                    b1 = gr.Button("1. Scraper")
                    b2 = gr.Button("2. Editor")
                    b3 = gr.Button("3. Photographer")
                    b4 = gr.Button("4. Reporter")
                    b5 = gr.Button("5. Renderer")
                    b6 = gr.Button("6. Youtuber")
            with gr.Column(scale=2):
                logs_view = gr.Textbox(label="Terminal Logs", lines=15, interactive=False, value=get_logs, every=1.0, autoscroll=True)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 📰 Scraped Content")
                out_news = gr.Textbox(label="Raw News (Partial)", lines=12)
            with gr.Column(scale=1):
                gr.Markdown("## 📝 Storyboard Viewer")
                story_selector = gr.Dropdown(label="Select Storyboard to View", choices=get_storyboard_list())
                out_story_json = gr.JSON(label="JSON Content")
                story_selector.change(load_selected_storyboard, inputs=[story_selector], outputs=[out_story_json])

        # Vertically stacked layout as requested
        gr.Markdown("---")
        gr.Markdown("## 🎨 Scene Visuals & Audio")
        scene_media_selector = gr.Dropdown(label="Select specific Scene to inspect its Media", choices=get_scene_media_choices())

        out_audio = gr.Audio(label="Latest TTS Segment")
        out_image = gr.Image(label="Scene Asset Image")

        gr.Markdown("## 🎬 Final Result")
        out_video = gr.Video(label="Final Generated Video")
        out_youtube_url = gr.Textbox(label="Live YouTube Link", lines=1, interactive=False)

        # Bind media dropdown
        scene_media_selector.change(load_scene_media, inputs=[scene_media_selector], outputs=[out_audio, out_image])

    with gr.Tab("Evaluation Results"):
        gr.Markdown("# Baseline vs. Advanced Comparison")
        gr.Markdown(
            "Comparing pipeline outputs **without** critic agents (baseline) vs. "
            "**with** script critic + image critic (advanced) on benchmark articles."
        )

        with gr.Row():
            btn_refresh_eval = gr.Button("Refresh Results", variant="primary")

        gr.Markdown("## Average Scores")
        comparison_md = gr.Markdown(value=build_comparison_table())
        score_chart = gr.Plot(value=build_score_chart())

        gr.Markdown("## Per-Storyboard Breakdown")
        per_sb_table = gr.Markdown(value=build_per_storyboard_table())
        per_sb_chart = gr.Plot(value=build_per_storyboard_chart())

        with gr.Row():
            retry_chart = gr.Plot(value=build_retry_chart())
            runtime_chart = gr.Plot(value=build_runtime_chart())

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Baseline Run")
                baseline_meta_md = gr.Markdown(value=load_eval_metadata("baseline"))
            with gr.Column():
                gr.Markdown("### Advanced Run")
                advanced_meta_md = gr.Markdown(value=load_eval_metadata("advanced"))

        gr.Markdown("## Storyboard Detail")
        sb_choices = get_storyboard_choices()
        sb_selector = gr.Dropdown(
            label="Select Storyboard",
            choices=sb_choices,
            value=sb_choices[0] if sb_choices else None,
        )
        _init_b, _init_a = load_storyboard_detail(sb_choices[0] if sb_choices else None)
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Baseline")
                sb_detail_baseline = gr.Markdown(value=_init_b)
            with gr.Column():
                gr.Markdown("### Advanced")
                sb_detail_advanced = gr.Markdown(value=_init_a)

        sb_selector.change(
            fn=load_storyboard_detail,
            inputs=[sb_selector],
            outputs=[sb_detail_baseline, sb_detail_advanced],
        )

        def refresh_eval():
            choices = get_storyboard_choices()
            first = choices[0] if choices else None
            b_detail, a_detail = load_storyboard_detail(first)
            return (
                build_comparison_table(),
                build_score_chart(),
                build_per_storyboard_table(),
                build_per_storyboard_chart(),
                build_retry_chart(),
                build_runtime_chart(),
                load_eval_metadata("baseline"),
                load_eval_metadata("advanced"),
                gr.update(choices=choices, value=first),
                b_detail,
                a_detail,
            )

        btn_refresh_eval.click(
            fn=refresh_eval,
            outputs=[
                comparison_md,
                score_chart,
                per_sb_table,
                per_sb_chart,
                retry_chart,
                runtime_chart,
                baseline_meta_md,
                advanced_meta_md,
                sb_selector,
                sb_detail_baseline,
                sb_detail_advanced,
            ],
        )

    # --- Binder Functions ---
    # Now includes approval_panel to toggle its visibility automatically
    std_all_outputs = [out_news, story_selector, out_story_json, scene_media_selector, out_audio, out_image, out_video, out_youtube_url, approval_panel]

    # We use minimal progress so components aren't aggressively grayed out
    btn_all.click(h_run_all, outputs=std_all_outputs, show_progress="minimal")
    b_approve_popup.click(h_run_approve, outputs=std_all_outputs, show_progress="minimal")
    b_revise_popup.click(h_run_revise, inputs=[prompt_input], outputs=std_all_outputs, show_progress="minimal")

    b1.click(h_run_scraper, outputs=[out_news], show_progress="minimal")
    b2.click(h_run_editor, outputs=[story_selector, out_story_json], show_progress="minimal")
    b3.click(h_run_photographer, outputs=[scene_media_selector, out_audio, out_image], show_progress="minimal")
    b4.click(h_run_reporter, outputs=[scene_media_selector, out_audio, out_image], show_progress="minimal")
    b5.click(h_run_renderer, outputs=[out_video], show_progress="minimal")
    b6.click(h_run_youtuber, show_progress="minimal")

if __name__ == "__main__":

    demo.launch(server_name="0.0.0.0", server_port=7860)
