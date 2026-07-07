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

GROQ_API_KEYS_RAW = os.getenv("GROQ_API_KEYS", "")
GROQ_KEYS = [k.strip() for k in GROQ_API_KEYS_RAW.split(",") if k.strip()]
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY and GROQ_KEYS:
    GROQ_API_KEY = GROQ_KEYS[0]
if not GROQ_KEYS:
    GROQ_KEYS = [GROQ_API_KEY] if GROQ_API_KEY else []
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SAPLING_API_KEY = os.getenv("SAPLING_API_KEY")
CEREBRAS_API_KEYS_RAW = os.getenv("CEREBRAS_API_KEYS", "")
CEREBRAS_KEYS = [k.strip() for k in CEREBRAS_API_KEYS_RAW.split(",") if k.strip()]
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
if not CEREBRAS_API_KEY and CEREBRAS_KEYS:
    CEREBRAS_API_KEY = CEREBRAS_KEYS[0]
if not CEREBRAS_KEYS:
    CEREBRAS_KEYS = [CEREBRAS_API_KEY] if CEREBRAS_API_KEY else []
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

RESEARCHER_MODEL = "llama-3.3-70b-versatile"
NARRATIVE_MODEL = "llama-3.3-70b-versatile"
SECTION_RESEARCHER_MODEL = "llama-3.3-70b-versatile"
WRITER_MODEL = "llama-3.1-8b-instant"
METADATA_MODEL = "llama-3.3-70b-versatile"
MCQ_MODEL = "llama-3.3-70b-versatile"
CEREBRAS_MODEL = "zai-glm-4.7"

BLOG_TARGET_LENGTH = 1500
MAX_RETRIES = 2
MCQ_COUNT = 5
SECTION_QUEUE_DELAY = 4
VALIDATOR_MODEL = "llama-3.1-8b-instant"


# ── Cerebras fallback client ──────────────────────────────────────────────────

cerebras_client = None
if CEREBRAS_API_KEY:
    try:
        cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    except Exception:
        cerebras_client = None


def cerebras_invoke(prompt: str, api_key: str = None) -> str:
    client = None
    if api_key:
        try:
            client = Cerebras(api_key=api_key)
        except Exception:
            client = None
    if not client:
        client = cerebras_client
    if not client:
        raise ValueError("Cerebras client not initialized due to missing API key")
    response = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def robust_json_loads(json_str: str) -> dict:
    import json, re
    if not json_str:
        return {}
    
    cleaned = json_str.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    cleaned = cleaned.strip()

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        start_idx = cleaned.find("{")
        if start_idx != -1:
            obj_str = cleaned[start_idx:]
        else:
            return {}
    else:
        obj_str = match.group()

    obj_str = re.sub(r',\s*\}', '}', obj_str)
    obj_str = re.sub(r',\s*\]', ']', obj_str)

    try:
        return json.loads(obj_str)
    except json.JSONDecodeError:
        if '"mcqs"' in obj_str and "[" in obj_str:
            last_comma_brace = obj_str.rfind("},")
            if last_comma_brace != -1:
                salvaged = obj_str[:last_comma_brace + 1] + "]}"
                try:
                    return json.loads(salvaged)
                except Exception:
                    pass

        repaired = obj_str
        if repaired.count('"') % 2 != 0:
            repaired += '"'

        open_braces = repaired.count('{')
        close_braces = repaired.count('}')
        open_brackets = repaired.count('[')
        close_brackets = repaired.count(']')

        if open_brackets > close_brackets:
            repaired += ']' * (open_brackets - close_brackets)
        if open_braces > close_braces:
            repaired += '}' * (open_braces - close_braces)
            
        try:
            return json.loads(repaired)
        except Exception:
            return {}


def invoke_agent_with_fallback(prompt: str, fallback_model: str, api_key: str = None, cerebras_api_key: str = None) -> str:
    c_key = cerebras_api_key if cerebras_api_key else CEREBRAS_API_KEY
    if c_key:
        try:
            return cerebras_invoke(prompt, api_key=c_key)
        except Exception:
            pass
    llm = build_llm(fallback_model, api_key=api_key)
    response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])
    return response.content


