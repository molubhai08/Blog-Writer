

import os
from typing import Annotated

from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"

load_dotenv(dotenv_path=env_path)


# ── State ──────────────────────────────────────────────────────────────────

class State(TypedDict):
    messages: Annotated[list, add_messages]


# ── Tools & Model ───────────────────────────────────────────────────────────

def build_agent(groq_api_key: str, tavily_api_key: str, model: str = "llama-3.3-70b-versatile"):
    """Build and return a compiled LangGraph search agent."""

    os.environ["TAVILY_API_KEY"] = tavily_api_key

    # Search tool — returns top 3 results
    search_tool = TavilySearchResults(max_results=3)
    tools = [search_tool]

    # Groq LLM bound with tools
    llm = ChatGroq(
        api_key=groq_api_key,
        model=model,
        temperature=0,
    ).bind_tools(tools)

    tool_map = {t.name: t for t in tools}

    # ── Nodes ─────────────────────────────────────────────────────────────

    def call_llm(state: State) -> State:
        """Ask the LLM what to do next."""
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    def call_tools(state: State) -> State:
        """Execute any tool calls the LLM requested."""
        last_msg = state["messages"][-1]
        results = []
        for call in last_msg.tool_calls:
            tool = tool_map[call["name"]]
            output = tool.invoke(call["args"])
            results.append(
                ToolMessage(content=str(output), tool_call_id=call["id"])
            )
        return {"messages": results}

    def should_continue(state: State) -> str:
        """Route: use tools if requested, else finish."""
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"
        return END

    # ── Graph ──────────────────────────────────────────────────────────────

    graph = StateGraph(State)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", call_tools)

    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")   # after tools → back to LLM

    return graph.compile()


# ── CLI helper ──────────────────────────────────────────────────────────────

def run_query(agent, query: str, verbose: bool = True) -> str:
    """Run a single query through the agent and return the final answer."""
    state = agent.invoke({"messages": [HumanMessage(content=query)]})
    final = state["messages"][-1].content

    if verbose:
        print(f"\n{'='*60}")
        print(f"Query : {query}")
        print(f"{'='*60}")
        # Show intermediate steps
        for msg in state["messages"]:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for call in msg.tool_calls:
                    print(f"[Tool call] {call['name']}({call['args']})")
            elif isinstance(msg, ToolMessage):
                preview = msg.content[:200].replace("\n", " ")
                print(f"[Tool result] {preview}…")
        print(f"\n[Answer]\n{final}")

    return final


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    GROQ_API_KEY   = os.getenv("GROQ_API_KEY",   "YOUR_GROQ_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY",  "YOUR_TAVILY_API_KEY")

    if "YOUR_" in GROQ_API_KEY or "YOUR_" in TAVILY_API_KEY:
        print("⚠  Set GROQ_API_KEY and TAVILY_API_KEY environment variables before running.")
        print("   export GROQ_API_KEY=gsk_...")
        print("   export TAVILY_API_KEY=tvly-...")
        sys.exit(1)

    agent = build_agent(GROQ_API_KEY, TAVILY_API_KEY)

    queries = [
        "What are the latest AI news today?",
        "Who won the most recent FIFA World Cup?",
    ]

    if len(sys.argv) > 1:
        queries = [" ".join(sys.argv[1:])]

    for q in queries:
        run_query(agent, q)