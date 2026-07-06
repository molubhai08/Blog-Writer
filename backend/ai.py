import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
RESEARCHER_MODEL = "llama-3.1-8b-instant"
NARRATIVE_MODEL = "llama-3.3-70b-versatile"
SECTION_RESEARCHER_MODEL = "llama-3.1-8b-instant"
WRITER_MODEL = "llama-3.3-70b-versatile"
REVIEWER_MODEL = "llama-3.3-70b-versatile"
BLOG_TARGET_LENGTH = 1500
MAX_RETRIES = 2


# ── Shared State ────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── Reusable LLM builder ─────────────────────────────────────────────────────

def build_llm(model: str, tools: list = []):
    llm = ChatGroq(api_key=GROQ_API_KEY, model=model, temperature=0.3)
    if tools:
        return llm.bind_tools(tools)
    return llm


# ── Reusable graph builder ───────────────────────────────────────────────────

def build_react_agent(llm, tools: list):
    tool_map = {t.name: t for t in tools}

    def call_llm(state: AgentState):
        return {"messages": [llm.invoke(state["messages"])]}

    def call_tools(state: AgentState):
        last = state["messages"][-1]
        results = []
        for call in last.tool_calls:
            output = tool_map[call["name"]].invoke(call["args"])
            results.append(ToolMessage(content=str(output), tool_call_id=call["id"]))
        return {"messages": results}

    def router(state: AgentState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", router, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")

    return graph.compile()


# ── Researcher Agent ─────────────────────────────────────────────────────────

def build_researcher():
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
    search_tool = TavilySearchResults(max_results=4)
    tools = [search_tool]
    llm = build_llm(RESEARCHER_MODEL, tools)
    return build_react_agent(llm, tools)


RESEARCHER_PROMPT = """You are a research agent. Search for 5-6 key facts and articles about the topic below. Use the search tool 2 times with different queries.

Return ONLY a valid JSON object like this:
{{
  "findings": [
    {{"fact": "...", "url": "...", "title": "..."}},
    ...
  ],
  "sources": ["url1", "url2", ...]
}}

No extra text. Just the JSON.

Topic: {topic}"""


def run_researcher(topic: str) -> dict:
    import json, re
    agent = build_researcher()
    prompt = RESEARCHER_PROMPT.format(topic=topic)
    state = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    final_answer = state["messages"][-1].content

    try:
        match = re.search(r"\{[\s\S]*\}", final_answer)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}

    return {
        "topic": topic,
        "findings": parsed.get("findings", [])[:6],
        "sources": parsed.get("sources", [])[:6]
    }


# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    result = run_researcher("Climate Change impact on India")
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ── Narrative Agent ──────────────────────────────────────────────────────────

def build_narrative_agent():
    llm = build_llm(NARRATIVE_MODEL)
    return llm


NARRATIVE_PROMPT = """You are a narrative designer. Given research findings on a topic and the target audience, create a blog structure.

RESEARCH FINDINGS:
{research_summary}

TOPIC: {topic}
AUDIENCE: {audience}
TARGET LENGTH: {target_length} words

{gs_context}

Return ONLY valid JSON:
{{
  "audience": "{audience}",
  "topic": "{topic}",
  "subject": "...",
  "gsPaper": "GS-I|GS-II|GS-III|GS-IV or null",
  "writingInstructions": ["instruction1", "instruction2", ...],
  "outline": ["section1", "section2", ...]
}}

Rules:
- If audience is UPSC, map the topic to the correct GS paper and subject using the reference above
- If audience is Professional or General, set gsPaper to null and subject to a general category
- writingInstructions should be 4-6 clear guidelines for the content writer
- outline should have 5-7 logical sections for a {target_length}-word blog
- For UPSC: avoid political bias, use educational tone, include exam relevance
- No extra text. Just JSON."""


def run_narrative_agent(topic: str, audience: str, research_data: dict) -> dict:
    import json, re
    
    gs_context = ""
    if audience == "UPSC":
        gs_path = Path(__file__).parent / "gs_papers.md"
        gs_context = "GS PAPERS REFERENCE:\n" + gs_path.read_text(encoding="utf-8")
    
    research_summary = "\n".join([
        f"- {f['fact']} ({f['url']})" for f in research_data.get("findings", [])
    ])
    
    llm = build_narrative_agent()
    prompt = NARRATIVE_PROMPT.format(
        topic=topic,
        audience=audience,
        target_length=BLOG_TARGET_LENGTH,
        research_summary=research_summary,
        gs_context=gs_context
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        match = re.search(r"\{[\s\S]*\}", response.content)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}
    
    return {
        "audience": parsed.get("audience", audience),
        "topic": parsed.get("topic", topic),
        "subject": parsed.get("subject"),
        "gsPaper": parsed.get("gsPaper"),
        "writingInstructions": parsed.get("writingInstructions", []),
        "outline": parsed.get("outline", [])
    }


# ── Section Researcher Agent ─────────────────────────────────────────────────

def build_section_researcher():
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
    search_tool = TavilySearchResults(max_results=3)
    tools = [search_tool]
    llm = build_llm(SECTION_RESEARCHER_MODEL, tools)
    return build_react_agent(llm, tools)


