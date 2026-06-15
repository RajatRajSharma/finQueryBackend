# FinQuery — Week 2 Plan (Make it impressive)

> **Goal of Week 2:** take the working Week 1 slice and make the answers *visibly better and nicer* — **rich citations → Cohere reranking → hybrid retrieval (dense + BM25) → SSE token streaming → UI polish.** Keep a working slice at all times: every change is additive and gated behind an `ENABLE_*` flag, so it falls back to the Week 1 path if a key/dep is missing.
>
> Read [finQueryArchitecture.md](finQueryArchitecture.md) (§4.2 query pipeline) first. This implements **Phase 2** from [Idea1.md](Idea1.md).

**Status legend:** ✅ done · 🔄 in progress · ⏳ to do · ⏸ deferred (blocked on a key/dep)

---

## Where this sits in the 3-week project

| Week | Theme | Deliverable |
|---|---|---|
| Week 1 ✅ | Core RAG end-to-end | Upload a 10-K, ask, get a correct grounded answer |
| **Week 2 (this file)** | Make it impressive | Hybrid search + Cohere rerank + citations + SSE streaming + UI polish |
| Week 3 | Differentiators + deploy | Agentic routing + RAGAS dashboard, then **½ week deployment** |

**Design rule carried over from Week 1:** every new vendor goes behind an interface and is wired in `core/factory.py` — adding Cohere = one new `Reranker` class + one `get_reranker()` builder, nothing in the routers changes. See [factory.py](../app/core/factory.py).

---

## Execution order (risk-adjusted, not calendar order)

Ordered by **value ÷ risk** so the demo improves even if a hard item slips. Each day is independent and shippable on its own.

1. **Citations in the UI** — backend already returns `snippet`+`score`; pure frontend, no keys/deps. Easiest win. → *Day 1*
2. **Cohere reranking** — clean interface, one SDK call; biggest answer-quality lever. → *Day 2*
3. **Hybrid retrieval (BM25)** — local, no key, but LlamaIndex integration + "where does the index live" carry real friction. → *Day 3*
4. **SSE streaming** — biggest *perceived* win, but the fiddliest (POST + ReadableStream + trailing citations event). → *Day 4*
5. **Polish + measure** → *Day 5*

---

## Pre-flight (Day 0 — ~1–2 hrs)

