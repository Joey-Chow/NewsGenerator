from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import AgentState
from src.agents.editor import batch_scraper_node, batch_editor_node
from src.agents.reporter import batch_reporter_node
from src.agents.asset_scraper import batch_asset_scraper_node
from src.agents.ingest import batch_human_asset_ingest_node, batch_human_script_review_node
from src.agents.scheduler import scheduler_node
from src.agents.concat import concat_node
from src.agents.batch_renderer import batch_video_renderer_node
from src.agents.youtuber import youtuber_node

def build_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("batch_scraper", batch_scraper_node)
    workflow.add_node("batch_editor", batch_editor_node)
    workflow.add_node("batch_script_review", batch_human_script_review_node) # New Node
    workflow.add_node("batch_asset_scraper", batch_asset_scraper_node)
    workflow.add_node("batch_human_ingest", batch_human_asset_ingest_node)
    workflow.add_node("batch_reporter", batch_reporter_node)
    workflow.add_node("batch_renderer", batch_video_renderer_node)
    workflow.add_node("concat", concat_node)
    workflow.add_node("youtuber", youtuber_node)

    # Set Entry Point
    workflow.set_entry_point("scheduler")

    # Define Linear Flow
    # Scheduler loads list of URLs -> Scraper
    workflow.add_edge("scheduler", "batch_scraper")
    workflow.add_edge("batch_scraper", "batch_editor")
    
    # Interrupt 1: Script Review (Check output/storyboard/*.json)
    workflow.add_edge("batch_editor", "batch_script_review")
    workflow.add_edge("batch_script_review", "batch_asset_scraper")
    
    # Interrupt 2: Asset Review (Check output/assets_final/*.jpg)
    workflow.add_edge("batch_asset_scraper", "batch_human_ingest")
    
    workflow.add_edge("batch_human_ingest", "batch_reporter")
    workflow.add_edge("batch_reporter", "batch_renderer")
    workflow.add_edge("batch_renderer", "concat")
    workflow.add_edge("concat", "youtuber")
    workflow.add_edge("youtuber", END)

    # Checkpointer for interrupt
    checkpointer = MemorySaver()
    
    # Interrupt before script review AND asset review
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["batch_script_review", "batch_human_ingest"])

if __name__ == "__main__":
    app = build_graph()
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except ImportError:
        print("Install 'grandalf' to visualize the graph.")
