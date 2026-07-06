import os
import time
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict
import requests
from groq import RateLimitError
from cerebras.cloud.sdk import Cerebras

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SAPLING_API_KEY = os.getenv("SAPLING_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

RESEARCHER_MODEL = "llama-3.1-8b-instant"
NARRATIVE_MODEL = "llama-3.3-70b-versatile"
SECTION_RESEARCHER_MODEL = "llama-3.1-8b-instant"
WRITER_MODEL = "llama-3.1-8b-instant"
METADATA_MODEL = "llama-3.3-70b-versatile"
MCQ_MODEL = "llama-3.3-70b-versatile"
CEREBRAS_MODEL = "zai-glm-4.7"

BLOG_TARGET_LENGTH = 1500
MAX_RETRIES = 2
MCQ_COUNT = 5
SECTION_QUEUE_DELAY = 4


# ── Cerebras fallback client ──────────────────────────────────────────────────

cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)


def cerebras_invoke(prompt: str) -> str:
    response = cerebras_client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


# ── Shared State ────────────────────────────────────────────────────────────


def llm_invoke_with_retry(llm, messages, retries=3, wait=5):
    for attempt in range(retries):
        try:
            return llm.invoke(messages)
        except RateLimitError:
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise

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
        return {"messages": [llm_invoke_with_retry(llm, state["messages"])]}

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
    search_tool = TavilySearchResults(max_results=2)
    tools = [search_tool]
    llm = build_llm(RESEARCHER_MODEL, tools)
    return build_react_agent(llm, tools)


RESEARCHER_PROMPT = """Research agent. Find 5-6 facts about the topic. Use search tool twice with different queries.

Return ONLY JSON:
{{"findings": [{{"fact": "...", "url": "...", "title": "..."}}], "sources": ["url1"]}}

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
- writingInstructions should be 3-4 clear guidelines for the content writer
- outline must have exactly 4 sections (Introduction, 2 body sections, Conclusion)
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
    
    response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])
    
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
    search_tool = TavilySearchResults(max_results=1)
    tools = [search_tool]
    llm = build_llm(SECTION_RESEARCHER_MODEL, tools)
    return build_react_agent(llm, tools)


SECTION_RESEARCHER_PROMPT = """Find 2-3 facts for this section. Use search tool once.

Return ONLY JSON: {{"facts": [{{"fact": "...", "source": "..."}}]}}

SECTION: {section}
TOPIC: {topic}"""


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

    try:
        raw = cerebras_invoke(prompt)
    except Exception:
        response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)], retries=4, wait=10)
        raw = response.content

    try:
        match = re.search(r"\{[\s\S]*\}", raw)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}

    raw_title = parsed.get("sectionTitle", section)
    clean_title = re.sub(r"^(Body Section \d+:|Introduction:|Conclusion:|Section \d+:)\s*", "", raw_title).strip()

    content = parsed.get("content", "")
    if not content:
        content_match = re.search(r'"content"\s*:\s*"([\s\S]*?)(?<!\\)",', raw)
        if content_match:
            content = content_match.group(1).replace('\\"', '"').replace("\\n", "\n")
        else:
            content = raw

    content = re.sub(r"##\s*(SECTION|Image|Section)[^\n]*\n?", "", content)
    content = re.sub(r"\{[^}]*\"required\"[^}]*\}", "", content, flags=re.DOTALL)
    content = re.sub(r'"(sectionTitle|image|required|prompt|caption)"\s*:.*\n?', "", content)
    content = re.sub(r'\{[\s\S]*?\}', "", content)
    content = content.strip()

    return {
        "sectionTitle": clean_title,
        "content": content,
        "image": parsed.get("image", {"required": False, "prompt": "", "caption": ""})
    }


# ── Reviewer Agent (Sapling AI Detection) ───────────────────────────────────

def run_reviewer(content: str) -> dict:
    try:
        response = requests.post(
            "https://api.sapling.ai/api/v1/aidetect",
            json={"key": SAPLING_API_KEY, "text": content},
            timeout=10
        )
        if response.status_code != 200 or not response.text.strip():
            return {"humanScore": 1.0, "feedback": ""}

        data = response.json()
        ai_score = data.get("score", 0.0)
        human_score = round(1.0 - ai_score, 2)

        feedback = ""
        if human_score < 0.7:
            feedback = "Too AI-like. Use shorter varied sentences, fragments, rhetorical questions, and casual phrasing. Avoid uniform structure."

        return {"humanScore": human_score, "feedback": feedback}

    except Exception:
        return {"humanScore": 1.0, "feedback": ""}


# ── Section Pipeline with Review Loop ────────────────────────────────────────

def run_section_pipeline(topic: str, section: str, audience: str, narrative: dict) -> dict:
    section_research = run_section_researcher(topic, section)
    
    written_section = None
    review = None
    
    for attempt in range(MAX_RETRIES + 1):
        feedback = review["feedback"] if review and review["humanScore"] < 0.7 else ""
        
        written_section = run_writer(topic, section, audience, section_research, narrative, feedback)
        review = run_reviewer(written_section["content"])
        
        if review["humanScore"] >= 0.7:
            break
    
    return {
        "sectionTitle": written_section["sectionTitle"],
        "content": written_section["content"],
        "humanScore": review["humanScore"],
        "image": written_section["image"]
    }


# ── Reference Generator ──────────────────────────────────────────────────────

def generate_references(main_research: dict, section_researches: list) -> dict:
    all_sources = []
    
    for finding in main_research.get("findings", []):
        all_sources.append({
            "url": finding.get("url", ""),
            "title": finding.get("title", "")
        })
    
    for section_research in section_researches:
        for fact in section_research.get("facts", []):
            source = fact.get("source", "")
            if source:
                all_sources.append({
                    "url": source,
                    "title": ""
                })
    
    seen_urls = set()
    unique_sources = []
    for src in all_sources:
        url = src["url"]
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_sources.append(src)
    
    references = [
        {"id": i+1, "url": src["url"], "title": src["title"]}
        for i, src in enumerate(unique_sources)
    ]
    
    return {"references": references}


# ── Metadata Generator ───────────────────────────────────────────────────────

METADATA_PROMPT = """You are an SEO metadata specialist. Generate metadata for this blog.

