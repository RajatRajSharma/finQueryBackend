# FinQuery — Week 2 Plan (Make it impressive)

> **Goal of Week 2:** take the working Week 1 slice and make the answers *visibly better and nicer* — **hybrid retrieval (dense + BM25) → Cohere reranking → richer citations in the UI → SSE token streaming → UI polish.** Keep a working slice at all times: every change is additive and falls back to the Week 1 path if a key/dep is missing.
>
> Read [finQueryArchitecture.md](finQueryArchitecture.md) (§4.2 query pipeline) first. This implements **Phase 2** from [Idea1.md](Idea1.md).

---

## Where this sits in the 3-week project

| Week | Theme | Deliverable |
|---|---|---|
| Week 1 ✅ | Core RAG end-to-end | Upload a 10-K, ask, get a correct grounded answer |
| **Week 2 (this file)** | Make it impressive | Hybrid search + Cohere rerank + citations + SSE streaming + UI polish |
| Week 3 | Differentiators + deploy | Agentic routing + RAGAS dashboard, then **½ week deployment** |

**Design rule carried over from Week 1:** every new vendor goes behind an interface and is wired in `core/factory.py` — adding Cohere = one new `Reranker` class + one `get_reranker()` builder, nothing in the routers changes. See [factory.py](../app/core/factory.py).

---

## Pre-flight (Day 0 — ~1 hr)

