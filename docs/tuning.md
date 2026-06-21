# FinQuery — Env & Tuning Log

> **What this is:** a living table of every configurable env var, its current value, and how confident we are it's near-optimal **for this corpus (dense financial 10-Ks)**. Glance here before tuning; update it whenever a value changes.

## How to read the "Confidence" column

It is an **honest judgment of how close the value is to best**, grounded in an evidence level — **not** a measured score (yet):

| Evidence | Meaning | Confidence ceiling |
|---|---|---|
| `untested` | set to a default/guess, never exercised | ≤ 55% |
| `eyeballed` | looks right on a few real questions | ≤ 80% |
| `RAGAS` | backed by Week 3 RAGAS numbers | up to 100% |

So a low % means "we haven't proven it," not "it's wrong." These numbers get **real in Week 3** when RAGAS gives measured faithfulness / relevancy / context-precision per config. Until then, treat the table as a tuning to-do list ranked by uncertainty.

---

## Retrieval & chunking knobs (the real tuning levers)

| Var | Current | Sane range | Controls | Confidence | Evidence | Next step |
|---|---|---|---|---|---|---|
| `CHUNK_SIZE` | 512 | 256–1024 | tokens per chunk; bigger = more context, less precise | **70%** | eyeballed | sweep 256/512/768 under RAGAS |
| `CHUNK_OVERLAP` | 50 | 0–128 | tokens shared across chunk boundaries (~10%) | **70%** | eyeballed | fine once size is fixed |
| `TOP_K` | 5 | 3–8 | chunks fed to the LLM (final) | **70%** | eyeballed | 3 vs 5 vs 8 under RAGAS |
| `RETRIEVE_CANDIDATES` | 20 | 10–50 | over-fetch pool before fuse/rerank (used when hybrid/rerank on) | **55%** | eyeballed | now exercised by hybrid; sweep under RAGAS |
| `HYBRID_ALPHA` | 0.5 | 0.5–0.7 | dense↔sparse mix (1=dense only, 0=BM25 only) | **65%** | eyeballed | swept 0.3/0.5/0.7: <0.5 demotes best semantic page; keep 0.5. RAGAS sweep next |

## Feature flags (target state vs current)

| Var | Current | Target | Controls | Confidence current is best | Evidence | Next step |
|---|---|---|---|---|---|---|
| `ENABLE_RERANK` | false | **true** | Cohere rerank of candidates | **40%** (off = Week-1 quality) | untested | needs `COHERE_API_KEY` + `pip install cohere` |
| `ENABLE_HYBRID` | false | **true** | dense + BM25 fusion | **45%** (off = dense only) | eyeballed | built + verified live (rank-bm25); flip on for demo, measure under RAGAS |
| `ENABLE_AGENT` | false | demo: **true** | route docs/clarify/web before retrieving | **50%** (off = Week 2 pipeline) | eyeballed | live-verified docs+clarify; adds 1 Gemini generate/query (quota cost) |
| `ENABLE_WEB_SEARCH` | false | opt-in | web fallback when not in docs | **60%** (off = no external dep) | eyeballed | DuckDuckGo tool live; keep off unless needed (free-tier gen quota) |
| `EVAL_SAMPLE_SIZE` | 2 | small | how many questions /evals scores | **70%** | eyeballed | RAGAS ~3 judge calls/Q; >a few hits the 20/min cap → NaN scores |

## Models & dimensions

| Var | Current | Controls | Confidence | Evidence | Note |
|---|---|---|---|---|---|
| `EMBED_MODEL` | gemini-embedding-001 | embedding model | **85%** | eyeballed | works live, 768-dim |
| `EMBED_DIM` | 768 | vector size (must match Qdrant collection) | **85%** | eyeballed | changing it = re-create collection + re-ingest |
| `LLM_MODEL` | gemini-2.5-flash | answer generation | **75%** | eyeballed | free tier 503s under load; fine for demo |
| `RERANK_MODEL` | rerank-english-v3.0 | Cohere rerank model | **55%** | untested | English is right for 10-Ks; v3.5 is multilingual |

## Provider / infra (locked choices, not tuning knobs)

