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
- ✅ Installed the deps actually used — `rank-bm25` (BM25 direct, skipping the churny `llama-index-retrievers-bm25`) and `sse-starlette==2.1.3` (pinned to keep `starlette <0.42` for fastapi). `cohere` still optional, installed only when rerank is switched on.
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

## Day 3 — Hybrid retrieval (dense + BM25 keyword)  ✅

Adds the sparse half of [§4.2 step 3](finQueryArchitecture.md). Vector search nails *meaning*; BM25 nails *exact terms* ("Q4 2024", ticker symbols, line-item names). Fusing both catches what either misses. (Used `rank-bm25` directly to avoid the LlamaIndex BM25 package's version churn.)

- ✅ New interface `SparseRetriever` in `core/interfaces.py` — `index(chunks)` + `search(question, k)`; plus `VectorStore.all_chunks()` so BM25 reuses the corpus already in Qdrant
- ✅ `clients/bm25_index.py` — `Bm25Retriever` over `rank-bm25`, in-memory, with a documented freshness trade-off (rebuild on restart; dense stays fresh for new uploads)
- ✅ `services/retrieval.py` — `fuse()` does **min-max-normalised weighted fusion** by `HYBRID_ALPHA` (dense+sparse), → `RETRIEVE_CANDIDATES`, then the Day-2 reranker
- ✅ `factory.py` — `get_sparse_retriever()` (built from `store.all_chunks()`, gated by `ENABLE_HYBRID`); assembled into `get_retrieval_service()`
- ✅ Tests: `FakeSparseRetriever`; `fuse()` proves a chunk strong in *both* lists outranks one strong in dense only (pytest 9/9)
- ✅ **Live-verified**: `ENABLE_HYBRID=true` on the real Apple corpus → correct cited answer with fused scores

**End of day:** ✅ `/query` fuses dense + keyword candidates; `ENABLE_HYBRID=false` falls back byte-for-byte to dense-only.

---

## Day 4 — SSE token streaming  ✅

Implements [§4.2 step 7](finQueryArchitecture.md). The answer "types out" live — the biggest *perceived* win, and the fiddliest item.

- ✅ Extended `LLMProvider` with `generate_stream(prompt) -> Iterator[str]`; implemented on `GeminiLLM` (via `generate_content_stream`, same error translation) and `FakeLLM`; kept non-streaming `generate()` for evals/tests
- ✅ `services/generation.py` — `generate_answer_stream(question, contexts)` yields deltas
- ✅ `routers/query.py` — `POST /query/stream` via `sse-starlette`: `token` events, then a `citations` event, then `done`; mid-stream failures emit an `error` event. `POST /query` stays the one-shot path.
- ✅ Frontend `src/shared/api/client.ts` — `askQuestionStream()` parses the SSE frames from a `fetch` `ReadableStream` (EventSource is GET-only); handles multi-line `data:` + keep-alive comments
- ✅ Frontend `Chat.tsx` — appends tokens to the assistant bubble live (first token clears the "Searching…" placeholder), attaches citation chips on the `citations` event
- ✅ **Live-verified** via curl: 5 `token` events → `citations` → `done`; frontend `build` + `lint` green

**End of day:** ✅ answer streams token-by-token; citations appear at the end. (Browser click-through not yet eyeballed — backend SSE + client parser proven, UI wired + type-checks.)

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
