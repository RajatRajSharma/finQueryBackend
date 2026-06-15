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
| `RETRIEVE_CANDIDATES` | 20 | 10–50 | over-fetch pool before rerank (only used if rerank/hybrid on) | **50%** | untested | tune with rerank on |
| `HYBRID_ALPHA` | 0.5 | 0.0–1.0 | dense↔sparse mix (1=dense only, 0=BM25 only) | **50%** | untested | sweep once hybrid is live |

## Feature flags (target state vs current)

| Var | Current | Target | Controls | Confidence current is best | Evidence | Next step |
|---|---|---|---|---|---|---|
| `ENABLE_RERANK` | false | **true** | Cohere rerank of candidates | **40%** (off = Week-1 quality) | untested | needs `COHERE_API_KEY` + `pip install cohere` |
| `ENABLE_HYBRID` | false | **true** | dense + BM25 fusion | **40%** (off = dense only) | untested | needs BM25 deps (Day 3) |

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
| `FRONTEND_ORIGIN` | http://localhost:5173 | n/a | CORS; changes per deploy |

---

## Overall setup validation

**~68%** — solid Week-1 baseline (dense retrieval eyeballed-good on real 10-Ks), but the two biggest quality levers (rerank, hybrid) are built-but-off and **unmeasured**. Expect this to jump once Week 3 RAGAS lets us replace `eyeballed`/`untested` with real numbers and actually sweep `CHUNK_SIZE` / `TOP_K` / `HYBRID_ALPHA`.

## Changelog

- **2026-06-16** — initial table. Week 2 Days 1–2 done (citations live; rerank code-complete, off). All retrieval values still pre-RAGAS (eyeballed/untested).