TOPIC: {topic}
AUDIENCE: {audience}
SUBJECT: {subject}

BLOG CONTENT SUMMARY:
{content_summary}

SEO GUIDELINES:
{seo_guidelines}

Return ONLY valid JSON:
{{
  "title": "...",
  "metaTitle": "...",
  "metaDescription": "...",
  "slug": "...",
  "tags": ["...", "..."],
  "primaryKeyword": "...",
  "relatedKeywords": ["...", "..."],
  "readingTime": 7
}}

Rules:
- title: descriptive, includes primary keyword, 50-60 chars
- metaTitle: same as title or slight variation, under 60 chars
- metaDescription: 150-160 chars, includes primary keyword, describes the article
- slug: lowercase, hyphen-separated, no special chars
- tags: 5-8 relevant tags
- readingTime: estimate in minutes based on {word_count} words (avg 200 words/min)
- No extra text"""


def run_metadata_generator(topic: str, audience: str, narrative: dict, sections: list) -> dict:
    import json, re

    seo_path = Path(__file__).parent / "seo.md"
    seo_guidelines = seo_path.read_text(encoding="utf-8")

    content_summary = "\n".join([
        f"- {s['sectionTitle']}: {s['content'][:200]}..."
        for s in sections
    ])

    total_words = sum(len(s["content"].split()) for s in sections)

    llm = build_llm(METADATA_MODEL)
    prompt = METADATA_PROMPT.format(
        topic=topic,
        audience=audience,
        subject=narrative.get("subject", ""),
        content_summary=content_summary,
        seo_guidelines=seo_guidelines,
        word_count=total_words
    )

    response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])

    try:
        match = re.search(r"\{[\s\S]*\}", response.content)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}

    reading_time = max(1, round(total_words / 200))

    return {
        "title": parsed.get("title", topic),
        "metaTitle": parsed.get("metaTitle", topic),
        "metaDescription": parsed.get("metaDescription", ""),
        "slug": parsed.get("slug", topic.lower().replace(" ", "-")),
        "tags": parsed.get("tags", []),
        "primaryKeyword": parsed.get("primaryKeyword", ""),
        "relatedKeywords": parsed.get("relatedKeywords", []),
        "readingTime": reading_time
    }


# ── MCQ Generator ────────────────────────────────────────────────────────────

MCQ_PROMPT = """You are an MCQ generator. Create {num_questions} multiple choice questions based on this blog content.

TOPIC: {topic}
AUDIENCE: {audience}

BLOG SECTIONS:
{sections_summary}

Generate questions that test understanding of key concepts covered in the blog.

Rules:
- Each question should have 4 options (A, B, C, D)
- Mark the correct answer
- Questions should be clear and unambiguous
- Avoid trick questions
- For UPSC audience: make questions exam-relevant

Return ONLY valid JSON:
{{
  "mcqs": [
    {{
      "question": "...",
      "options": {{
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "..."
      }},
      "correctAnswer": "A",
      "explanation": "..."
    }},
    ...
  ]
}}

No extra text."""


def run_mcq_generator(topic: str, audience: str, sections: list) -> dict:
    import json, re

    sections_summary = "\n".join([
        f"{s['sectionTitle']}:\n{s['content'][:300]}..."
        for s in sections
    ])

    llm = build_llm(MCQ_MODEL)
    prompt = MCQ_PROMPT.format(
        num_questions=MCQ_COUNT,
        topic=topic,
        audience=audience,
        sections_summary=sections_summary
    )

    response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])

    try:
        match = re.search(r"\{[\s\S]*\}", response.content)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}

    return {
        "mcqs": parsed.get("mcqs", [])
    }

# ── Full Blog Assembler ──────────────────────────────────────────────────────

def generate_blog(topic: str, audience: str) -> dict:
    print(f"[1/6] Researching topic: {topic}")
    main_research = run_researcher(topic)

    print("[2/6] Building narrative and outline...")
    narrative = run_narrative_agent(topic, audience, main_research)

    sections = []
    section_researches = []

    for i, section in enumerate(narrative["outline"]):
        print(f"[3/6] Writing section {i+1}/{len(narrative['outline'])}: {section}")
        if i > 0:
            time.sleep(SECTION_QUEUE_DELAY)
        result = run_section_pipeline(topic, section, audience, narrative)
        sections.append(result)
        section_researches.append({"facts": []})

    print("[4/6] Generating references...")
    references = generate_references(main_research, section_researches)

    print("[5/6] Generating metadata...")
    metadata = run_metadata_generator(topic, audience, narrative, sections)

    print("[6/6] Generating MCQs...")
    mcqs = run_mcq_generator(topic, audience, sections)

    return {
        "metadata": metadata,
        "narrative": {
            "audience": narrative["audience"],
            "subject": narrative["subject"],
            "gsPaper": narrative.get("gsPaper"),
            "writingInstructions": narrative["writingInstructions"]
        },
        "sections": sections,
        "references": references["references"],
        "mcqs": mcqs["mcqs"]
    }


if __name__ == "__main__":
    import json
    result = generate_blog("Climate Change impact on India", "UPSC")
    print(json.dumps(result, indent=2, ensure_ascii=False))
