# FinQuery — Tuning Runs (call → config → result log)

> **What this is:** a log of actual retrieval/answer runs and what config produced them — the "calls and responses" companion to [tuning.md](tuning.md) (which holds the *current* values). Append a block whenever you test a config change so comparisons are recorded, not lost in a terminal. Becomes rigorous in Week 3 when RAGAS attaches measured scores.
>
> **How to regenerate the retrieval comparison:** `ENABLE_HYBRID=true python -m scripts.compare_retrieval` (embeds each question once, runs dense + hybrid over the same vector — no generation quota spent). Format below is `pageN:score`.

---

## Run 2026-06-16 — dense vs hybrid (Apple 10-K, 64 chunks)

**Config:** `EMBED_MODEL=gemini-embedding-001` · `TOP_K=5` · `RETRIEVE_CANDIDATES=20` · `HYBRID_ALPHA=0.5` · rerank off · corpus = `AppleInc.pdf` only.
(Scores differ by mode: dense = raw cosine; hybrid = min-max-normalised weighted fusion, so they aren't directly comparable in magnitude — look at *which pages* and *their order*.)

| Question | dense (page:score) | hybrid (page:score) |
|---|---|---|
| Total net sales? | p9:.745, p4:.728, p18:.725, p6:.705, p18:.702 | p9:.766, p17:.704, p18:.575, p4:.517, p18:.514 |
| Risk factors: tariffs/trade? | p17:.724, p27:.653, p27:.637, p26:.633, p17:.631 | **p17:1.00**, p27:.553, p17:.508, p24:.410, p27:.357 |
| Services net sales? | p18:.717, p18:.711, p19:.692, p9:.691, p4:.677 | p18:.973, p18:.937, p17:.694, p4:.637, p9:.618 |
| Share repurchase program? | p13:.681, p13:.678, p21:.663, p27:.663, p21:.656 | **p13:.985**, p27:.915, p21:.860, p13:.707, p21:.401 |
| iPhone net sales YoY? | p18:.746, p9:.731, p17:.723, p17:.714, p18:.701 | **p18:1.00**, p17:.836, p17:.728, p9:.652, p18:.602 |

**Observations (eyeballed, not RAGAS):**
- Hybrid sharpens the top hit — the page that's strong in *both* dense and keyword (e.g. tariffs→p17, repurchase→p13, iPhone→p18) is promoted decisively to rank 1.
- It also pulls in keyword-matching pages dense ranked lower (tariffs surfaces p24; net-sales surfaces p17).
- Top pages overlap a lot with dense, so for this corpus hybrid is a **reordering/precision tweak**, not a different result set — expected, since the answers were already correct under dense.

**Verdict:** hybrid behaves correctly and favours exact-term pages, as intended. Whether it raises answer quality is **not yet proven** — needs RAGAS context-precision (Week 3) on a multi-doc corpus where keyword disambiguation matters more (e.g. comparing companies). No regression observed.

**Next runs to log:** rerank on (needs Cohere key); `HYBRID_ALPHA` sweep 0.3/0.5/0.7; same questions across 2–3 companies; then the same set under RAGAS.

---

## Run 2026-06-16 — RAGAS evaluation trials (Apple corpus)

Goal: get a clean RAGAS score under the Gemini free tier. Each trial = config set → what came back.

| # | Config | Result | Read |
|---|---|---|---|
| T1 | 1 record, default concurrency (judge only, budget available) | faithfulness **0.0**, answer_relevancy **0.82**, context_precision **1.0** | Wiring works — RAGAS+Gemini scores live. Faithfulness 0.0 is a metric quirk (below). |
| T2 | full pipeline, `sample=2`, default concurrency | ran end-to-end but mostly **NaN** | RAGAS fired its ~3 jobs/Q concurrently (16 workers) → burst past 20/min → timeouts. |
| T3 | `sample=1`, default concurrency | timed out at 2/3 jobs | Same burst problem even for 1 question. |
| T4 | `sample=1`, **throttle on** (`EVAL_LLM_RPM=10`, `EVAL_MAX_WORKERS=1`) | **429 on the pipeline's answer-gen** | Throttle is correct, but the day's quota was already spent. |
| T5 | idle 60s, then **one** generate call | **429, "retry in 53s"** | A fresh minute + 1 call should pass → confirms the **daily** cap (RPD) is exhausted, not per-minute. |

**Blocker (precise):** the free-tier **daily** generate quota for `gemini-2.5-flash` is exhausted from a full day of testing. A daily cap resets ~midnight Pacific; no waiting/throttling helps today. Embeddings (separate, higher quota) still work.

**Improvement made (so it works when quota has headroom):** added env-controlled throttling to `RagasEvaluator` — `EVAL_LLM_RPM` (token-bucket rate limiter on the judge) + `EVAL_MAX_WORKERS=1` (serialize jobs so RAGAS doesn't burst the cap) + a per-job timeout. T1 proves the scoring path works; with the throttle, a small `EVAL_SAMPLE_SIZE` should complete once the daily budget refreshes.

**Faithfulness quirk:** RAGAS faithfulness returned 0.0/NaN on Gemini even for a directly-supported answer — its statement-extraction prompt parses poorly on non-OpenAI judges. Fix later via a custom prompt or alternate metric; relevancy + precision look sane.

**To get a real run tomorrow:** `EVAL_SAMPLE_SIZE=2 EVAL_LLM_RPM=10 EVAL_MAX_WORKERS=1` → `GET /evals?run=true`. Bump sample only if it stays green.