- ⏳ Get a **Cohere API key** → `COHERE_API_KEY` in `.env` (https://dashboard.cohere.com/api-keys)
- ⏳ Uncomment the **Week 2 deps** in [requirements.txt](../requirements.txt) and `pip install -r requirements.txt`:
  `rank-bm25`, `llama-index-retrievers-bm25`, `cohere`, `llama-index-postprocessor-cohere-rerank`, `sse-starlette`
- ✅ Add Week 2 knobs to `config.py` + `.env.example`: `ENABLE_RERANK`, `RERANK_PROVIDER`, `RERANK_MODEL`, `RETRIEVE_CANDIDATES`, `ENABLE_HYBRID`, `HYBRID_ALPHA` (all default to the Week 1 behaviour)
- ⏳ **De-risk spikes (~1 hr each, do before committing a full day):**
  - SSE: a throwaway token round-trip (backend `sse-starlette` → browser `ReadableStream`) to learn the real cost
  - (Week 3) RAGAS: a 2-question RAGAS-on-Gemini run, to surface the Gemini-judge compat + quota issues early
- ⏳ Confirm Week 1 still green: `pytest -q` (5/5) and a live Apple query still returns a cited answer

> **Free-tier quota reminder:** Gemini embeds are capped ~100/min — re-ingesting for BM25 stays small, but don't bulk re-embed all 8 reports in one go (see the project memory + Week 1 learnings).

---

## Day 1 — Citations in the UI  ✅

Implements [§4.2 step 8](finQueryArchitecture.md) richly. The backend's `Citation` already carries `source_file`, `company`, `page_number`, `snippet`, and `score` — Week 1 only rendered file + page. Surface the rest. Pure frontend, no keys/deps, fully verifiable. (The frontend uses a feature-based structure + a CSS design-token system — `src/styles/tokens.css` — not Tailwind; polish within it.)

- ✅ Extend the frontend `Citation` type with optional `company`, `snippet`, `score`
- ✅ `Chat.tsx` — map the full citation (not just `{doc, page}`) from the `/query` response
- ✅ `ChatArea` — expandable citation chips: file · page · score%, click to reveal the snippet (native `<details>` for accessibility)
- ✅ Verified `npm run build` + `npm run lint` green; live `/query` confirms citations carry snippet + score (e.g. AppleInc.pdf p.9, 0.745)

**End of day:** ✅ every answer shows clickable citations with page, relevance score, and a snippet preview.

---

## Day 2 — Cohere reranking  ✅ (code) · ⏸ (live)

Implements [§4.2 step 4](finQueryArchitecture.md). Take ~20 candidates and let a cross-encoder keep the genuinely-best 3–5. The single biggest answer-quality lever. (Code lands now behind `ENABLE_RERANK=false`; flip on once the Cohere key is set.)

- ✅ New interface `Reranker` in `core/interfaces.py` — `rerank(question, hits, top_n) -> list[SearchHit]`
- ✅ Filled the `clients/cohere_client.py` **stub** → `CohereReranker(Reranker)` (the ONLY file importing the `cohere` SDK), raising `ConfigurationError` on missing key and translating Cohere errors to `UpstreamServiceError` → 503 (mirrors the Gemini pattern in [gemini_client.py](../app/clients/gemini_client.py))
- ✅ `factory.py` — `get_reranker()` returns `None` when `ENABLE_RERANK=false` and lazy-imports the SDK only when enabled (verified: app boots with cohere unimported); injected into `RetrievalService`
- ✅ `services/retrieval.py` — over-fetch `RETRIEVE_CANDIDATES` then rerank → `TOP_K`; with no reranker, behaves exactly like Week 1
- ✅ Tests: `FakeReranker` proves over-fetch + reorder + top_n trim (pytest 6/6)
- ⏸ **Live-verify** reranking against the real Cohere API — *deferred until `COHERE_API_KEY` is set + `ENABLE_RERANK=true` + `pip install cohere`*

**End of day (code):** ✅ rerank path built + fake-tested; `ENABLE_RERANK=true` + a key turns it on with zero router changes.

---

## Day 3 — Hybrid retrieval (dense + BM25 keyword)

Adds the sparse half of [§4.2 step 3](finQueryArchitecture.md). Vector search nails *meaning*; BM25 nails *exact terms* ("Q4 2024", ticker symbols, line-item names). Fusing both catches what either misses. (Needs the Week 2 deps installed — do this as a deliberate step; LlamaIndex sub-packages are unpinned and can churn the resolve.)

- ⏳ New interface `SparseRetriever` in `core/interfaces.py` — `search(question, k) -> list[SearchHit]`
- ⏳ `clients/bm25_index.py` — wrap `llama-index-retrievers-bm25` / `rank-bm25` over the stored chunk text
- ⏳ Decide **where BM25 lives** (write it in the docstring): rebuild from Qdrant payloads on startup/after ingest (simplest) vs persist. Note the trade-off.
- ⏳ `services/retrieval.py` — `HybridRetriever`: dense + sparse, **fuse** (RRF or weighted by `HYBRID_ALPHA`) → `RETRIEVE_CANDIDATES`, then the Day-2 reranker
- ⏳ `factory.py` — `get_sparse_retriever()`; assemble hybrid, gated by `ENABLE_HYBRID`
- ⏳ Tests: fake sparse retriever; assert fusion ordering deterministically (no infra)

**End of day:** `/query` fuses dense + keyword candidates; `ENABLE_HYBRID=false` falls back to dense-only.

---

## Day 4 — SSE token streaming

Implements [§4.2 step 7](finQueryArchitecture.md). The answer "types out" live — the biggest *perceived* win, and the fiddliest item. Do the spike first.

- ⏳ Extend `LLMProvider` with `generate_stream(prompt) -> Iterator[str]`; implement on `GeminiLLM` (keep non-streaming `generate()` for evals/tests)
- ⏳ `services/generation.py` — `generate_answer_stream(question, contexts)` yielding deltas
- ⏳ `routers/query.py` — add `POST /query/stream` (`text/event-stream` via `sse-starlette`): stream answer tokens, then a **final `citations` event**. Keep `POST /query` as the non-streaming path.
- ⏳ Frontend `src/shared/api/` — streaming helper (fetch + `ReadableStream`) + `useStreamingQuery` hook
- ⏳ Frontend `Chat.tsx` / `ChatArea` — append tokens to the assistant bubble live, attach citations on the final event

**End of day:** ask in the browser and watch the answer stream token-by-token, citations at the end.

---

## Day 5 — Quality pass, measure, buffer

- ⏳ Tune retrieval: `RETRIEVE_CANDIDATES`, `HYBRID_ALPHA`, `TOP_K`, chunk size — eyeball quality on 5–10 real questions across 2–3 reports
- ⏳ Capture an informal **before/after**: dense-only vs hybrid+rerank on the same questions (rigorous RAGAS numbers come in Week 3)
- ⏳ Update `README.md`: citations, rerank, hybrid, streaming + new env vars / `ENABLE_*` toggles
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
