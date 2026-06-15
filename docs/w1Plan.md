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

- ✅ Install: Node 20+ (v22), Python 3.13, **Docker (v29 + Compose v5)**, Git, VS Code
- ✅ Confirm repo folders exist: `finQueryBackend/` (this repo) and `finQueryFrontend/`
- ✅ Get a **Gemini API key** → in `.env` (using `gemini-embedding-001` + `gemini-2.5-flash`)
- ✅ (Cohere key NOT needed in Week 1 — that's Week 2 reranking)
- ✅ Real text-based 10-Ks in `data/raw/` (8 companies; the earlier image-only set was replaced).
  `scripts/make_sample_pdf.py` also generates a synthetic `Acme.pdf` as an offline/quota-free fixture
- ✅ Confirm `.env`, `venv/`, `data/` are in `.gitignore`

> Note: the architecture lists Gemini as the LLM/embeddings provider ([finQueryArchitecture.md §2](finQueryArchitecture.md)). `Idea1.md` mentions OpenAI — **follow the architecture doc (Gemini)** since it's the free-tier choice.

---

## Day 1 — Backend skeleton + Qdrant running

- ✅ Create Python venv in `finQueryBackend/`, `pip install` the backend packages
- ✅ Start Qdrant via `docker compose up -d qdrant` (Qdrant 1.18, storage volume persisted)
- ✅ Confirm Qdrant reachable — `/readyz` = "all shards are ready"; dashboard at :6333/dashboard
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
- ✅ Test: uploaded the real `AppleInc.pdf` live → 32 pages parsed, 64 chunks embedded + stored
  in Qdrant (the earlier image-only PDFs had correctly produced 0 chunks — no extractable text)

**End of day:** Apple 10-K is chunked, embedded, and stored.

---

## Day 3 — Query pipeline (retrieve → generate)

Simplified [query LLD](finQueryArchitecture.md#L136) — **dense retrieval only** this week (no hybrid/rerank/agent/streaming). Logic in `services/retrieval.py` + `services/generation.py`.

- ✅ `services/retrieval.py` — embed question, vector-search, return top-k (tested w/ fake store)
- ✅ `services/generation.py` — prompt build + Gemini call (verified live: grounded, cited answer)
- ✅ `models/schemas.py` — `QueryRequest` / `QueryResponse` / `Citation` shapes
- ✅ `routers/query.py` — `POST /query` runs retrieve → generate → cite
- ✅ Test via curl: full retrieve→generate proven live on the real Apple 10-K — "net sales" →
  "$111,184M (Products $80,208M, Services $30,976M), p.4" with citations (scores ~0.74). A
  2030-dividend question correctly returns "not in the documents" (grounding guardrail holds).

> Bonus done: `services/citations.py`, `core/` abstraction layer (interfaces + factory), and a fake-backed **5/5 passing test suite** (runs with no infra).

**End of day:** backend answers a question correctly from the terminal. **This is the core RAG milestone.**

---

## Day 4 — Frontend wired to backend

The frontend shell was already scaffolded (Vite + React 19 + TS, feature-based);
Day 4's real work was replacing its mock data with live backend calls.

- ✅ `finQueryFrontend/` scaffolded (Vite React-TS) with packages installed
- ✅ `.env` → `VITE_API_BASE_URL=http://localhost:8000` (+ `.env.example`, gitignored)
- ✅ `src/shared/api/client.ts` — `uploadPdf()`, `askQuestion()`, `checkReady()` + `ApiError`
- ✅ `DocumentsPanel` (file picker / drag-drop) wired to `/upload` — processing → ready/error
- ✅ `ChatArea` + `Chat.tsx` wired to `/query` — pending bubble → grounded answer + citations
- ✅ Confirm CORS: backend returns `access-control-allow-origin: http://localhost:5173`
  for both `/query` and the `/upload` preflight
- ✅ `npm run build` (tsc + vite) and `npm run lint` both pass

**End of day:** upload + ask + see answer, fully in the browser.

---

## Day 5 — End-to-end glue, cleanup, buffer

- ✅ Full pipeline run live: ingest the real `AppleInc.pdf` (64 chunks) → ask 3 questions
  (net sales / legal-risk / out-of-scope) → grounded, cited answers (verified via curl + CORS)
- ✅ Rough edges: loading "pending" bubble, error bubbles on failure, upload error state,
  empty-input guard (send disabled), and **upstream Gemini failures → clean 503** (not raw 500)
- ✅ `requirements.txt` kept curated/manual on purpose — NOT `pip freeze`d (that would leak the
  dev-only `fpdf2` + destroy the staged Week 2/3 comments). Verified complete for Week 1 imports.
- ✅ `README.md` (backend) covers setup, env vars, Docker, and how to run
- ✅ Commit both repos with a clean Phase-1 state
- ✅ **Buffer** absorbed: Gemini `gemini-2.5-flash` intermittently returns 503 "high demand";
  client/tests retry, and the backend now translates it to a clean 503

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
