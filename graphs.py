from langgraph.graph import StateGraph, START, END
from nodes import query_generator, lead_finder, enrich_leads, score_leads, route_leads, outreach_agent, route_function, query_optimizer
from state import LeadState
from langgraph.checkpoint.memory import MemorySaver
graph = StateGraph(LeadState)

memory = MemorySaver()

graph.add_node("query_generator", query_generator)
graph.add_node("lead_finder", lead_finder)
graph.add_node("enrich", enrich_leads)
graph.add_node("score", score_leads)
graph.add_node("router", route_leads)
graph.add_node("outreach", outreach_agent)
graph.add_node("query_optimizer", query_optimizer)

graph.add_edge(START, "query_generator")
graph.add_edge("query_generator", "lead_finder")
graph.add_edge("lead_finder", "enrich")
graph.add_edge("enrich", "score")
graph.add_edge("score", "router")
graph.add_conditional_edges(
    "router",
    route_function,
    {
        "outreach": "outreach",
        "query_optimizer": "query_optimizer",
        END: END,
    },
)
graph.add_edge("query_optimizer", "query_generator")
graph.add_edge("outreach", END)

compiled_graph=graph.compile(checkpointer=memory)


# compiled_graph.invoke({
#     "queries": ["gyms in Karachi", "dentists in Karachi"]
# }, config={"configurable": {"thread_id": "lead-agent-1"}})