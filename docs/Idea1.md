# FinQuery — Agentic RAG over Annual Reports

**Short name:** `finquery`
**One-line pitch:** An agentic RAG application that lets users chat with real company annual reports (10-Ks), getting source-cited answers, with hybrid search, reranking, token streaming, and a built-in evaluation dashboard.

**Resume keywords this hits:** RAG, vector embeddings, semantic search, vector database (Qdrant), LlamaIndex, hybrid search (dense + BM25), reranking, FastAPI, LLM integration, agentic retrieval / tool-calling, token streaming (SSE), RAGAS evaluation, React, TypeScript, Docker.

---

## Tech Stack Overview

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS, SSE streaming |
| Backend | Python + FastAPI (async), Pydantic v2 |
| RAG orchestration | LlamaIndex |
| Embeddings | OpenAI `text-embedding-3-large` |
| Generation LLM | OpenAI GPT-4o (or Anthropic Claude) |
| Vector DB | Qdrant (Dockerized) |
| Retrieval | Hybrid: dense vectors + BM25 keyword, fused |
| Reranking | Cohere Rerank |
| Evaluation | RAGAS (faithfulness, answer relevance, context precision) |
| Infra / Deploy | Docker + docker-compose, Railway or Render |

---

## What to INSTALL (system-level / tooling)

Install these on your machine before writing any code.

### Core tooling
- **Node.js** (v20 LTS or newer) + npm — for the React frontend
- **Python** (3.11 or 3.12) — for the backend
- **Docker Desktop** — runs Qdrant locally and packages the app for deploy
- **Git** — version control
- A code editor — **VS Code** recommended

### Python environment (create a virtual env, then pip install)
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install \
  fastapi \
  "uvicorn[standard]" \
  pydantic \
  python-multipart \
  llama-index \
  llama-index-vector-stores-qdrant \
  llama-index-embeddings-openai \
  llama-index-llms-openai \
  qdrant-client \
  cohere \
  ragas \
  pypdf \
  rank-bm25 \
  python-dotenv \
  sse-starlette
```
(Freeze later with `pip freeze > requirements.txt`.)

### Frontend packages (run inside the React project)
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install tailwindcss @tailwindcss/vite
npm install lucide-react        # icons
npm install @microsoft/fetch-event-source   # clean SSE handling
```

### Vector DB (via Docker — no manual install)
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

### API keys needed (put in a .env file, never commit)
- `OPENAI_API_KEY` — embeddings + generation
- `COHERE_API_KEY` — reranking

---

## What to IMPORT (in code)

### Python backend imports
```python
# Web framework
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import uvicorn

# Environment
import os
from dotenv import load_dotenv

# RAG core (LlamaIndex)
from llama_index.core import VectorStoreIndex, StorageContext, Document, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.retrievers import VectorIndexRetriever

# Vector DB client
import qdrant_client

# Reranking
import cohere

# PDF parsing
from pypdf import PdfReader

# Keyword search
from rank_bm25 import BM25Okapi

# Evaluation
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
```

### Frontend imports (TypeScript / React)
```typescript
import { useState, useRef, useEffect } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { Upload, Send, FileText, BarChart3 } from "lucide-react";
```

---

## Documents We Are Using

**Corpus:** 8 real annual reports (10-K filings) from recognizable US public companies.

**Why real reports:** They are dense, table-heavy, 100-300 pages each — exactly the messiness that makes RAG look impressive. Saying "tested on real SEC filings" is a strong interview line.

**Starter set of 8:** Apple, Microsoft, Nvidia, Tesla, Amazon, Alphabet, Coca-Cola, Walmart.

### Where to get them (all free)
1. **SEC EDGAR** — official source for every US public company 10-K.
   - Search UI: https://www.sec.gov/cgi-bin/browse-edgar
   - Full-text search: https://efts.sec.gov/LATEST/search-index?q=
   - Filter by form type "10-K", download the document.
2. **Investor Relations pages** — cleaner, better-formatted PDFs.
   - Apple → investor.apple.com
   - Microsoft → microsoft.com/investor
   - Plus Tesla, Nvidia, Amazon, Alphabet, Coca-Cola, Walmart IR pages.
