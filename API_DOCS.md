# FinQuery API — Reference

Base URL (production): `https://finquerybackend.onrender.com` · Interactive docs: `/docs`
Base URL (local): `http://localhost:8000`

All bodies are JSON unless noted. Examples are illustrative.

---

## GET `/health`
Liveness — is the process up? Touches no dependencies.

**Input:** none

**Output:**
```json
{ "status": "ok", "service": "finquery-backend", "version": "0.1.0" }
```

---

## GET `/health/ready`
Readiness — are downstream deps (Qdrant) reachable? Used by load balancers.

**Input:** none

**Output:**
```json
{ "status": "ready", "dependencies": { "qdrant": true } }
```
`status` is `"degraded"` if any dependency is down.

---

## POST `/upload`
Ingest a PDF 10-K into the vector store (parse → chunk → embed → upsert).

**Input:** `multipart/form-data` with a `file` field (`.pdf` only).
```bash
curl -F "file=@AppleInc.pdf" http://localhost:8000/upload
```

**Output:**
```json
{
  "source_file": "AppleInc.pdf",
  "company": "AppleInc",
  "pages_parsed": 32,
  "chunks_created": 64,
  "chunks_stored": 64
}
```

---

## POST `/query`
Ask a question; returns a grounded answer with citations. (With the agent on, may instead clarify or use web search.)

**Input:**
```json
{ "question": "What were Apple's total net sales?", "top_k": 5 }
```
`top_k` is optional (defaults to the configured value).

**Output:**
```json
{
  "answer": "Apple's total net sales were $111,184 million...",
  "citations": [
    {
      "source_file": "AppleInc.pdf",
      "company": "AppleInc",
      "page_number": 9,
      "snippet": "Total net sales ...",
      "score": 0.74
    }
  ],
  "route": null,
  "web_sources": null
}
```
`route` is `"answer_from_docs" | "clarify" | "web_search"` when the agent is enabled (else `null`). `web_sources` is populated only on the `web_search` route.

---

## POST `/query/stream`
Same as `/query`, but streams the answer over SSE (Server-Sent Events).

**Input:** same body as `/query`.

**Output:** an SSE event stream:
```
event: token       data: "Apple's"
event: token       data: " total net sales"
event: citations   data: [{"source_file":"AppleInc.pdf","page_number":9, ...}]
event: done        data: ""
```
On mid-stream failure: `event: error  data: "<message>"`.

---

## GET `/evals`
Return the last cached RAGAS evaluation run (instant). 404 if none yet.

**Input:** none

**Output:**
```json
{
  "runId": "run_20260620_1",
  "createdAt": "2026-06-20T18:00:00Z",
  "questionCount": 1,
  "metrics": { "faithfulness": 1.0, "answerRelevancy": 0.89, "contextPrecision": 0.89, "contextRecall": 1.0 },
  "config": { "model": "gemini-2.5-flash", "topK": 5, "hybrid": false },
  "questions": [ { "question": "...", "answer": "...", "groundTruth": "..." } ],
  "baseline": null,
  "stale": false,
  "running": false
}
```
`stale=true` means the cache is older than the TTL; `running=true` means a fresh run is in progress.

---

## POST `/evals/run`
Kick off a fresh evaluation in the background (slow + quota-heavy). 409 if one is already running.

**Input:** optional query param `as_baseline=true` to save the run as the before/after reference.
```bash
curl -X POST "http://localhost:8000/evals/run?as_baseline=false"
```

**Output:** (HTTP 202)
```json
{ "status": "started", "asBaseline": false }
```
Poll `GET /evals` until `running` clears.

---

## POST `/admin/prune`
Admin-only. Delete every stored chunk whose document isn't in the canonical `data/raw` keep-list. Dry-run by default.

**Input:**
- Header `X-Admin-Token: <ADMIN_API_KEY>` (required; 503 if the key is unset, 401 if it mismatches).
- Optional query param `apply=true` to actually delete (omitted = dry run).
```bash
curl -X POST "http://localhost:8000/admin/prune?apply=true" -H "X-Admin-Token: <key>"
```

**Output:**
```json
{
  "applied": true,
  "keep": ["AppleInc.pdf", "Amazon.pdf", "..."],
  "kept_counts": { "AppleInc.pdf": 64 },
  "deleted_counts": { "Junk.pdf": 12 },
  "deleted_total": 12
}
```
On a dry run, `applied` is `false` and `deleted_*` show what *would* be removed.
