# FinQuery — Week 1 Plan (Core RAG, end-to-end)

> **Goal of Week 1:** Upload a PDF → ask a question → get a correct, doc-grounded answer in the React UI. Ugly but functional. No hybrid search, no reranking, no streaming yet — those are Week 2. Keep a working slice at all times.
>
> Read [finQueryArchitecture.md](finQueryArchitecture.md) first. This plan implements **Phase 1** from [Idea1.md](Idea1.md).

---

## Where this sits in the 3-week project

| Week | Theme | Deliverable |
|---|---|---|
| **Week 1 (this file)** | Core RAG end-to-end | Ask one Apple 10-K a question, get a correct answer |
| Week 2 | Make it impressive | Hybrid search + Cohere rerank + citations + SSE streaming + UI polish |
| Week 3 | Differentiators + deploy | Agentic routing + RAGAS dashboard, then **½ week deployment** |

**Is ½ week for deployment enough?** Yes — backend is one FastAPI service (Dockerfile), frontend is a static build (Vercel/Netlify), and Qdrant uses the **Qdrant Cloud free tier** in prod. Budget ~3 days for Dockerfiles + deploy + README.

---

## Pre-flight (Day 0 — ~1–2 hrs, do before Day 1)

- ⏳ Install: Node 20+, Python 3.13, **Docker Desktop (not installed)**, Git, VS Code
- ✅ Confirm repo folders exist: `finQueryBackend/` (this repo) and `finQueryFrontend/`
- ✅ Get a **Gemini API key** → in `.env` (using `gemini-embedding-001` + `gemini-2.5-flash`)
- ✅ (Cohere key NOT needed in Week 1 — that's Week 2 reranking)
- ⏳ Download **1 real text-based PDF** — current 8 in `data/raw/` are image-only (no text)
- ✅ Confirm `.env`, `venv/`, `data/` are in `.gitignore`

> Note: the architecture lists Gemini as the LLM/embeddings provider ([finQueryArchitecture.md §2](finQueryArchitecture.md)). `Idea1.md` mentions OpenAI — **follow the architecture doc (Gemini)** since it's the free-tier choice.

---

## Day 1 — Backend skeleton + Qdrant running

- ✅ Create Python venv in `finQueryBackend/`, `pip install` the backend packages
- ⏳ Start Qdrant (Docker not installed — embedded mode available as fallback)
- ⏳ Confirm Qdrant dashboard loads at http://localhost:6333/dashboard
- ✅ Scaffold `app/main.py` (FastAPI app + CORS) + split `/health` & `/health/ready` routers
- ✅ `app/config.py` — loads `.env` (keys, chunk size, top_k, models, provider, FRONTEND_ORIGIN)
- ✅ Run `uvicorn app.main:app --reload --port 8000`, hit `/health` → OK

**End of day:** server boots, Qdrant up, `/health` returns OK.

---

## Day 2 — Ingestion pipeline (PDF → vectors in Qdrant)

Implements the [ingestion LLD](finQueryArchitecture.md#L90). Logic lives in `app/services/ingestion.py`.

- ✅ `clients/qdrant_client.py` — connect, create collection if missing (built; live-test pending Qdrant)
- ✅ `clients/gemini_client.py` — embedding wrapper (verified live, 768-dim)
- ✅ `services/ingestion.py`:
  - ✅ Parse PDF with `pypdf`, keep **page numbers** (needed for citations later)
  - ✅ Chunk with LlamaIndex `SentenceSplitter` (~512 tokens, small overlap)
  - ✅ Embed each chunk via Gemini
  - ✅ Store in Qdrant with payload: `{text, page, source_file, company, chunk_id}`
- ✅ `routers/upload.py` — `POST /upload` triggers ingestion
- ⏳ Test: upload a PDF, confirm vectors appear in Qdrant dashboard (needs Qdrant + real PDF)

**End of day:** Apple 10-K is chunked, embedded, and stored.

---

## Day 3 — Query pipeline (retrieve → generate)

Simplified [query LLD](finQueryArchitecture.md#L136) — **dense retrieval only** this week (no hybrid/rerank/agent/streaming). Logic in `services/retrieval.py` + `services/generation.py`.

- ✅ `services/retrieval.py` — embed question, vector-search, return top-k (tested w/ fake store)
- ✅ `services/generation.py` — prompt build + Gemini call (verified live: grounded, cited answer)
- ✅ `models/schemas.py` — `QueryRequest` / `QueryResponse` / `Citation` shapes
- ✅ `routers/query.py` — `POST /query` runs retrieve → generate → cite
- ⏳ Test via curl: full retrieve→generate answer (generation proven live; needs Qdrant for retrieval)

> Bonus done: `services/citations.py`, `core/` abstraction layer (interfaces + factory), and a fake-backed **5/5 passing test suite** (runs with no infra).

**End of day:** backend answers a question correctly from the terminal. **This is the core RAG milestone.**

---

## Day 4 — Frontend wired to backend

Minimal UI — no Tailwind polish yet (that's Week 2).

- ⏳ Scaffold `finQueryFrontend/` with Vite React-TS template, install packages
- ⏳ `.env` → `VITE_API_BASE_URL=http://localhost:8000`
- ⏳ `api/client.ts` — `uploadPdf()` and `askQuestion()` functions
- ⏳ `components/FileUpload.tsx` — pick a PDF, call `/upload`
- ⏳ `components/ChatBox.tsx` — type a question, call `/query`, render the answer
- ⏳ `App.tsx` — stack the two components
- ⏳ Confirm CORS: backend allows `http://localhost:5173`

**End of day:** upload + ask + see answer, fully in the browser.

---

## Day 5 — End-to-end glue, cleanup, buffer

- ⏳ Full run: upload a real 10-K in UI → ask 3 questions → all answered correctly
- ⏳ Fix the rough edges (loading state, error if Gemini/Qdrant down, empty-input guard)
- ⏳ `pip freeze > requirements.txt` (requirements.txt maintained manually for now)
- ⏳ Short `README.md` (backend): setup steps, env vars, how to run
- ⏳ Commit both repos with a clean Phase-1 state
- ⏳ **Buffer** — Days 1–4 always overrun somewhere; this absorbs it

**End of Week 1 demo:** In the React UI, upload the Apple 10-K and get a correct answer to a real question. ✅

---

## Explicitly OUT of scope this week (don't get pulled in)

- ❌ Hybrid search / BM25 → Week 2
- ❌ Cohere reranking → Week 2
- ❌ Source citations in UI → Week 2
- ❌ SSE token streaming → Week 2
- ❌ Agent router → Week 3
- ❌ RAGAS evaluation → Week 3
- ❌ Deployment / Docker prod → Week 3 (½ week)

> Rule for the week: if it isn't on the path to "upload → ask → correct answer," it waits.