# ── Shared State ────────────────────────────────────────────────────────────


def llm_invoke_with_retry(llm, messages, retries=3, wait=5):
    for attempt in range(retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                if attempt < retries - 1:
                    time.sleep(wait)
                    continue
            raise


# ── Topic Validator ──────────────────────────────────────────────────────────

VALIDATOR_PROMPT = """You are a topic validator for a blog generation system.

Evaluate if this topic is suitable for generating an informative, educational blog post.

TOPIC: "{topic}"

Reject if:
- It is nonsensical, random characters, or gibberish (e.g. "asdfjkl", "123xyz")
- It is too vague to write a meaningful blog (e.g. "things", "stuff", "idk")
- It is inappropriate, hateful, violent, or politically biased
- It is a single common word with no context (e.g. "cat", "yes", "hello")
- It is a person's first name with no other context (e.g. "sarthak", "john", "rahul")
- It cannot support a 1000+ word informative blog

Accept if:
- It is a real topic, concept, event, issue, or subject
- A knowledgeable person could write multiple paragraphs about it
- It is educational or informative in nature

Return ONLY valid JSON:
{{"valid": true, "reason": ""}}
or
{{"valid": false, "reason": "Brief explanation why this topic is not suitable"}}

No extra text."""


def validate_topic(topic: str) -> dict:
    import json, re
    topic_clean = topic.strip()
    if not topic_clean or len(topic_clean) < 3:
        return {"valid": False, "reason": "Topic is too short. Please enter a meaningful topic."}

    # Local check: Reject single short words (e.g. cat, dog, yes)
    if len(topic_clean.split()) == 1 and len(topic_clean) < 4:
        return {"valid": False, "reason": "Single short words are not valid topics. Please expand your topic description."}

    # Supabase conflict check: compare against past blog topics using cosine similarity
    try:
        past_blogs = get_supabase_topics()
        for blog in past_blogs:
            past_topic = blog.get("topic", "")
            sim = topic_similarity(topic_clean, past_topic)
            if sim >= 0.75:
                title = blog.get("title", past_topic)
                return {
                    "valid": False,
                    "conflict": True,
                    "reason": f"A highly similar blog already exists: \"{title}\".",
                    "conflictSlug": blog.get("slug", ""),
                    "conflictTitle": title
                }
    except Exception:
        pass  # If Supabase check fails, continue to LLM validation

    llm = build_llm(VALIDATOR_MODEL)
    prompt = VALIDATOR_PROMPT.format(topic=topic.strip())
    try:
        response = llm_invoke_with_retry(llm, [HumanMessage(content=prompt)])
        match = re.search(r"\{[\s\S]*\}", response.content)
        parsed = json.loads(match.group()) if match else {}
        return {
            "valid": parsed.get("valid", True),
            "reason": parsed.get("reason", "")
        }
    except Exception:
        return {"valid": True, "reason": ""}



# ── Supabase REST Helpers ───────────────────────────────────────────────────────────

def _supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }


def supabase_request(method: str, path: str, json_data=None, params=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    # Clean the base URL by stripping trailing slashes and any /rest/v1 suffix
    base_url = SUPABASE_URL.strip().rstrip("/")
    if base_url.endswith("/rest/v1"):
        base_url = base_url[:-8].rstrip("/")
        
    url = f"{base_url}/rest/v1/{path}"
    try:
        resp = requests.request(
            method, url,
            headers=_supabase_headers(),
            json=json_data,
            params=params,
            timeout=10
        )
        if resp.status_code in (200, 201, 204):
            try:
                return resp.json()
            except Exception:
                return {}
        return None
    except Exception:
        return None


def get_supabase_topics() -> list:
    result = supabase_request(
        "GET", "blogs",
        params={"select": "slug,topic,data->>title", "order": "created_at.desc"}
    )
    if not result:
        return []
    return result


def topic_similarity(topic_a: str, topic_b: str) -> float:
    import re, math
    from collections import Counter

    # Acronym mapping: expand 'ai' to 'artificial intelligence'
    t_a = re.sub(r'\bai\b', 'artificial intelligence', topic_a.lower())
    t_b = re.sub(r'\bai\b', 'artificial intelligence', topic_b.lower())

    def tokenize(text: str) -> list:
        return re.findall(r'\b[a-z]{2,}\b', text)

    def clean_word(word: str) -> str:
        w = word.lower()
        if w in ("indian", "indians"):
            return "india"
        if w == "services":
            return "service"
        return w

    STOPWORDS = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
                 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'has', 'on', 'of', 'in'}

    tokens_a = [clean_word(t) for t in tokenize(t_a) if t not in STOPWORDS]
    tokens_b = [clean_word(t) for t in tokenize(t_b) if t not in STOPWORDS]

    if not tokens_a or not tokens_b:
        return 0.0

    all_tokens = list(set(tokens_a) | set(tokens_b))
    vec_a = Counter(tokens_a)
    vec_b = Counter(tokens_b)

    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in all_tokens)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def save_blog_to_supabase(slug: str, topic: str, audience: str, blog_data: dict):
    supabase_request(
        "POST", "blogs",
        json_data={
            "slug": slug,
            "topic": topic,
            "audience": audience,
            "data": blog_data
        }
    )


def delete_blog_from_supabase(slug: str):
    supabase_request(
        "DELETE", "blogs",
        params={"slug": f"eq.{slug}"}
    )

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── Reusable LLM builder ─────────────────────────────────────────────────────