3. **AnnualReports.com** — https://www.annualreports.com — free library of glossy annual report PDFs, easy to bulk-download.

**Tip:** During development, ingest only 1-2 reports (re-embedding 8 long PDFs each time is slow and burns API credits). Batch-ingest all 8 once the pipeline is finalized. Prefer text-based PDFs; avoid scanned/image-only PDFs at first (they need OCR).

---

## 4-Phase Execution Plan

Each phase ends with something you can demo. Always keep a working slice.

### Phase 1 — Core RAG works end-to-end  *(~Week 1)*
**Goal:** Upload a PDF → answer questions from it in the React UI. Ugly but functional.
- Set up repo structure (backend/ and frontend/ folders, .env, .gitignore).
- Spin up Qdrant in Docker.
- Backend: PDF upload endpoint → parse with pypdf → chunk with SentenceSplitter → embed with OpenAI → store in Qdrant.
- Backend: `/query` endpoint → retrieve top-k chunks → send to LLM → return answer.
- Frontend: simple upload + chat box, calls the backend, shows the answer.
- **Demo at end:** Ask one Apple 10-K a question, get a correct answer.

### Phase 2 — Make it impressive  *(~Week 2)*
**Goal:** Turn the basic pipeline into something that looks production-grade.
- Add **hybrid search** (dense vectors + BM25 keyword, fused).
- Add **Cohere reranking** on retrieved chunks.
- Add **source citations** — show the exact chunk + page number behind each answer.
- Add **token streaming** (SSE) so the answer types out live.
- Polish the React UI with Tailwind (clean chat layout, file list, loading states).
- **Demo at end:** Streaming, cited answers across multiple ingested reports.

### Phase 3 — The differentiators  *(~Week 3, first half)*
**Goal:** Add the features that put you ahead of typical portfolio projects.
- **Agentic routing:** an agent decides — answer from docs, ask for clarification, or fall back to web search when docs don't cover the question (tool-calling).
- **RAGAS evaluation dashboard:** run faithfulness / answer relevance / context precision on a set of test questions, display scores in the UI.
- Ingest all 8 reports as the final corpus.
- **Demo at end:** Eval dashboard showing 0.9+ faithfulness; agent handling an out-of-scope question gracefully.

### Phase 4 — Deployment & presentation  *(~Week 3, second half)*
**Goal:** Make it live and resume-ready.
- Write `Dockerfile` for backend and frontend; wire up `docker-compose.yml` (backend + frontend + Qdrant).
- Deploy to **Railway** or **Render** (managed Qdrant or a hosted Qdrant Cloud free tier).
- Write a strong **README**: architecture diagram, screenshots, eval results, live demo link, setup instructions.
- Record a 60-second demo GIF/video for the README.
- **Deliverable:** Public GitHub repo + live URL you can link from your resume.

---

## Resume Bullet (target)
> Built an agentic RAG system (FastAPI, LlamaIndex, Qdrant) with hybrid dense+sparse retrieval and Cohere reranking, achieving 0.9+ faithfulness on RAGAS evals; React/TypeScript frontend with SSE token streaming and source-cited answers; fully Dockerized and deployed.

---

## Detailed Phase 1 Kickoff Checklist (do these first)
1. Install Node.js, Python 3.11+, Docker Desktop, Git, VS Code.
2. Create project folder `finquery/` with subfolders `backend/` and `frontend/`.
3. Create a Python virtual env in `backend/` and pip install the backend packages above.
4. Scaffold the React app in `frontend/` with the Vite TypeScript template and install frontend packages.
5. Get an **OpenAI API key** and a **Cohere API key**; put them in `backend/.env`.
6. Add `.env`, `venv/`, `node_modules/` to `.gitignore`.
7. Start Qdrant: `docker run -p 6333:6333 qdrant/qdrant` and confirm the dashboard loads at http://localhost:6333/dashboard.
8. Download 1 annual report (e.g., Apple's latest 10-K) from SEC EDGAR to test ingestion.
9. Build the upload → chunk → embed → store pipeline, then the query endpoint.
10. Wire the React chat box to the backend. Confirm an end-to-end answer.
