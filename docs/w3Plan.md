# FinQuery — Week 3 Plan (Differentiators + deploy)

> **Goal of Week 3:** add the two features that make this "agentic RAG" instead of "a RAG tutorial" — an **agent router** and a **RAGAS evaluation dashboard** — then **deploy** both repos so it's a live, shareable URL. Keep a working slice at all times; both features are additive and gated behind config flags.
>
> Read [finQueryArchitecture.md](finQueryArchitecture.md) (§4.2 step 2 = agent) and [finQueryEvaluation.md](finQueryEvaluation.md) (the whole eval module) first. This implements **Phase 3** from [Idea1.md](Idea1.md).

---

## Where this sits in the 3-week project

| Week | Theme | Deliverable |
|---|---|---|
| Week 1 ✅ | Core RAG end-to-end | Upload a 10-K, ask, get a correct grounded answer |
| Week 2 | Make it impressive | Hybrid search + Cohere rerank + citations + SSE streaming + UI polish |
| **Week 3 (this file)** | Differentiators + deploy | Agentic routing + RAGAS dashboard, then **½ week deployment** |

**Time split:** ~Days 1–3 build the two differentiators, ~Days 4–5 (the "½ week") are deployment + final polish. Deployment is small because the backend is one FastAPI service (Dockerfile exists), the frontend is a static build, and Qdrant uses the **Qdrant Cloud free tier** in prod.

---

## Pre-flight (Day 0 — ~1 hr)

- ✅ Installed the **Week 3 deps**: `ragas==0.2.9`, `datasets==3.2.0`, plus a **pinned langchain 0.3.x stack** + `langchain-google-genai` (RAGAS 0.2.9 breaks on langchain 1.x — see the requirements note). App still imports; pytest green.
- ✅ Chose the **web-search tool**: keyless **DuckDuckGo** (`ddgs`) — no key needed (Day 2)
- ✅ Added Week 3 knobs to `config.py` + `.env.example`: `ENABLE_AGENT`, `ENABLE_WEB_SEARCH`, `EVAL_PROVIDER`, `EVAL_QUESTIONS_PATH`, `EVAL_RESULTS_PATH`, `EVAL_SAMPLE_SIZE` (all default to off / safe)
- ✅ Weeks 1–2 still green (pytest 15/15)
- ✅ **RAGAS de-risk spike**: a 1-record RAGAS-on-Gemini run **works** (answer_relevancy 0.82, context_precision 1.0; faithfulness needs attention — see Day 3). Surfaced the langchain-version trap early, as intended.

> **Free-tier quota reminder:** RAGAS grades with an **LLM judge**, so a 20-question eval = dozens of Gemini calls. Embeds are capped ~100/min — run evals once, not in a loop, and expect to pace runs. (See the project memory on the Gemini free-tier quota.)

---

## Day 1 — Agent router (the "agentic" part)  ✅

Implements [§4.2 step 2](finQueryArchitecture.md). Before retrieving, the agent classifies the question and picks a route — this is what lets the project honestly be called *agentic* RAG.

- ✅ New interface `QueryRouter` in `core/interfaces.py` — `route(question) -> RouteDecision` (`answer_from_docs | clarify | web_search`); `RouteDecision` added to `core/domain.py`
- ✅ Filled the `services/agent.py` **stub** → `LLMQueryRouter`: a JSON-classification prompt over `LLMProvider` (reuses Gemini — no new vendor), robust parse, **safe fallback to `answer_from_docs`** on any error
- ✅ `routers/query.py` — runs the router first on both `/query` and `/query/stream`:
  - `answer_from_docs` → the Week 2 hybrid→rerank→generate path
  - `clarify` → returns a one-line follow-up question (no retrieval)
  - `web_search` → hands off to the Day 2 tool (falls back to docs if web is off)
- ✅ `factory.py` — `get_query_router()` gated by `ENABLE_AGENT` (off → `None` → exactly Week 2); `schemas.QueryResponse` gained an additive `route` field
- ✅ Tests: `FakeQueryRouter` + endpoint tests force each branch (pytest 14/14); router parse + fallback unit-tested
- ✅ **Live-verified**: docs question → `answer_from_docs` (cited answer); "how did they do?" → `clarify` (asks which company/metric)

**End of day:** ✅ the backend decides *how* to answer before answering; `ENABLE_AGENT=false` is the plain Week 2 pipeline.

---

## Day 2 — Web-search fallback tool  ✅ (live tool; end-to-end answer quota-blocked)

Completes the agent: when a question isn't covered by the uploaded reports, fall back to web search instead of forcing a weak doc-grounded answer ([§3 external services / §4.2](finQueryArchitecture.md)).

