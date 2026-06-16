# FinQuery — Execution Plan (3 weeks, combined)

Agentic RAG over company 10-Ks: upload → ask → grounded, cited answer; hybrid retrieval + rerank + streaming; agent routing + RAGAS evaluation; deploy.

**Status:** ✅ done · ⏸ built but not fully verified (key/quota) · ⏳ to do

> Tuning values + logged runs live in [tuning.md](tuning.md) and [tuning-runs.md](tuning-runs.md).

---

## Week 1 — Core RAG (end-to-end)
- ✅ FastAPI app + split `/health` & `/health/ready`; config via `.env`
- ✅ Qdrant running via Docker / docker-compose
- ✅ Ingestion: parse (pypdf) → chunk (LlamaIndex) → embed (Gemini) → store (Qdrant)
- ✅ Query: embed → vector search → generate (Gemini) → citations
- ✅ Real 10-K corpus ingested; live grounded, cited answers
- ✅ Frontend wired: upload PDF + ask question (loading/error states)
- ✅ Fake-backed tests; vendor errors → clean HTTP 503

## Week 2 — Make it impressive
- ✅ Rich citations in UI (snippet + relevance score, expandable)
- ✅ Hybrid retrieval: dense + BM25, weighted fusion (`ENABLE_HYBRID`, keep `HYBRID_ALPHA=0.5`)
- ⏸ Cohere reranking — built + gated (`ENABLE_RERANK`); live-verify needs a Cohere key
- ✅ SSE token streaming (`POST /query/stream`) wired to the chat
- ✅ Informal `HYBRID_ALPHA` sweep logged; README/env updated

## Week 3 — Differentiators + deploy
- ✅ Agent router: answer-from-docs / clarify / web-search (`ENABLE_AGENT`)
- ✅ Web-search fallback (keyless DuckDuckGo, opt-in `ENABLE_WEB_SEARCH`)
- ✅ Multi-key rotation (`GEMINI_API_KEY_2/_3`, pool rotates 1→2→3 on quota)
- ✅ RAGAS evaluation built + wired (`GET /evals`, `POST /evals/run`, TTL cache, judge on Gemini)
- ✅ First real RAGAS scores landed (faithfulness 1.0, relevancy 0.89, precision 0.89, recall 1.0)
- ⏸ Full 12-question RAGAS run — free-tier 20/min cap; score 1–2 at a time or use a paid key
- ✅ Eval dashboard wired to live `/evals` (cards + bar chart + per-question table, baseline + config)
- ⏳ Deployment: Qdrant Cloud + backend (Railway/Render) + frontend (Vercel/Netlify) + CORS + READMEs

---

## Known follow-ups
- ⏳ Deploy (Week 3 Day 5) — the main remaining piece
- ⏸ Full RAGAS run + dashboard screenshot (quota-gated)
- ⏸ Cohere rerank live-verify (needs key)
- ⏳ Browser click-through of streaming + eval dashboard (code/API verified, not eyeballed)
- ⏳ Faithfulness-prompt tuning for the Gemini judge (RAGAS quirk on non-OpenAI judges)