| Var | Current | Confidence it's the right choice | Note |
|---|---|---|---|
| `EMBED_PROVIDER` / `LLM_PROVIDER` | gemini | **95%** | free-tier, project-mandated; swappable via factory |
| `VECTOR_STORE` | qdrant | **95%** | Dockerized local / Qdrant Cloud in prod |
| `RERANK_PROVIDER` | cohere | **80%** | per architecture doc |
| `QDRANT_URL` / `QDRANT_COLLECTION` | localhost:6333 / finquery_chunks | n/a | env/infra, not tuned |
| `QDRANT_API_KEY` | (blank) | n/a | blank = local open Docker; set to a Qdrant Cloud key for prod (authed HTTPS) |
| `FRONTEND_ORIGIN` | http://localhost:5173 | n/a | CORS; changes per deploy |
| `ADMIN_API_KEY` | (blank) | n/a | blank = admin endpoints (POST /admin/prune) disabled; set a secret to enable, sent as `X-Admin-Token` |

---

## Overall setup validation

**~72%** — solid Week-1 baseline, and now a **first real RAGAS data point** (dense, 1 question: faithfulness 1.0, answerRelevancy 0.89, contextPrecision 0.89, contextRecall 1.0 — see [tuning-runs.md](tuning-runs.md)). Still partial: scored only 1–2 questions (free-tier per-minute cap), rerank unmeasured (no Cohere key), and no full per-config RAGAS sweep yet. Multi-key rotation removed the *daily* wall; a paid key would remove the per-minute one and let us score the full 12-question set + sweep `CHUNK_SIZE`/`TOP_K`/`HYBRID_ALPHA`.

## Changelog

- **2026-06-16** — initial table. Week 2 Days 1–2 done (citations live; rerank code-complete, off). All retrieval values still pre-RAGAS (eyeballed/untested).
- **2026-06-16** — Week 2 Days 3–4 done. Hybrid (dense+BM25) built + verified live; `HYBRID_ALPHA`/`RETRIEVE_CANDIDATES` now `eyeballed`. SSE streaming added (no new env knobs). Defaults still ship hybrid/rerank **off** until measured.
- **2026-06-16** — Week 2 Day 5 done. Logged a dense-vs-hybrid retrieval comparison in [tuning-runs.md](tuning-runs.md) (hybrid sharpens top-hit toward keyword pages, no regression). Rigorous `CHUNK_SIZE`/`TOP_K`/`HYBRID_ALPHA` sweep deferred to Week 3 RAGAS.
- **2026-06-16** — Week 3 Days 1–2 done. Added `ENABLE_AGENT` (router: docs/clarify/web) and `ENABLE_WEB_SEARCH` (DuckDuckGo). Both off by default. Heads-up: with the agent on, each query costs an extra Gemini *generate* call — easy to hit the free-tier 20/min generation cap.
- **2026-06-16** — Week 3 Day 3 (RAGAS) built + wired (`GET /evals`, judge on Gemini). Single-record scoring verified live; multi-question full runs hit the 20/min cap and return NaNs (`EVAL_SAMPLE_SIZE` added, default 2). NOTE: ragas 0.2.9 forced a pinned **langchain 0.3.x** stack — don't bump langchain to 1.x. Faithfulness metric on Gemini needs a prompt fix (returns 0/NaN).
- **2026-06-21** — Added corpus-prune maintenance (CLI `scripts/prune_corpus.py` + `POST /admin/prune`, shared `CorpusPruner` service). New `ADMIN_API_KEY` gates the admin API (disabled when blank; sent as `X-Admin-Token`). Prune keeps the `data/raw` corpus and deletes all other chunks; dry-run by default.
- **2026-06-20** — Added `QDRANT_API_KEY` (optional) to support an authenticated production Qdrant (Qdrant Cloud). Empty key = unchanged local open-Docker path; a set key is passed through to the client over HTTPS. Wired in `config.py`/`factory.py`/`qdrant_client.py` and both env files.
- **2026-06-16** — Added multi-key rotation (`GEMINI_API_KEY_2/_3` + `GeminiKeyPool`, 1→2→3 on 429). Unblocked the daily cap → **first real RAGAS scores landed** (sample=1). Also swept `HYBRID_ALPHA` (keep 0.5). Day-4 eval dashboard wired to live `GET /evals`.
