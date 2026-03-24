
import gradio as gr
import asyncio
import os
import sys
import json
import contextlib
import inspect
from dotenv import load_dotenv
from src.graph import build_graph

load_dotenv()

# --- Globals ---
class UIState:
    def __init__(self):
        self.logs = "--- Serious News Automation Dashboard Ready ---\n"
        self.app = build_graph()
        self.config = {"configurable": {"thread_id": "gradio_thread"}}

ui_state = UIState()

# --- Logging (Zero-Loading) ---
class StreamToGradio:
    def write(self, data):
        if data:
            # Prepend for real-time terminal feel
            ui_state.logs = str(data) + ui_state.logs
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

# --- Operations ---
def execute_node_logic(node_name):
    from src.agents.photographer import batch_photographer_node
    from src.agents.reporter import batch_reporter_node
    from src.agents.editor import batch_editor_node
    from src.agents.scraper import batch_scraper_node
    from src.agents.batch_renderer import batch_video_renderer_node
    from src.agents.youtuber import youtuber_node
    from src.agents.ingest import batch_human_script_review_node, batch_human_asset_ingest_node

    mapping = {
        "Scraper": batch_scraper_node, 
        "Editor": batch_editor_node,
        "ScriptReview": batch_human_script_review_node,
        "Photographer": batch_photographer_node, 
        "AssetIngest": batch_human_asset_ingest_node,
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

def pipeline_generator(is_start=False):
    with capture_output():
        snapshot = ui_state.app.get_state(ui_state.config)
        
        # Determine Input
        if not snapshot.next or is_start:
            if is_start:
                print("🚩 Starting Pipeline execution...")
            current_input = {"news_urls": [], "generated_segments": [], "news_url": None}
        else:
            print(f"▶️ Approving and Resuming pipeline (pending node: {snapshot.next})...")
            current_input = None
            
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
    gr.Markdown("# 🚀 News Automation Dashboard")
    
    with gr.Group(visible=False) as approval_panel:
        gr.Markdown("## 🚨 ACTION REQUIRED: Pipeline Paused for Review")
        gr.Markdown("The pipeline has automatically paused at a designated checkpoint. Please review the relevant files locally or adjust settings, then click the button below to approve and resume.")
        b_approve_popup = gr.Button("✅ Confirm & Resume Pipeline", variant="stop")
        
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
            logs_view = gr.Textbox(label="Terminal Logs", lines=15, interactive=False, value=get_logs, every=1.0)

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

    # --- Binder Functions ---
    # Now includes approval_panel to toggle its visibility automatically
    std_all_outputs = [out_news, story_selector, out_story_json, scene_media_selector, out_audio, out_image, out_video, out_youtube_url, approval_panel]
    
    # We use minimal progress so components aren't aggressively grayed out
    btn_all.click(h_run_all, outputs=std_all_outputs, show_progress="minimal")
    b_approve_popup.click(h_run_approve, outputs=std_all_outputs, show_progress="minimal")
    
    b1.click(h_run_scraper, outputs=[out_news], show_progress="minimal") 
    b2.click(h_run_editor, outputs=[story_selector, out_story_json], show_progress="minimal")
    b3.click(h_run_photographer, outputs=[scene_media_selector, out_audio, out_image], show_progress="minimal")
    b4.click(h_run_reporter, outputs=[scene_media_selector, out_audio, out_image], show_progress="minimal")
    b5.click(h_run_renderer, outputs=[out_video], show_progress="minimal")
    b6.click(h_run_youtuber, show_progress="minimal")

if __name__ == "__main__":

    demo.launch(server_name="0.0.0.0", server_port=7860)
