from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import AgentState
from src.agents.editor import batch_editor_node
from src.agents.scraper import batch_scraper_node
from src.agents.reporter import batch_reporter_node
from src.agents.photographer import batch_photographer_node
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
    workflow.add_node("batch_photographer", batch_photographer_node)
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
    
    # Conditional Edge for Script Review (LLM Revision Loop)
    def route_after_review(state: AgentState):
        if state.get("user_feedback"):
            print(f"Routing logic: 'user_feedback' detected. Routing BACK to batch_editor for revision.")
            return "batch_editor"
        print(f"Routing logic: No 'user_feedback' detected. Routing FORWARD to batch_photographer.")
        return "batch_photographer"

    workflow.add_conditional_edges(
        "batch_script_review",
        route_after_review,
        {"batch_editor": "batch_editor", "batch_photographer": "batch_photographer"}
    )
    
    workflow.add_edge("batch_photographer", "batch_reporter")
    workflow.add_edge("batch_reporter", "batch_renderer")
    workflow.add_edge("batch_renderer", "concat")
    workflow.add_edge("concat", "youtuber")
    workflow.add_edge("youtuber", END)

    # Checkpointer for interrupt
    checkpointer = MemorySaver()
    
    # Interrupt ONLY before script review
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["batch_script_review"])

if __name__ == "__main__":
    app = build_graph()
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except ImportError:
        print("Install 'grandalf' to visualize the graph.")