- ✅ New interface `WebSearchTool` — `search(query) -> list[WebResult]`; `WebResult` in `core/domain.py`
- ✅ `clients/websearch_client.py` — `DuckDuckGoSearch` via the **keyless `ddgs`** package (no API key needed), errors → `UpstreamServiceError` (mirrors the Gemini/Cohere pattern)
- ✅ Wired the `web_search` branch: `generation.generate_web_answer()` builds a web-grounded prompt prefixed **"From the web:"** (clearly not from the user's reports); `QueryResponse.web_sources` returns the URLs
- ✅ Kept **opt-in** (`ENABLE_WEB_SEARCH=false` default) so the core demo never depends on it; provider lazy-imported only when enabled
- ✅ Tests: `FakeWebSearchTool` + endpoint test assert the web branch returns `web_sources` and calls the tool (pytest 14/14)
- ✅ **Live-verified**: `DuckDuckGoSearch.search()` returns real results (no key)
- ⏸ **End-to-end web *answer* live**: blocked by the Gemini free-tier generation cap (20/min) — the agent adds a classify call per query, so the budget runs out. Surfaces cleanly as a 503. Components all verified individually.

**End of day:** out-of-corpus questions get an honest web-sourced answer (when enabled) rather than a hallucinated one.

---

## Day 3 — RAGAS evaluation  ✅ (built + wired; full-run scores quota-limited)

Implements the whole of [finQueryEvaluation.md](finQueryEvaluation.md) — the standout "I measured my RAG" feature. Built the project's way: an `Evaluator` port + `RagasEvaluator` adapter (lazy-imported) + `FakeEvaluator` for tests.

- ✅ Authored `data/eval/questions.json` — 12 `{question, ground_truth}` pairs (Apple 10-K; the committed test fixture — only cached `results.json` is gitignored)
- ✅ New `Evaluator` interface + `EvalRecord`/`EvalReport` domain; filled `clients/ragas_evaluator.py` → `RagasEvaluator` using `ragas.evaluate` with `faithfulness, answer_relevancy, context_precision`, judge + embeddings pointed at **Gemini** (errors → `UpstreamServiceError`)
- ✅ Filled `services/evaluation.py` → `EvaluationService`: for each question runs the **live pipeline** (retrieve → generate), captures `question/answer/contexts/ground_truth`, scores via the evaluator, **caches** to `EVAL_RESULTS_PATH`
- ✅ Filled `routers/evals.py` → `GET /evals` (cached) / `GET /evals?run=true` (fresh); **mounted in `main.py`**; `EvalResponse` schema added
- ✅ `factory.get_evaluator()` / `get_evaluation_service()`; `FakeEvaluator` + endpoint/service tests (pytest 15/15)
- ✅ **Live-verified the flow end-to-end** (endpoint→service→pipeline→RAGAS→cache runs)
- ⏸ **Meaningful full-run scores**: blocked by the Gemini free-tier **20 generates/min** — RAGAS fires ~3 judge jobs/question, so a multi-question run times out mid-eval and returns `NaN`s. Single-record scoring works (spike). Real numbers need a tiny `EVAL_SAMPLE_SIZE` + spaced retries, or paid quota.
- ⚠️ **Faithfulness metric with Gemini** returned 0.0/NaN in places — a known RAGAS quirk where its statement-extraction prompt doesn't parse cleanly on non-OpenAI judges. Flag for tuning (custom prompt or a different metric impl).

**End of day:** `GET /evals` is wired and runs; trustworthy faithfulness/relevancy/precision numbers await more quota (and a faithfulness-prompt fix for Gemini).

---

## Day 4 — Eval dashboard + deploy prep (start of the ½ week)

The frontend already has the eval UI shells — `features/evaluation` (`MetricCards`, `MetricBarChart`, `QuestionsTable`) and the `pages/Evaluation` route are built with mock data. Wire them to the live endpoint, then prep both repos for deploy.

- ⏳ Frontend `src/shared/api/` — add `getEvals()`; replace the Evaluation page's mock data with the real `GET /evals` response
- ⏳ Show the headline number (faithfulness) prominently; bar chart for the three metrics; table of per-question scores
- ⏳ **Screenshot the dashboard** for the README (aim for 0.9+ faithfulness — the resume artifact)
- ⏳ Deploy prep — backend: confirm the [Dockerfile](../Dockerfile) builds standalone; add prod env (`FRONTEND_ORIGIN`=prod URL, `QDRANT_URL`=Qdrant Cloud); document required keys
- ⏳ Deploy prep — frontend: `vite build` → `dist/`; set prod `VITE_API_BASE_URL`

**End of day:** the eval dashboard shows live RAGAS scores; both repos are build-clean and configured for prod.

---

## Day 5 — Deploy + final polish (rest of the ½ week)

- ⏳ **Qdrant Cloud** (free tier) — create a cluster, set `QDRANT_URL`/api key as backend env, batch-ingest the corpus once (pace it for the embed quota)
- ⏳ **Backend** → Railway or Render as a web service (container or buildpack); set all env vars; verify `/health/ready` is green against Qdrant Cloud
- ⏳ **Frontend** → Vercel / Netlify (static `dist/`); set `VITE_API_BASE_URL` to the deployed backend
- ⏳ **CORS** — set the backend `FRONTEND_ORIGIN` to the deployed frontend URL; verify a cross-origin query from the live site
- ⏳ Final READMEs (both repos): live URLs, architecture recap, the RAGAS screenshot, "run locally" + "deployed" sections
- ⏳ Tag/commit a clean **v1.0** in both repos
- ⏳ **Buffer** — first-time cloud deploys (CORS, env, cold starts, Qdrant Cloud auth) always surprise; this absorbs it

**End of Week 3 demo:** a public URL where anyone can upload a 10-K, watch a reranked answer stream in with citations, and open a dashboard showing measured RAGAS quality.

---

## Explicitly OUT of scope (stretch / post-v1)

- ❌ OpenAI provider swap — the interfaces + factory make it a small change, but it's not needed for v1
- ❌ Auth / accounts / multi-tenant — single shared demo instance is fine
- ❌ Persisting chat history / per-user document stores
- ❌ CI/CD pipelines, observability stacks — manual deploy is acceptable for a portfolio v1

> Rule for the week: ship the two differentiators, then get it **live**. A deployed URL with a RAGAS screenshot beats one more local feature.