def build_llm(model: str, tools: list = [], api_key: str = None):
    key = api_key if api_key else GROQ_API_KEY
    llm = ChatGroq(api_key=key, model=model, temperature=0.3, max_tokens=4096)
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
- For UPSC, follow these structural rules:
  1. Inter-disciplinary connection: Connect the topic to another GS paper dimension. One body section must represent this connection (e.g. connect a GS-I/III topic to GS-IV Ethics via concepts like 'Crisis of Conscience' or moral dilemmas, or to GS-II International Relations via foreign policy corridors).
  2. Active Recall & Gamification: Do NOT use passive, dry headings (like 'Challenges' or 'Way Forward'). Instead, formulate the body and conclusion section outline headings as challenging, role-based, analytical, or situational questions (e.g., 'If you are a District Magistrate, how would you deploy PWDVA 2005 to protect a victim today?' or 'How does Green Hydrogen corridors redefine India's bilateral tie with Japan and EU?').
- For UPSC: avoid political bias, use educational tone, include exam relevance
- No extra text. Just JSON.
"""


def run_narrative_agent(topic: str, audience: str, research_data: dict) -> dict:
    import json, re
    
    gs_context = ""
    if audience == "UPSC":
        gs_path = Path(__file__).parent / "gs_papers.md"
        gs_context = "GS PAPERS REFERENCE:\n" + gs_path.read_text(encoding="utf-8")
    
    research_summary = "\n".join([
        f"- {f['fact']} ({f['url']})" for f in research_data.get("findings", [])
    ])
    
    prompt = NARRATIVE_PROMPT.format(
        topic=topic,
        audience=audience,
        target_length=BLOG_TARGET_LENGTH,
        research_summary=research_summary,
        gs_context=gs_context
    )
    
    raw_response = invoke_agent_with_fallback(prompt, NARRATIVE_MODEL)
    
    try:
        match = re.search(r"\{[\s\S]*\}", raw_response)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}
    
    outline = parsed.get("outline", [])
    if not outline or len(outline) != 4:
        outline = [
            f"Introduction to {topic}",
            f"Key Challenges and Issues of {topic}",
            f"Current Measures and Solutions for {topic}",
            f"Conclusion and Way Forward for {topic}"
        ]

    writing_instructions = parsed.get("writingInstructions", [])
    if not writing_instructions:
        writing_instructions = [
            "Use clear headings and structured paragraphs.",
            "Integrate facts and figures from research where relevant.",
            "Write in an engaging, reader-friendly tone matching the target audience."
        ]

    subject = parsed.get("subject")
    if not subject:
        subject = "General Studies" if audience == "UPSC" else "General Interest"

    gs_paper = parsed.get("gsPaper")
    if audience == "UPSC" and not gs_paper:
        gs_paper = "GS-III"

    return {
        "audience": parsed.get("audience", audience),
        "topic": parsed.get("topic", topic),
        "subject": subject,
        "gsPaper": gs_paper,
        "writingInstructions": writing_instructions,
        "outline": outline
    }


# ── Section Researcher Agent ─────────────────────────────────────────────────

def build_section_researcher(api_key: str = None):
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
    search_tool = TavilySearchResults(max_results=1)
    tools = [search_tool]
    llm = build_llm(SECTION_RESEARCHER_MODEL, tools, api_key=api_key)
    return build_react_agent(llm, tools)


SECTION_RESEARCHER_PROMPT = """Find 2-3 facts for this section. Use search tool once.

Return ONLY JSON: {{"facts": [{{"fact": "...", "source": "..."}}]}}

SECTION: {section}
TOPIC: {topic}"""


def run_section_researcher(topic: str, section: str, api_key: str = None) -> dict:
    import json, re
    agent = build_section_researcher(api_key=api_key)
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

{section_role}

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


def run_writer(topic: str, section: str, audience: str, section_research: dict, narrative: dict, feedback: str = "", api_key: str = None, cerebras_api_key: str = None) -> dict:
    import json, re
    
    para_path = Path(__file__).parent / "para.md"
    writing_guidelines = para_path.read_text(encoding="utf-8")
    
    gs_info = ""
    if audience == "UPSC":
        gs_info = f"GS Paper: {narrative.get('gsPaper')}\nSubject: {narrative.get('subject')}\nInclude UPSC-relevant examples where appropriate."
    
    facts_text = "\n".join([f"- {f['fact']} ({f.get('source', '')})" for f in section_research.get("facts", [])])
    
    outline = narrative.get("outline", [])
    num_sections = len(outline)
    target_words = BLOG_TARGET_LENGTH // num_sections if num_sections > 0 else 200
    
    section_role = ""
    if outline:
        def clean(s):
            return re.sub(r"[^a-zA-Z0-9]", "", s).lower()
        cleaned_sec = clean(section)
        if cleaned_sec == clean(outline[0]):
            section_role = "SECTION ROLE: This is the INTRODUCTION section. Start with an engaging, attention-grabbing hook (such as a shocking fact, rhetorical question, or real-life anecdote) to immediately pull the reader in."
        elif cleaned_sec == clean(outline[-1]):
            section_role = "SECTION ROLE: This is the CONCLUSION section. End with a clear takeaway or call-to-action / question to prompt the reader to think or reply."
            
    feedback_text = f"\nREVIEWER FEEDBACK:\n{feedback}\n\nRewrite addressing the above issues." if feedback else ""
    
    prompt = WRITER_PROMPT.format(
        section=section,
        topic=topic,
        audience=audience,
        target_words=target_words,
        section_role=section_role,
        facts=facts_text,
        gs_info=gs_info,
        writing_guidelines=writing_guidelines,
        feedback=feedback_text
    )

    raw = invoke_agent_with_fallback(prompt, WRITER_MODEL, api_key=api_key, cerebras_api_key=cerebras_api_key)

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

def run_section_pipeline(topic: str, section: str, audience: str, narrative: dict, api_key: str = None, cerebras_api_key: str = None) -> dict:
    section_research = run_section_researcher(topic, section, api_key=api_key)
    
    written_section = None
    review = None
    
    for attempt in range(MAX_RETRIES + 1):
        feedback = review["feedback"] if review and review["humanScore"] < 0.7 else ""
        
        written_section = run_writer(topic, section, audience, section_research, narrative, feedback, api_key=api_key, cerebras_api_key=cerebras_api_key)
        review = run_reviewer(written_section["content"])
        
        if review["humanScore"] >= 0.7:
            break
    
    return {
        "section": {
            "sectionTitle": written_section["sectionTitle"],
            "content": written_section["content"],
            "humanScore": review["humanScore"],
            "image": written_section["image"]
        },
        "facts": section_research.get("facts", [])
    }


# ── Reference Generator ──────────────────────────────────────────────────────

def generate_references(main_research: dict, section_researches: list) -> dict:
    all_sources = []

    def clean_url(url: str) -> str:
        url = url.strip()
        if not url:
            return ""
        # Check if it has spaces or doesn't have a dot (likely an organization name, not a URL)
        if " " in url or "." not in url:
            return ""
        # Prepend https:// if no protocol scheme is specified
        if not (url.startswith("http://") or url.startswith("https://")):
            return "https://" + url
        return url
    
    for finding in main_research.get("findings", []):
        url = clean_url(finding.get("url", ""))
        if url:
            all_sources.append({
                "url": url,
                "title": finding.get("title", "")
            })
    
    for section_research in section_researches:
        for fact in section_research.get("facts", []):
            source = fact.get("source", "")
            url = clean_url(source)
            if url:
                all_sources.append({
                    "url": url,
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
- title: A strong, engaging, benefit-driven or curiosity-sparking headline (e.g. "How India is Secretly Winning the Renewable Energy Race" or "10 Ways to Save Time Every Morning" rather than dry academic titles), includes primary keyword, 50-70 chars
- metaTitle: same as title or slight variation, under 70 chars
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

    prompt = METADATA_PROMPT.format(
        topic=topic,
        audience=audience,
        subject=narrative.get("subject", ""),
        content_summary=content_summary,
        seo_guidelines=seo_guidelines,
        word_count=total_words
    )

    raw_response = invoke_agent_with_fallback(prompt, METADATA_MODEL)

    parsed = robust_json_loads(raw_response)

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

    prompt = MCQ_PROMPT.format(
        num_questions=MCQ_COUNT,
        topic=topic,
        audience=audience,
        sections_summary=sections_summary
    )

    raw_response = invoke_agent_with_fallback(prompt, MCQ_MODEL)

    print(f"[MCQ] Raw model response (first 300 chars):\n{raw_response[:300]}")

    parsed = robust_json_loads(raw_response)
    questions = parsed.get("mcqs", [])
    valid_questions = []
    for q in questions:
        if isinstance(q, dict) and "options" in q:
            opts = q["options"]
            if isinstance(opts, dict) and all(k in opts for k in ["A", "B", "C", "D"]):
                valid_questions.append(q)
    print(f"[MCQ] Parsed result. Questions count: {len(valid_questions)}")

    return {
        "mcqs": valid_questions
    }


# ── UPSC Mains Callout Generator ─────────────────────────────────────────────

UPSC_CALLOUT_PROMPT = """You are a UPSC Mains exam specialist. Based on this blog topic and content, generate a UPSC Mains practice callout.

TOPIC: {topic}
GS PAPER: {gs_paper}
SUBJECT: {subject}

BLOG SUMMARY:
{content_summary}

Return ONLY valid JSON:
{{
  "mainsQuestion": "A realistic UPSC Mains 250-word question on this topic",
  "keywordsToWrite": ["keyword1", "keyword2", "keyword3"],
  "approach": "Brief 1-line approach to answer this question"
}}

No extra text."""


def run_upsc_callout(topic: str, gs_paper: str, subject: str, sections: list) -> dict:
    import json, re

    content_summary = "\n".join([
        f"- {s['sectionTitle']}: {s['content'][:150]}..."
        for s in sections
    ])

    prompt = UPSC_CALLOUT_PROMPT.format(
        topic=topic,
        gs_paper=gs_paper,
        subject=subject,
        content_summary=content_summary
    )

    try:
        raw_response = invoke_agent_with_fallback(prompt, NARRATIVE_MODEL)
        match = re.search(r"\{[\s\S]*\}", raw_response)
        parsed = json.loads(match.group()) if match else {}
    except Exception:
        parsed = {}

    return {
        "mainsQuestion": parsed.get("mainsQuestion", ""),
        "keywordsToWrite": parsed.get("keywordsToWrite", []),
        "approach": parsed.get("approach", "")
    }


def run_topic_ideator(audience: str, existing_topics: list) -> list:
    import json
    existing_str = "\n".join(f"- {t}" for t in existing_topics) if existing_topics else "None yet."
    audience_hint = {
        "UPSC": "GS I–IV syllabus (polity, economy, environment, society, international relations, science & technology). Suitable for UPSC essay or answer writing.",
        "Professional": "Business, technology, productivity, leadership, industry trends.",
        "General": "Broad interest topics: health, culture, science, society, travel."
    }.get(audience, "general interest")
    prompt = f"""You are a Topic Ideator for an AI blog machine. Suggest exactly 5 fresh, specific, trending blog topics for the "{audience}" audience.

Audience focus: {audience_hint}

Already published topics (DO NOT suggest anything similar to these):
{existing_str}

Rules:
- Be specific, not generic (e.g. "Impact of AI on India's IT Sector" not just "Artificial Intelligence")
- Each topic must be clearly different from all existing ones
- Topics must be timely and relevant for 2025-2026
- Return ONLY valid JSON, no extra text

Return:
{{
  "topics": [
    "Topic 1",
    "Topic 2",
    "Topic 3",
    "Topic 4",
    "Topic 5"
  ]
}}"""

    raw = invoke_agent_with_fallback(prompt, MCQ_MODEL)
    try:
        import re
        match = re.search(r"\{[\s\S]*\}", raw)
        parsed = json.loads(match.group()) if match else {}
        return parsed.get("topics", [])
    except Exception:
        return []


# ── Intra-Link Engine (Hybrid: LLM keywords + section frequency) ─────────────

def apply_intra_links(sections: list, keywords: list = []) -> list:
    """
    Links LLM-extracted keywords (primaryKeyword, relatedKeywords, tags) across
    sections of the blog. For each keyword:
      - Finds which section mentions it the most (the "home" section)
      - In all other sections that mention it, replaces the FIRST occurrence
        with a [[LINK:home_idx:original_text]] marker
    Supports multi-word phrases, hyphenated terms, and acronyms.
    Falls back gracefully if no keywords are supplied.
    """
    import re

    if not keywords or not sections:
        return sections

    # Deduplicate and sort keywords: longest first so multi-word phrases are
    # matched before their sub-words (e.g. "Climate Change" before "Change")
    seen = set()
    unique_keywords = []
    for kw in keywords:
        kw_clean = kw.strip()
        if kw_clean and kw_clean.lower() not in seen:
            seen.add(kw_clean.lower())
            unique_keywords.append(kw_clean)
    unique_keywords.sort(key=len, reverse=True)

    # For each keyword, count occurrences in each section to find the "home" section
    # (the section that discusses it the most — likely the one defining or explaining it)
    link_map = {}  # {keyword_lower: (home_section_idx, keyword_original_case)}
    for kw in unique_keywords:
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        counts = [len(pattern.findall(s['content'])) for s in sections]
        max_count = max(counts)
        if max_count == 0:
            continue  # keyword not found in any section — skip
        home_idx = counts.index(max_count)
        link_map[kw.lower()] = (home_idx, kw)

    # Apply [[LINK]] markers — only the FIRST occurrence per keyword per section
    # Never link a keyword back to its own home section
    result = []
    for src_idx, section in enumerate(sections):
        content = section['content']
        for kw_lower, (home_idx, kw_original) in link_map.items():
            if home_idx == src_idx:
                continue  # This is the home section — don't self-link
            # Build a pattern that matches whole-word, including hyphens and slashes
            # so "HWC" doesn't match inside "NHWC", and "climate change" matches
            # "Climate Change" anywhere in the text
            escaped = re.escape(kw_original)
            pattern = re.compile(r'(?<![A-Za-z0-9\-])(' + escaped + r')(?![A-Za-z0-9\-])', re.IGNORECASE)
            match = pattern.search(content)
            if match:
                replacement = f'[[LINK:{home_idx}:{match.group(1)}]]'
                content = content[:match.start()] + replacement + content[match.end():]
        result.append({**section, 'content': content})
    return result


def generate_blog(topic: str, audience: str) -> dict:
    print(f"[0/6] Validating topic: {topic}")
    validation = validate_topic(topic)
    if not validation["valid"]:
        return {"error": validation["reason"]}

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
        sections.append(result["section"])
        section_researches.append({"facts": result["facts"]})

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
