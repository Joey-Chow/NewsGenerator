from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import AgentState
from src.agents.editor import batch_editor_node
from src.agents.scraper import batch_scraper_node
from src.agents.reporter import batch_reporter_node
from src.agents.photographer import batch_photographer_node
from src.agents.ingest import batch_human_script_review_node
from src.agents.scheduler import scheduler_node
from src.agents.concat import concat_node
from src.agents.batch_renderer import batch_video_renderer_node
from src.agents.youtuber import youtuber_node
from src.agents.joiner import join_assets_node
from src.agents.script_critic import script_critic_node
from src.agents.image_critic import image_critic_node

def build_graph(checkpointer=None):
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("scraper", batch_scraper_node)
    workflow.add_node("editor", batch_editor_node)
    workflow.add_node("script_review", batch_human_script_review_node)
    workflow.add_node("script_critic", script_critic_node)
    workflow.add_node("photographer", batch_photographer_node)
    workflow.add_node("image_critic", image_critic_node)
    workflow.add_node("reporter", batch_reporter_node)
    workflow.add_node("renderer", batch_video_renderer_node)
    workflow.add_node("concat", concat_node)
    workflow.add_node("youtuber", youtuber_node)
    workflow.add_node("join_assets", join_assets_node)

    # Set Entry Point
    workflow.set_entry_point("scheduler")

    # Define Linear Flow
    workflow.add_edge("scheduler", "scraper")
    workflow.add_edge("scraper", "editor")
    
    # Editor -> Script Critic (automatic evaluation)
    workflow.add_edge("editor", "script_critic")

    # Script Critic -> conditional: loop back to editor OR proceed to human review
    def route_after_script_critic(state: AgentState):
        if state.get("script_critic_feedback"):
            print("Routing: Script Critic FAILED. Looping back to Editor for revision.")
            return "editor"
        print("Routing: Script Critic PASSED. Proceeding to Human Review.")
        return "script_review"

    workflow.add_conditional_edges(
        "script_critic",
        route_after_script_critic,
        {"editor": "editor", "script_review": "script_review"}
    )

    # Conditional Edge for Script Review
    def route_after_review(state: AgentState):
        if state.get("user_feedback"):
            print(f"Routing logic: 'user_feedback' detected. Routing BACK to editor for revision.")
            return "editor"
        print(f"Routing logic: No 'user_feedback' detected. Routing FORWARD to Parallel branch (photographer & reporter).")
        return ["photographer", "reporter"]

    workflow.add_conditional_edges(
        "script_review",
        route_after_review,
        {
            "editor": "editor", 
            "photographer": "photographer", 
            "reporter": "reporter"
        }
    )
    
    # Parallel Workflow Branch
    # Photographer -> Image Critic (automatic evaluation)
    workflow.add_edge("photographer", "image_critic")

    # Gate node: signals that the photographer branch is done
    workflow.add_node("photographer_done", lambda state: state)

    # Image Critic -> conditional: loop back to photographer OR proceed through gate
    def route_after_image_critic(state: AgentState):
        if state.get("image_critic_feedback"):
            print("Routing: Image Critic FAILED. Looping back to Photographer for re-fetch.")
            return "photographer"
        print("Routing: Image Critic PASSED. Proceeding to Join Assets.")
        return "photographer_done"

    workflow.add_conditional_edges(
        "image_critic",
        route_after_image_critic,
        {"photographer": "photographer", "photographer_done": "photographer_done"}
    )

    # Barrier: join_assets waits for BOTH branches to complete
    workflow.add_edge(["photographer_done", "reporter"], "join_assets")
    
    workflow.add_edge("join_assets", "renderer")
    workflow.add_edge("renderer", "concat")
    workflow.add_edge("concat", "youtuber")
    workflow.add_edge("youtuber", END)


    # Checkpointer for interrupt
    return workflow.compile(
        checkpointer=checkpointer
    )


# For LangGraph Studio (no manual checkpointer)
app = build_graph()

if __name__ == "__main__":
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except ImportError:
        print("Install 'grandalf' to visualize the graph.")
