import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ai import (
    run_researcher,
    run_narrative_agent,
    run_section_pipeline,
    generate_references,
    run_metadata_generator,
    run_mcq_generator,
    run_upsc_callout,
    apply_intra_links,
    validate_topic,
    save_blog_to_supabase,
    delete_blog_from_supabase,
    get_supabase_topics,
    topic_similarity,
    supabase_request,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    topic: str
    audience: str


class RegenerateRequest(BaseModel):
    topic: str
    audience: str
    sectionTitle: str
    narrative: dict


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_blog(topic: str, audience: str):
    loop = asyncio.get_event_loop()

    yield sse("status", {"step": "validator", "message": "Validating topic...", "done": False})
    validation = await loop.run_in_executor(None, validate_topic, topic)
    if not validation["valid"]:
        # Check if this is a Supabase conflict (similar topic exists)
        if validation.get("conflict"):
            yield sse("conflict", {
                "message": validation["reason"],
                "conflictSlug": validation.get("conflictSlug", ""),
                "conflictTitle": validation.get("conflictTitle", "")
            })
        else:
            yield sse("error", {"message": validation["reason"]})
        return
    yield sse("status", {"step": "validator", "message": "Topic validated", "done": True})

    yield sse("status", {"step": "researcher", "message": "Researching topic...", "done": False})
    main_research = await loop.run_in_executor(None, run_researcher, topic)
    yield sse("status", {"step": "researcher", "message": "Research complete", "done": True, "data": {
        "sources": main_research["sources"],
        "findingsCount": len(main_research["findings"])
    }})

    yield sse("status", {"step": "narrative", "message": "Building outline...", "done": False})
    narrative = await loop.run_in_executor(None, run_narrative_agent, topic, audience, main_research)
    yield sse("status", {"step": "narrative", "message": "Outline ready", "done": True, "data": {
        "outline": narrative["outline"],
        "gsPaper": narrative.get("gsPaper"),
        "subject": narrative.get("subject")
    }})

    sections = []
    section_researches = []

    for i, section in enumerate(narrative["outline"]):
        yield sse("status", {"step": f"section_{i}", "message": f"Writing: {section}", "done": False})
        result = await loop.run_in_executor(None, run_section_pipeline, topic, section, audience, narrative)
        sections.append(result["section"])
        section_researches.append({"facts": result["facts"]})
        yield sse("section", {"index": i, "section": result["section"]})
        yield sse("status", {"step": f"section_{i}", "message": f"Done: {section}", "done": True, "data": {
            "humanScore": result["section"]["humanScore"]
        }})

    yield sse("status", {"step": "references", "message": "Generating references...", "done": False})
    references = generate_references(main_research, section_researches)
    yield sse("status", {"step": "references", "message": "References ready", "done": True})

    yield sse("status", {"step": "metadata", "message": "Generating metadata...", "done": False})
    metadata = await loop.run_in_executor(None, run_metadata_generator, topic, audience, narrative, sections)
    yield sse("status", {"step": "metadata", "message": "Metadata ready", "done": True})

    # Generate MCQs
    yield sse("status", {"step": "mcqs", "message": "Generating quiz...", "done": False})
    mcqs = await loop.run_in_executor(None, run_mcq_generator, topic, audience, sections)
    yield sse("status", {"step": "mcqs", "message": "Quiz ready", "done": True})

    # UPSC Mains callout (only for UPSC audience)
    upsc_callout = None
    if audience == "UPSC" and narrative.get("gsPaper"):
        yield sse("status", {"step": "upsc_callout", "message": "Generating UPSC Mains callout...", "done": False})
        upsc_callout = await loop.run_in_executor(
            None, run_upsc_callout,
            topic, narrative["gsPaper"], narrative.get("subject", ""), sections
        )
        yield sse("status", {"step": "upsc_callout", "message": "Mains callout ready", "done": True})

    # Apply intra-linking markers to section content before sending the payload
    linked_sections = apply_intra_links(sections)

    blog_payload = {
        "metadata": metadata,
        "narrative": {
            "audience": narrative["audience"],
            "subject": narrative["subject"],
            "gsPaper": narrative.get("gsPaper"),
            "writingInstructions": narrative["writingInstructions"]
        },
        "sections": linked_sections,
        "references": references["references"],
        "mcqs": mcqs["mcqs"],
        "upscCallout": upsc_callout
    }

    # NOTE: Blog is NOT saved here — it is saved only when the user clicks Publish
    yield sse("complete", blog_payload)


@app.post("/generate")
async def generate(req: GenerateRequest):
    return StreamingResponse(
        stream_blog(req.topic, req.audience),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/regenerate-section")
async def regenerate_section(req: RegenerateRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, run_section_pipeline, req.topic, req.sectionTitle, req.audience, req.narrative
    )
    return result["section"]


@app.get("/blogs")
async def list_blogs():
    result = get_supabase_topics()
    return result or []


@app.get("/blog/{slug}")
async def get_blog(slug: str):
    result = supabase_request(
        "GET", "blogs",
        params={"select": "data", "slug": f"eq.{slug}", "limit": "1"}
    )
    if result and len(result) > 0:
        return result[0]["data"]
    return {}


@app.delete("/blog/{slug}")
async def delete_blog(slug: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, delete_blog_from_supabase, slug)
    return {"deleted": slug}


class PublishRequest(BaseModel):
    topic: str
    audience: str
    blog: dict


@app.post("/publish")
async def publish_blog(req: PublishRequest):
    loop = asyncio.get_event_loop()
    slug = req.blog.get("metadata", {}).get("slug", "")
    if not slug:
        return {"error": "Missing slug"}
    await loop.run_in_executor(
        None, save_blog_to_supabase,
        slug, req.topic, req.audience, req.blog
    )
    return {"published": slug}
