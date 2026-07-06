# AI Blog Machine (Aspire IAS)

A production-grade, multi-agent blog generation dashboard built to generate high-quality, SEO-optimized, and "human-like" articles targeting specific audiences (such as Civil Services UPSC aspirants).

---

## 🏗️ Architecture & Agent Workflows

The application coordinates a cooperative team of **6 specialized agents** communicating through state transitions and Server-Sent Events (SSE) to generate the final blog:

```mermaid
graph TD
    subgraph Client ["Client (Next.js Dashboard)"]
        UI[Home Page] -->|POST /generate| API_Client[api.ts]
        API_Client -->|Listen SSE| Progress[WorkflowProgress]
        UI -->|Regenerate Section| API_Client
    end

    subgraph Backend ["Backend (FastAPI Team)"]
        API_Client -->|SSE Stream| Main[main.py]
        Main -->|1. Validate| Val[Topic Validator]
        Main -->|2. Search| Res[Researcher Agent]
        Main -->|3. Structure| Nar[Narrative Agent]
        Main -->|4. Section Pipeline| Sec[Section Writer & Review Loop]
        Sec -->|4a. Search| SecRes[Section Researcher]
        Sec -->|4b. Write| Writer[Content Writer]
        Sec -->|4c. Audit| Rev[Reviewer Agent]
        Writer <-->|Feedback Loop| Rev
        Main -->|5. References| Ref[Reference Generator]
        Main -->|6. SEO Metadata| Meta[Metadata Generator]
        Main -->|7. MCQs| MCQ[MCQ Generator]
    end
    
    subgraph ThirdParty ["Third-Party Integrations"]
        Res & SecRes -->|Search queries| Tavily[Tavily Search API]
        Rev -->|Human Score Audit| Sapling[Sapling AI Detector API]
        Writer -->|Primary Writer| Cerebras[Cerebras API / Groq Fallback]
        Val & Nar & Meta & MCQ -->|Text generation| Groq[Groq API]
    end
```

### The Agent Team
1. **Topic Validator**: Evaluates inputs to reject gibberish, political bias, or unsupported short prompts.
2. **Researcher**: Executes web queries using Tavily to compile top findings and source URLs.
3. **Narrative Agent**: Groups findings into a 4-section outline, maps the topic to General Studies syllabus papers (GS-I to GS-IV) for UPSC mode, and specifies audience-aware writing guidelines.
4. **Section Researcher**: Conducts focused searches on individual section outlines.
5. **Content Writer**: Drafts section contents using strict stylistic rules (sentence variations, simplicity connectors) from `para.md`.
6. **Reviewer (Sapling Detector Loop)**: Automatically audits draft paragraphs for AI markers. If the human-likeness rating drops below 70%, it fires a critique back to the Writer for a rewrite (capped at 2 retries).

---

## ⚡ Key Features

- **Real-Time Pipeline Status**: The generation progress is streamed to the UI in real-time, displaying structural decisions, source URLs, and section-level human-likeness scores.
- **Section-Level Controls**: Allows editors to manually run the review loop on an individual section cards rather than rebuilding the entire blog.
- **Interactive MCQ Quiz**: Automatically builds a custom 5-question conceptual quiz with instant scoring and full explanations.
- **Dynamic Image Suggester**: Generates customized visual prompts and captions for suggested sections, supporting local image uploads on the final published page.

---

## 🚀 Setup & Local Execution

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Core dependencies include fastapi, uvicorn, langchain-groq, langchain-community, langgraph, cerebras-cloud, requests, and python-dotenv)*
3. Create a `.env` file in the root project directory (see **Environment Variables** below).
4. Run the FastAPI development server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### 2. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the Next.js development server:
   ```bash
   npm run dev
   ```
4. Access the web dashboard at `http://localhost:3000`.

---

## 🔑 Environment Variables
Create a file named `.env` in the root folder of the project with the following keys:

```ini
# Core LLM Providers
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=csk-...

# Search & Research Integration
TAVILY_API_KEY=tvly-...

# AI Detection & Quality Auditing
SAPLING_API_KEY=...
SAPLING_PUBLIC_KEY=...

# Frontend Deployment URL (Optional for production)
NEXT_PUBLIC_API_URL=https://your-backend-api.com
```
