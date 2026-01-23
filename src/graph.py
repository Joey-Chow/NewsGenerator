from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.editor import editor_node, scraper_node
from src.agents.reporter import reporter_node
from src.agents.asset_scraper import asset_scraper_node
from src.agents.ingest import human_asset_ingest_node
from src.agents.scheduler import scheduler_node
from src.agents.concat import concat_node
from src.agents.batch_renderer import batch_video_renderer_node
from langgraph.checkpoint.memory import MemorySaver

def human_review_node(state: AgentState):
    # This node serves as a breakpoint or review step
    print("Human Review: Storing approved storyboard for batch rendering...")
    sb = state.get("storyboard")
    
    # FIX: Only return the NEW item. operator.add will append it to the existing list.
    to_append = [sb] if sb else []
    
    return {"is_approved": True, "ready_to_render_storyboards": to_append}

def should_render(state: AgentState):
    if state.get("is_approved"):
        return "scheduler" # Loop back to process next URL
    return "human_review" 

def route_scheduler(state: AgentState):
    # If we have a news_url set by the scheduler, we start the loop
    if state.get("news_url"):
        return "scraper"
    # Otherwise we go to batch rendering
    return "batch_renderer"

def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("concat", concat_node)
    
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("asset_scraper", asset_scraper_node)
    workflow.add_node("human_asset_ingest", human_asset_ingest_node)
    workflow.add_node("reporter", reporter_node)
    workflow.add_node("human_review", human_review_node)
    
    # New Batch Node
    workflow.add_node("batch_renderer", batch_video_renderer_node)

    # Add edges
    # Entry Point -> Scheduler
    workflow.set_entry_point("scheduler")
    
    # Scheduler Routing
    workflow.add_conditional_edges(
        "scheduler",
        route_scheduler,
        {
            "scraper": "scraper",
            "batch_renderer": "batch_renderer"
        }
    )
    
    # Subgraph Sequence
    workflow.add_edge("scraper", "editor")
    workflow.add_edge("editor", "asset_scraper")
    workflow.add_edge("asset_scraper", "human_asset_ingest")
    workflow.add_edge("human_asset_ingest", "reporter")
    workflow.add_edge("reporter", "human_review")
    
    # Review Loop -> Back to Scheduler
    workflow.add_conditional_edges(
        "human_review",
        should_render,
        {
            "scheduler": "scheduler",
            "human_review": "human_review" 
        }
    )
    
    # Batch Renderer -> Concat
    workflow.add_edge("batch_renderer", "concat")
    
    # Final Output
    workflow.add_edge("concat", END)

    # Compile with interrupt and checkpointer
    checkpointer = MemorySaver()
    # Interrupt before human_asset_ingest (for manual asset checks)
    # And potentially before human_review if user wants to check script (optional, but requested flow puts interrupts at ingest)
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["human_asset_ingest"])

if __name__ == "__main__":
    app = build_graph()
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except ImportError:
        print("Install 'grandalf' to visualize the graph.")