SECTION_RESEARCHER_PROMPT = """You are a section researcher. Find specific facts for this section.

SECTION: {section}
TOPIC: {topic}

Use the search tool to find 2-3 key facts relevant to this section only.

Return JSON:
{{
  "facts": [
    {{"fact": "...", "source": "..."}},
    ...
  ]
}}

No extra text."""


def run_section_researcher(topic: str, section: str) -> dict:
    import json, re
    agent = build_section_researcher()
    prompt = SECTION_RESEARCHER_PROMPT.format(topic=topic, section=section)
    state = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    
    final_answer = state["messages"][-1].content
    
    try:
        match = re.search(r"\{[\s\S]*\}", final_answer)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}
    
    return {
        "section": section,
        "facts": parsed.get("facts", [])
    }


# ── Content Writer Agent ─────────────────────────────────────────────────────

def build_writer():
    llm = build_llm(WRITER_MODEL)
    return llm


WRITER_PROMPT = """You are a content writer. Write this section following the guidelines below.

SECTION: {section}
TOPIC: {topic}
AUDIENCE: {audience}
TARGET WORDS: ~{target_words} words

RESEARCH FACTS:
{facts}

{gs_info}

{writing_guidelines}

{feedback}

Write natural, human-like content. Follow the examples in the guidelines.

Return JSON:
{{
  "sectionTitle": "{section}",
  "content": "...",
  "image": {{
    "required": true/false,
    "prompt": "...",
    "caption": "..."
  }}
}}

No extra text."""


def run_writer(topic: str, section: str, audience: str, section_research: dict, narrative: dict, feedback: str = "") -> dict:
    import json, re
    
    para_path = Path(__file__).parent / "para.md"
    writing_guidelines = para_path.read_text(encoding="utf-8")
    
    gs_info = ""
    if audience == "UPSC":
        gs_info = f"GS Paper: {narrative.get('gsPaper')}\nSubject: {narrative.get('subject')}\nInclude UPSC-relevant examples where appropriate."
    
    facts_text = "\n".join([f"- {f['fact']} ({f.get('source', '')})" for f in section_research.get("facts", [])])
    
    num_sections = len(narrative.get("outline", []))
    target_words = BLOG_TARGET_LENGTH // num_sections if num_sections > 0 else 200
    
    feedback_text = f"\nREVIEWER FEEDBACK:\n{feedback}\n\nRewrite addressing the above issues." if feedback else ""
    
    llm = build_writer()
    prompt = WRITER_PROMPT.format(
        section=section,
        topic=topic,
        audience=audience,
        target_words=target_words,
        facts=facts_text,
        gs_info=gs_info,
        writing_guidelines=writing_guidelines,
        feedback=feedback_text
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        match = re.search(r"\{[\s\S]*\}", response.content)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}
    
    return {
        "sectionTitle": parsed.get("sectionTitle", section),
        "content": parsed.get("content", ""),
        "image": parsed.get("image", {"required": False, "prompt": "", "caption": ""})
    }


# ── Reviewer Agent ───────────────────────────────────────────────────────────

def build_reviewer():
    llm = build_llm(REVIEWER_MODEL)
    return llm


REVIEWER_PROMPT = """You are a content reviewer. Evaluate this section for human-likeness.

SECTION TITLE: {section_title}
CONTENT:
{content}

EVALUATION CRITERIA:
{guidelines}

Score the content on human-likeness (0.0 to 1.0).

Consider:
- Sentence variety and length
- Natural flow and transitions
- Avoidance of robotic phrasing
- Specific examples vs generic statements
- Active voice usage

Return JSON:
{{
  "humanScore": 0.85,
  "feedback": "Specific issues if score < 0.7, otherwise empty string"
}}

No extra text."""


def run_reviewer(section_title: str, content: str) -> dict:
    import json, re
    
    para_path = Path(__file__).parent / "para.md"
    guidelines = para_path.read_text(encoding="utf-8")
    
    llm = build_reviewer()
    prompt = REVIEWER_PROMPT.format(
        section_title=section_title,
        content=content,
        guidelines=guidelines
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        match = re.search(r"\{[\s\S]*\}", response.content)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}
    
    return {
        "humanScore": parsed.get("humanScore", 0.0),
        "feedback": parsed.get("feedback", "")
    }


# ── Section Pipeline with Review Loop ────────────────────────────────────────

def run_section_pipeline(topic: str, section: str, audience: str, narrative: dict) -> dict:
    section_research = run_section_researcher(topic, section)
    
    written_section = None
    review = None
    
    for attempt in range(MAX_RETRIES + 1):
        feedback = review["feedback"] if review and review["humanScore"] < 0.7 else ""
        
        written_section = run_writer(topic, section, audience, section_research, narrative, feedback)
        review = run_reviewer(written_section["sectionTitle"], written_section["content"])
        
        if review["humanScore"] >= 0.7:
            break
    
    return {
        "sectionTitle": written_section["sectionTitle"],
        "content": written_section["content"],
        "humanScore": review["humanScore"],
        "image": written_section["image"]
    }
