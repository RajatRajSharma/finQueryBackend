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

- ⏳ Uncomment the **Week 3 deps** in [requirements.txt](../requirements.txt) and install: `ragas`, `datasets`
- ⏳ Decide the **web-search tool** for the agent fallback (e.g. Tavily / SerpAPI free tier, or DuckDuckGo) → add its key to `.env` + `.env.example`
- ⏳ Add Week 3 knobs to `config.py`: `ENABLE_AGENT=true`, `ENABLE_WEB_SEARCH=false` (default off — opt-in), `EVAL_QUESTIONS_PATH=data/eval/questions.json`
- ⏳ Confirm Weeks 1–2 still green (`pytest -q`, a live streamed + reranked query)

> **Free-tier quota reminder:** RAGAS grades with an **LLM judge**, so a 20-question eval = dozens of Gemini calls. Embeds are capped ~100/min — run evals once, not in a loop, and expect to pace runs. (See the project memory on the Gemini free-tier quota.)

---

## Day 1 — Agent router (the "agentic" part)

Implements [§4.2 step 2](finQueryArchitecture.md). Before retrieving, the agent classifies the question and picks a route — this is what lets the project honestly be called *agentic* RAG.

- ⏳ New interface (e.g. `QueryRouter`) in `core/interfaces.py` — `route(question) -> RouteDecision` where the decision is one of `answer_from_docs | clarify | web_search`
- ⏳ Fill the `services/agent.py` **stub** → an LLM-backed router: a small classification prompt over `LLMProvider` returning a structured decision (reuse the existing Gemini client; no new vendor)
- ⏳ `routers/query.py` — run the router first:
  - `answer_from_docs` → the normal Week 2 hybrid→rerank→generate path
  - `clarify` → return a short clarifying question instead of an answer (new response shape / event)
  - `web_search` → hand off to the Day 2 fallback tool
- ⏳ `factory.py` — `get_query_router()`, gated by `ENABLE_AGENT` (off → behaves exactly like Week 2)
- ⏳ Tests: fake router forcing each branch; assert the pipeline takes the right path (no infra)

**End of day:** the backend decides *how* to answer before answering; with `ENABLE_AGENT=false` it's the plain Week 2 pipeline.

---

## Day 2 — Web-search fallback tool

Completes the agent: when a question isn't covered by the uploaded reports, fall back to web search instead of forcing a weak doc-grounded answer ([§3 external services / §4.2](finQueryArchitecture.md)).

- ⏳ New interface `WebSearchTool` — `search(query) -> list[{title, url, snippet}]`
- ⏳ `clients/websearch_client.py` — wrap the chosen provider; `ConfigurationError` on missing key, errors → `UpstreamServiceError` (mirror the Gemini/Cohere pattern)
- ⏳ Wire the `web_search` branch: generate an answer from web snippets, clearly **labelled as web-sourced (not from the user's reports)** and cited with URLs
- ⏳ Keep it **opt-in** (`ENABLE_WEB_SEARCH=false` by default) so the core demo never depends on an external search key
- ⏳ Tests: fake web tool; assert web answers are labelled distinctly from doc answers

**End of day:** out-of-corpus questions get an honest web-sourced answer (when enabled) rather than a hallucinated one.

---

## Day 3 — RAGAS evaluation

Implements the whole of [finQueryEvaluation.md](finQueryEvaluation.md) — the standout "I measured my RAG" feature.

- ⏳ Author `data/eval/questions.json` — ~20 `{question, ground_truth}` pairs across the corpus (Apple net sales, Tesla risks, etc.). `contexts` + `answer` are filled by running the pipeline.
- ⏳ Fill the `services/evaluation.py` **stub** → `run_evaluation(records)` using `ragas.evaluate` with `faithfulness, answer_relevancy, context_precision` (point RAGAS's judge + embeddings at Gemini)
- ⏳ Add a runner: for each test question, run the live query pipeline, capture `question / answer / contexts / ground_truth`, then score
- ⏳ Fill the `routers/evals.py` **stub** → `GET /evals` returning averaged metrics (+ per-question rows); **mount it in `main.py`** (the Week 1 TODO comment marks the spot)
- ⏳ Cache the last run's results (results file under `data/eval/`, gitignored) so `GET /evals` is fast and doesn't re-burn API calls on every request

**End of day:** `GET /evals` returns real faithfulness / relevancy / precision scores for the current pipeline.

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
