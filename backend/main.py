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
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
        sections.append(result)
        section_researches.append({"facts": []})
        yield sse("section", {"index": i, "section": result})
        yield sse("status", {"step": f"section_{i}", "message": f"Done: {section}", "done": True, "data": {
            "humanScore": result["humanScore"]
        }})

    yield sse("status", {"step": "references", "message": "Generating references...", "done": False})
    references = generate_references(main_research, section_researches)
    yield sse("status", {"step": "references", "message": "References ready", "done": True})

    yield sse("status", {"step": "metadata", "message": "Generating metadata...", "done": False})
    metadata = await loop.run_in_executor(None, run_metadata_generator, topic, audience, narrative, sections)
    yield sse("status", {"step": "metadata", "message": "Metadata ready", "done": True})

    yield sse("status", {"step": "mcqs", "message": "Generating quiz...", "done": False})
    mcqs = await loop.run_in_executor(None, run_mcq_generator, topic, audience, sections)
    yield sse("status", {"step": "mcqs", "message": "Quiz ready", "done": True})

    yield sse("complete", {
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
    })


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
    return result