- ⏳ Get a **Cohere API key** → `COHERE_API_KEY` in `.env` (https://dashboard.cohere.com/api-keys)
- ⏳ Uncomment the **Week 2 deps** in [requirements.txt](../requirements.txt) and `pip install -r requirements.txt`:
  `rank-bm25`, `llama-index-retrievers-bm25`, `cohere`, `llama-index-postprocessor-cohere-rerank`, `sse-starlette`
- ⏳ Add Week 2 knobs to `config.py` + `.env.example`: `RERANK_PROVIDER=cohere`, `RERANK_MODEL`, `RETRIEVE_CANDIDATES=20`, `HYBRID_ALPHA=0.5`, `ENABLE_RERANK=true`, `ENABLE_HYBRID=true`
- ⏳ Confirm Week 1 still green: `pytest -q` (5/5) and a live Apple query still returns a cited answer

> **Free-tier quota reminder:** Gemini embeds are capped ~100/min — re-ingesting for BM25 stays small, but don't bulk re-embed all 8 reports in one go (see Week 1 learnings).

---

## Day 1 — Hybrid retrieval (dense + BM25 keyword)

Adds the sparse half of [§4.2 step 3](finQueryArchitecture.md). Vector search nails *meaning*; BM25 nails *exact terms* ("Q4 2024", ticker symbols, line-item names). Fusing both catches what either misses.

- ⏳ New interface `SparseRetriever` (or `KeywordIndex`) in `core/interfaces.py` — `search(question, k) -> list[SearchHit]`
- ⏳ `clients/bm25_index.py` (or `processing/`) — wrap `llama-index-retrievers-bm25` / `rank-bm25` over the stored chunk text
- ⏳ Decide **where BM25 lives** (write it down): rebuild the index from Qdrant payloads on startup/after each ingest (simplest), *or* persist it. Note the trade-off in the file docstring.
- ⏳ `services/retrieval.py` — add a `HybridRetriever` path: run dense + sparse, **fuse** (Reciprocal Rank Fusion or weighted by `HYBRID_ALPHA`) → top `RETRIEVE_CANDIDATES` (~20)
- ⏳ `factory.py` — `get_sparse_retriever()` + assemble hybrid into `get_retrieval_service()`, gated by `ENABLE_HYBRID`
- ⏳ Tests: extend `tests/fakes.py` with a fake sparse retriever; assert fusion ordering deterministically (no infra)

**End of day:** `/query` retrieves ~20 fused candidates from dense + keyword search; falls back to dense-only if `ENABLE_HYBRID=false`.

---

## Day 2 — Cohere reranking

Implements [§4.2 step 4](finQueryArchitecture.md). Take the ~20 fused candidates and let a cross-encoder keep the genuinely-best 3–5. This is the single biggest answer-quality lever.

- ⏳ New interface `Reranker` in `core/interfaces.py` — `rerank(question, hits, top_n) -> list[SearchHit]`
- ⏳ Fill the `clients/cohere_client.py` **stub** → `CohereReranker(Reranker)` (the ONLY file importing the `cohere` SDK), raising `ConfigurationError` on missing key and translating Cohere API errors to `UpstreamServiceError` → 503 (mirror the Gemini pattern in [gemini_client.py](../app/clients/gemini_client.py))
- ⏳ `factory.py` — `get_reranker()` (provider switch), inject into `RetrievalService`, gated by `ENABLE_RERANK`
- ⏳ Pipeline: hybrid → `RETRIEVE_CANDIDATES` (~20) → rerank → `TOP_K` (3–5) → generate
- ⏳ Tests: fake reranker that reorders predictably; assert only `top_n` survive

**End of day:** answers are built from reranked top chunks; toggle `ENABLE_RERANK=false` to compare.

---

## Day 3 — SSE token streaming

Implements [§4.2 step 7](finQueryArchitecture.md). The answer "types out" live instead of appearing after a pause — the single biggest *perceived* speed/quality win.

- ⏳ Extend `LLMProvider` with `generate_stream(prompt) -> Iterator[str]`; implement on `GeminiLLM` via the SDK's streaming API (keep the existing non-streaming `generate()` for evals/tests)
- ⏳ `services/generation.py` — `generate_answer_stream(question, contexts)` yielding text deltas
- ⏳ `routers/query.py` — add `POST /query/stream` returning `text/event-stream` via `sse-starlette`; send the **answer tokens first, then a final `citations` event** (so the UI can render chips once retrieval metadata is known). Keep `POST /query` as the non-streaming path.
- ⏳ Frontend `src/shared/api/` — a streaming helper (fetch + `ReadableStream`/`EventSource`) and a `useStreamingQuery` hook
- ⏳ Frontend `Chat.tsx` / `ChatArea` — append tokens to the assistant bubble as they arrive (replaces the single pending→final swap from Week 1), then attach citations on the final event

**End of day:** ask a question in the browser and watch the answer stream token-by-token, citations appearing at the end.

---

## Day 4 — Citations + UI polish

Implements [§4.2 step 8](finQueryArchitecture.md) richly, and makes the whole thing look like a product. (The frontend already uses a feature-based structure with a CSS design-token system — `src/styles/tokens.css` — not Tailwind; polish within that system, don't rip it out.)

- ⏳ Backend already returns `snippet` + `score` per citation — surface them: expandable citation chips showing the source file, page, score, and snippet preview
- ⏳ `features/chat` — tidy message bubbles, streaming caret, copy-answer button, scroll-to-latest
- ⏳ `features/documents` — clearer processing/ready/error states (carried from Week 1), multi-doc "ask across all reports" affordance
- ⏳ Empty/loading/error polish across the chat + documents panels; mobile-reasonable layout
- ⏳ Verify `npm run build` + `npm run lint` stay green

**End of day:** the UI is demo-ready — streamed answers with clean, clickable citations.

---

## Day 5 — Quality pass, measure, buffer

- ⏳ Tune retrieval: `RETRIEVE_CANDIDATES`, `HYBRID_ALPHA`, `TOP_K`, chunk size — eyeball answer quality on 5–10 real questions across 2–3 reports
- ⏳ Capture an informal **before/after**: dense-only vs hybrid+rerank on the same questions (the rigorous RAGAS numbers come in Week 3 — this is the qualitative preview)
- ⏳ Update `README.md`: hybrid + rerank + streaming sections, new env vars, the `ENABLE_*` toggles
- ⏳ Commit both repos with a clean Phase-2 state
- ⏳ **Buffer** — streaming/SSE and BM25 persistence usually eat a half-day; this absorbs it

**End of Week 2 demo:** ask a question → answer streams in live → reranked, grounded → citations with page + snippet. Visibly better than Week 1.

---

## Explicitly OUT of scope this week (don't get pulled in)

- ❌ Agent router (answer / clarify / web-search) → Week 3
- ❌ RAGAS evaluation + eval dashboard wiring → Week 3
- ❌ Deployment / prod Docker / Qdrant Cloud → Week 3 (½ week)
- ❌ Auth, multi-user, persistence of chat history → not in this project's scope

> Rule for the week: if it doesn't make the answer **more accurate** or the demo **more impressive**, it waits.
