# FinQuery — Architecture (HLD + LLD)

> **What this doc is:** the architecture reference for FinQuery, an agentic RAG application that lets users chat with real company annual reports (10-Ks) and get source-cited answers. Read this to understand how the system is structured and how data flows through it. New developers (and AI assistants) should read this first.

---

## 1. What the system does (one paragraph)

A user uploads annual report PDFs. The system parses, chunks, embeds, and stores them in a vector database. When the user asks a question, an agent decides how to handle it, the system retrieves the most relevant chunks (using both vector and keyword search), reranks them, and an LLM generates an answer grounded in those chunks — streamed back token-by-token with source citations. A separate evaluation module measures answer quality with RAGAS metrics.

**Project type:** RAG-first, with an agentic routing layer (so it can honestly be called "agentic RAG").

---

## 2. Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS, SSE streaming |
| Backend | Python + FastAPI (async), Pydantic v2 |
| RAG orchestration | LlamaIndex |
| Embeddings + generation | Google Gemini API (free tier) |
| Vector DB | Qdrant (Dockerized) |
| Retrieval | Hybrid: dense vectors + BM25 keyword, fused |
| Reranking | Cohere Rerank |
| Evaluation | RAGAS (see finQueryEvaluation.md) |
| Infra / Deploy | Docker + docker-compose, Railway or Render |

---

## 3. High-Level Design (HLD)

Three layers: the **frontend** talks to the **backend** over HTTP/SSE; the backend holds the two core pipelines plus the agent and eval modules; the backend calls out to four **external services**.

<svg width="100%" viewBox="0 0 680 620" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="FinQuery high-level architecture">
<defs><marker id="arrowA" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888780" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
<style>
.tA{font-family:sans-serif;font-size:14px;fill:#2C2C2A}.tsA{font-family:sans-serif;font-size:12px;fill:#5F5E5A}.thA{font-family:sans-serif;font-size:14px;font-weight:500;fill:#2C2C2A}
.arrA{stroke:#888780;stroke-width:1.5;fill:none}
</style>
<text class="thA" x="40" y="30">Frontend layer</text>
<rect x="40" y="42" width="600" height="56" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text class="thA" x="340" y="66" text-anchor="middle" fill="#0C447C">React + TypeScript UI</text>
<text class="tsA" x="340" y="84" text-anchor="middle" fill="#185FA5">Upload PDFs, ask questions, see streamed cited answers + eval dashboard</text>
<line x1="340" y1="98" x2="340" y2="136" class="arrA" marker-end="url(#arrowA)"/>
<text class="tsA" x="356" y="121">HTTP / SSE</text>
<text class="thA" x="40" y="160">Backend layer (FastAPI)</text>
<rect x="40" y="172" width="600" height="240" rx="14" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
<rect x="60" y="196" width="270" height="84" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text class="thA" x="195" y="222" text-anchor="middle" fill="#3C3489">Ingestion pipeline</text>
<text class="tsA" x="195" y="244" text-anchor="middle" fill="#534AB7">Parse PDF, chunk text,</text>
<text class="tsA" x="195" y="262" text-anchor="middle" fill="#534AB7">embed, store vectors</text>
<rect x="350" y="196" width="270" height="84" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text class="thA" x="485" y="222" text-anchor="middle" fill="#3C3489">Query pipeline</text>
<text class="tsA" x="485" y="244" text-anchor="middle" fill="#534AB7">Retrieve, rerank, agent</text>
<text class="tsA" x="485" y="262" text-anchor="middle" fill="#534AB7">route, generate answer</text>
<rect x="60" y="300" width="270" height="84" rx="8" fill="#FAEEDA" stroke="#BA7517" stroke-width="0.5"/>
<text class="thA" x="195" y="326" text-anchor="middle" fill="#633806">Evaluation module</text>
<text class="tsA" x="195" y="348" text-anchor="middle" fill="#854F0B">RAGAS: faithfulness,</text>
<text class="tsA" x="195" y="366" text-anchor="middle" fill="#854F0B">relevance, precision</text>
<rect x="350" y="300" width="270" height="84" rx="8" fill="#FAEEDA" stroke="#BA7517" stroke-width="0.5"/>
<text class="thA" x="485" y="326" text-anchor="middle" fill="#633806">Agent router</text>
<text class="tsA" x="485" y="348" text-anchor="middle" fill="#854F0B">Answer, clarify, or</text>
<text class="tsA" x="485" y="366" text-anchor="middle" fill="#854F0B">fall back to web search</text>
<line x1="340" y1="412" x2="340" y2="450" class="arrA" marker-end="url(#arrowA)"/>
<text class="thA" x="40" y="474">External services</text>
<rect x="40" y="486" width="140" height="64" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thA" x="110" y="512" text-anchor="middle" fill="#27500A">Qdrant</text>
<text class="tsA" x="110" y="532" text-anchor="middle" fill="#3B6D11">Vector DB</text>
<rect x="194" y="486" width="140" height="64" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thA" x="264" y="512" text-anchor="middle" fill="#27500A">Gemini API</text>
<text class="tsA" x="264" y="532" text-anchor="middle" fill="#3B6D11">Embed + generate</text>
<rect x="348" y="486" width="140" height="64" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thA" x="418" y="512" text-anchor="middle" fill="#27500A">Cohere</text>
<text class="tsA" x="418" y="532" text-anchor="middle" fill="#3B6D11">Reranking</text>
<rect x="502" y="486" width="138" height="64" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thA" x="571" y="512" text-anchor="middle" fill="#27500A">Web search</text>
<text class="tsA" x="571" y="532" text-anchor="middle" fill="#3B6D11">Fallback tool</text>
</svg>

**Key points:**
- The frontend never talks to Qdrant, Gemini, or Cohere directly — everything goes through the FastAPI backend. This keeps API keys server-side and secure.
- The two pipelines (ingestion and query) are the heart of the system. Everything else supports them.
- The agent router and the evaluation module are the two features that make this stand out from a basic RAG tutorial.

---

## 4. Low-Level Design (LLD)

### 4.1 Ingestion pipeline — runs ONCE per uploaded document

Turns a messy PDF into searchable vectors plus a keyword index, with enough metadata to support citations later.

<svg width="100%" viewBox="0 0 680 560" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ingestion pipeline flow">
<defs><marker id="arrowB" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888780" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
<style>
.tsB{font-family:sans-serif;font-size:12px;fill:#5F5E5A}.thB{font-family:sans-serif;font-size:14px;font-weight:500}.arrB{stroke:#888780;stroke-width:1.5;fill:none}
</style>
<rect x="200" y="20" width="280" height="56" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text class="thB" x="340" y="44" text-anchor="middle" fill="#2C2C2A">1. User uploads PDF</text>
<text class="tsB" x="340" y="62" text-anchor="middle">POST /upload (annual report)</text>
<line x1="340" y1="76" x2="340" y2="98" class="arrB" marker-end="url(#arrowB)"/>
<rect x="200" y="100" width="280" height="56" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text class="thB" x="340" y="124" text-anchor="middle" fill="#3C3489">2. Parse text (pypdf)</text>
<text class="tsB" x="340" y="142" text-anchor="middle" fill="#534AB7">Extract text + page numbers</text>
<line x1="340" y1="156" x2="340" y2="178" class="arrB" marker-end="url(#arrowB)"/>
<rect x="200" y="180" width="280" height="56" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text class="thB" x="340" y="204" text-anchor="middle" fill="#3C3489">3. Chunk text</text>
<text class="tsB" x="340" y="222" text-anchor="middle" fill="#534AB7">SentenceSplitter, ~512 tokens, overlap</text>
<line x1="340" y1="236" x2="340" y2="258" class="arrB" marker-end="url(#arrowB)"/>
<rect x="200" y="260" width="280" height="56" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text class="thB" x="340" y="284" text-anchor="middle" fill="#0C447C">4. Embed each chunk</text>
<text class="tsB" x="340" y="302" text-anchor="middle" fill="#185FA5">Gemini embedding model to vectors</text>
<line x1="340" y1="316" x2="340" y2="338" class="arrB" marker-end="url(#arrowB)"/>
<rect x="160" y="340" width="360" height="72" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thB" x="340" y="364" text-anchor="middle" fill="#27500A">5. Store in Qdrant</text>
<text class="tsB" x="340" y="386" text-anchor="middle" fill="#3B6D11">Vector + payload: text, page, source file,</text>
<text class="tsB" x="340" y="404" text-anchor="middle" fill="#3B6D11">company name, chunk id</text>
<line x1="340" y1="412" x2="340" y2="434" class="arrB" marker-end="url(#arrowB)"/>
<rect x="160" y="436" width="360" height="56" rx="8" fill="#FAEEDA" stroke="#BA7517" stroke-width="0.5"/>
<text class="thB" x="340" y="460" text-anchor="middle" fill="#633806">6. Build BM25 keyword index</text>
<text class="tsB" x="340" y="478" text-anchor="middle" fill="#854F0B">For the keyword half of hybrid search</text>
<text class="tsB" x="40" y="525">Runs once per document. Re-run only when a new report is added.</text>
</svg>

**Step-by-step:**
1. **Upload** — User sends a PDF to `POST /upload`. Handled by `routers/upload.py`.
2. **Parse** — `pypdf` extracts raw text, keeping track of which page each piece came from (needed for citations).
3. **Chunk** — LlamaIndex `SentenceSplitter` breaks text into ~512-token chunks with slight overlap, so context isn't lost at chunk boundaries.
4. **Embed** — Each chunk is sent to the Gemini embedding model, which returns a vector (a list of numbers capturing meaning).
5. **Store** — Vectors go into Qdrant. Crucially, each vector carries a *payload*: the original text, page number, source filename, and company — this metadata is what lets you show citations.
6. **BM25 index** — A keyword index is built so hybrid search can do exact-term matching (ticker symbols, "Q4 2024", etc.) alongside vector search.

> **Logic lives in:** `services/ingestion.py`

### 4.2 Query pipeline — runs on EVERY question

<svg width="100%" viewBox="0 0 680 760" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Query pipeline flow">
<defs><marker id="arrowC" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888780" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
<style>
.tsC{font-family:sans-serif;font-size:12px;fill:#5F5E5A}.thC{font-family:sans-serif;font-size:14px;font-weight:500}.arrC{stroke:#888780;stroke-width:1.5;fill:none}
</style>
<rect x="190" y="20" width="300" height="50" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text class="thC" x="340" y="40" text-anchor="middle" fill="#2C2C2A">1. User asks a question</text>
<text class="tsC" x="340" y="58" text-anchor="middle">POST /query</text>
<line x1="340" y1="70" x2="340" y2="90" class="arrC" marker-end="url(#arrowC)"/>
<rect x="190" y="92" width="300" height="56" rx="8" fill="#FAEEDA" stroke="#BA7517" stroke-width="0.5"/>
<text class="thC" x="340" y="116" text-anchor="middle" fill="#633806">2. Agent router decides</text>
<text class="tsC" x="340" y="134" text-anchor="middle" fill="#854F0B">answer from docs / clarify / web search</text>
<line x1="190" y1="120" x2="122" y2="120" class="arrC" marker-end="url(#arrowC)"/>
<rect x="40" y="92" width="150" height="56" rx="8" fill="#FAECE7" stroke="#D85A30" stroke-width="0.5"/>
<text class="thC" x="115" y="116" text-anchor="middle" fill="#712B13">Web search</text>
<text class="tsC" x="115" y="134" text-anchor="middle" fill="#993C1D">if not in docs</text>
<line x1="340" y1="148" x2="340" y2="170" class="arrC" marker-end="url(#arrowC)"/>
<text class="tsC" x="356" y="161">answer from docs</text>
<rect x="160" y="172" width="360" height="72" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text class="thC" x="340" y="196" text-anchor="middle" fill="#0C447C">3. Hybrid retrieval</text>
<text class="tsC" x="340" y="218" text-anchor="middle" fill="#185FA5">Dense (Qdrant vectors) + sparse (BM25),</text>
<text class="tsC" x="340" y="236" text-anchor="middle" fill="#185FA5">fuse to top ~20 candidate chunks</text>
<line x1="340" y1="244" x2="340" y2="266" class="arrC" marker-end="url(#arrowC)"/>
<rect x="160" y="268" width="360" height="56" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text class="thC" x="340" y="292" text-anchor="middle" fill="#0C447C">4. Rerank (Cohere)</text>
<text class="tsC" x="340" y="310" text-anchor="middle" fill="#185FA5">Re-score, keep best 3-5 chunks</text>
<line x1="340" y1="324" x2="340" y2="346" class="arrC" marker-end="url(#arrowC)"/>
<rect x="160" y="348" width="360" height="56" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text class="thC" x="340" y="372" text-anchor="middle" fill="#3C3489">5. Build prompt</text>
<text class="tsC" x="340" y="390" text-anchor="middle" fill="#534AB7">Question + top chunks + instructions</text>
<line x1="340" y1="404" x2="340" y2="426" class="arrC" marker-end="url(#arrowC)"/>
<rect x="160" y="428" width="360" height="56" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text class="thC" x="340" y="452" text-anchor="middle" fill="#3C3489">6. Generate answer (Gemini)</text>
<text class="tsC" x="340" y="470" text-anchor="middle" fill="#534AB7">Grounded in retrieved chunks only</text>
<line x1="340" y1="484" x2="340" y2="506" class="arrC" marker-end="url(#arrowC)"/>
<rect x="160" y="508" width="360" height="56" rx="8" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
<text class="thC" x="340" y="532" text-anchor="middle" fill="#085041">7. Stream answer (SSE)</text>
<text class="tsC" x="340" y="550" text-anchor="middle" fill="#0F6E56">Token by token back to React</text>
<line x1="340" y1="564" x2="340" y2="586" class="arrC" marker-end="url(#arrowC)"/>
<rect x="160" y="588" width="360" height="56" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thC" x="340" y="612" text-anchor="middle" fill="#27500A">8. Attach citations</text>
<text class="tsC" x="340" y="630" text-anchor="middle" fill="#3B6D11">Source file + page for each chunk used</text>
<text class="tsC" x="40" y="685">Runs on every question. Steps 3-4 are what make retrieval accurate;</text>
<text class="tsC" x="40" y="705">step 2 (the agent) and step 8 (citations) are the standout features.</text>
</svg>

**Step-by-step:**
1. **Question** — User sends a question to `POST /query`. Handled by `routers/query.py`.
2. **Agent router** — Before retrieving anything, the agent decides: answer from the documents, ask the user to clarify, or fall back to web search if the question isn't covered by the reports. This is the "agentic" part.
3. **Hybrid retrieval** — The question is embedded and searched against Qdrant (dense/meaning) AND against the BM25 index (sparse/keyword). Results are fused into ~20 candidate chunks. Two methods catch more than one.
4. **Rerank** — Cohere re-scores those ~20 candidates for true relevance and keeps the best 3-5. This is a quality filter that sharply improves answers.
5. **Build prompt** — The question, the top chunks, and instructions are assembled into a prompt.
6. **Generate** — Gemini produces an answer grounded *only* in the retrieved chunks (so it can't make things up).
7. **Stream** — The answer is sent back to React token-by-token over SSE, so it "types out" live.
8. **Citations** — Each chunk used is mapped back to its source file and page, shown under the answer as proof.

> **Logic lives in:** `services/retrieval.py` (steps 3-4), `services/agent.py` (step 2), `services/generation.py` (steps 5-7), `services/citations.py` (step 8)

---

## 5. Folder & file structure — two independent repos

FinQuery is split into **two separate folders**, each meant to become **its own Git repo**, with its own deployment and its own local dev port. They are decoupled: the frontend is a static app that talks to the backend only over HTTP/SSE, and the only shared contract is the request/response shapes plus the backend URL.

| Folder | Becomes repo | Local dev port | Deploys to |
|---|---|---|---|
| `finquery-backend/` | `finquery-backend` | **8000** (Qdrant on 6333) | Railway / Render (web service) |
| `finquery-frontend/` | `finquery-frontend` | **5173** (Vite default) | Vercel / Netlify / static host |

> **Why two repos?** Independent deploys (UI on a free CDN, backend as a heavier service), keys stay server-side, and you can run both locally on different ports for long-run dev without one restarting the other. See §8 for the cross-repo contract.

### 5.1 `finquery-backend/` — the RAG engine

```
finQueryBackend/                ← ROOT OF ITS OWN GIT REPO
│
├── README.md                    ← backend overview, setup, env vars, deploy notes
├── docker-compose.yml           ← runs backend + Qdrant together (LOCAL DEV ONLY)
├── .gitignore                   ← ignore .env, venv/, data/, __pycache__/
├── .env.example                 ← documents required env vars (no real secrets)
├── .env                         ← API keys (GEMINI_API_KEY, COHERE_API_KEY) — NEVER commit
├── requirements.txt             ← pinned Python dependencies
├── Dockerfile                   ← containerizes the backend
│
├── data/                        ← THE 8-9 ANNUAL REPORT PDFs GO HERE (gitignored)
│   ├── raw/                     ← original downloaded PDFs (apple_10k.pdf, etc.)
│   └── eval/                    ← test questions + expected answers for RAGAS
│
└── app/
    ├── main.py                  ← FastAPI app, route mounting, CORS, startup
    ├── config.py                ← loads env vars, settings (chunk size, top_k, models, CORS origins)
    │
    ├── routers/                 ← API endpoints, one file per concern
    │   ├── upload.py            ← POST /upload  → triggers ingestion
    │   ├── query.py             ← POST /query   → runs query pipeline, streams answer (SSE)
    │   └── evals.py             ← GET  /evals   → returns RAGAS scores
    │
    ├── services/                ← THE CORE LOGIC — the RAG engine lives here
    │   ├── ingestion.py         ← parse → chunk → embed → store (ingestion LLD)
    │   ├── retrieval.py         ← hybrid search + reranking
    │   ├── agent.py             ← the router: answer / clarify / web search
    │   ├── generation.py        ← prompt building + streaming LLM call
    │   ├── citations.py         ← maps chunks back to source file + page
    │   └── evaluation.py        ← RAGAS metrics (see finQueryEvaluation.md)
    │
    ├── clients/                 ← thin wrappers around external services
    │   ├── qdrant_client.py
    │   ├── gemini_client.py
    │   └── cohere_client.py
    │
    └── models/                  ← Pydantic schemas (request/response shapes)
        └── schemas.py
```

### 5.2 `finquery-frontend/` — the UI (static app)

```
finQueryFrontend/               ← ROOT OF ITS OWN GIT REPO
│
├── README.md                    ← frontend overview, setup, env vars, deploy notes
├── .gitignore                   ← ignore node_modules/, dist/, .env
├── .env.example                 ← documents VITE_API_BASE_URL (no secrets)
├── .env                         ← local: VITE_API_BASE_URL=http://localhost:8000 (gitignored)
├── package.json
├── Dockerfile                   ← OPTIONAL — only if containerizing the static build
├── vite.config.ts               ← dev server port (5173) + optional /api proxy
├── tailwind.config.js
├── tsconfig.json
├── index.html                   ← Vite HTML entry
│
└── src/
    ├── main.tsx                 ← React entry point
    ├── App.tsx                  ← top-level layout
    │
    ├── components/              ← reusable UI pieces
    │   ├── ChatBox.tsx          ← question input + streamed answer
    │   ├── FileUpload.tsx       ← drag-drop PDF upload
    │   ├── SourceCitation.tsx   ← shows cited chunk + page
    │   ├── MessageList.tsx      ← conversation history
    │   └── EvalDashboard.tsx    ← RAGAS scores view
    │
    ├── hooks/
    │   └── useStreamingQuery.ts ← handles SSE token streaming
    │
    ├── api/
    │   └── client.ts            ← functions that call the backend (reads VITE_API_BASE_URL)
    │
    └── types/
        └── index.ts             ← shared TypeScript types (mirror of backend schemas.py)
```

### Why it's structured this way (notes for new contributors)

- **`data/` (backend) is where the PDFs go** — specifically `data/raw/`. Keep it out of Git (it's large); the README lists download links so anyone can fetch the same set. `data/eval/` holds the RAGAS test-question set.
- **`services/` (backend) is the most important folder** — it is the actual RAG engine, and each file maps almost one-to-one to a step in the LLD diagrams above. When showing the code to anyone, open this folder first.
- **`routers/` vs `services/` split** — routers handle HTTP (parse request, return response); services hold the logic. Standard professional backend pattern.
- **`clients/` isolates each external service** behind one file, so swapping Gemini for OpenAI later means changing one file.
- **`api/client.ts` (frontend) is the single door to the backend** — every network call goes through it and reads the backend URL from one env var, so switching local ↔ prod is one config change.
- **No secrets in the frontend** — anything in a `VITE_*` var is bundled into the public JS, so it must be non-sensitive (just the backend URL). All API keys live in the backend.

---

## 8. Cross-repo contract (how the two halves stay in sync)

The two repos are independent but agree on three things:

| Concern | `finquery-backend` | `finquery-frontend` |
|---|---|---|
| Local port | `8000` (Qdrant `6333`) | `5173` |
| Base URL | serves the API | `VITE_API_BASE_URL=http://localhost:8000` |
| CORS | `main.py` allows `FRONTEND_ORIGIN` | sends requests to the backend origin |
| Endpoints | implements `POST /upload`, `POST /query` (SSE), `GET /evals` | calls them from `src/api/client.ts` |
| Shared shapes | `app/models/schemas.py` | `src/types/index.ts` |

**CORS** — because the two run on different origins, the backend must allow the frontend's origin explicitly (read from a `FRONTEND_ORIGIN` env var):

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],   # http://localhost:5173 in dev
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Deployment** — frontend builds to static files (`vite build` → `dist/`) and goes on a CDN/static host; backend deploys as a web service with managed Qdrant (Qdrant Cloud or a separate container). The `docker-compose.yml` in the backend repo is **local-dev only**, not the production topology.

The only real coupling is the **request/response shapes** and the **backend URL** — keep `types/index.ts` aligned with `schemas.py` and the two repos can be developed, deployed, and scaled independently.

---

## 6. The 8-9 documents and where to get them

**Corpus:** real annual reports (10-K filings) from recognizable US public companies. Real reports are dense and table-heavy — exactly the messiness that makes RAG look impressive.

**Starter set of 8:** Apple, Microsoft, Nvidia, Tesla, Amazon, Alphabet, Coca-Cola, Walmart.

**Where to download (all free):**
1. **SEC EDGAR** — official source for every US public company 10-K. Search UI: https://www.sec.gov/cgi-bin/browse-edgar — filter by form type "10-K".
2. **Investor Relations pages** — cleaner PDFs (e.g. investor.apple.com, microsoft.com/investor).
3. **AnnualReports.com** — https://www.annualreports.com — free library of annual report PDFs.

**During development:** ingest only 1-2 reports (re-embedding 8 long PDFs each time is slow and burns API credits). Batch-ingest all 8 once the pipeline is finalized. Prefer text-based PDFs; avoid scanned/image-only ones at first (they need OCR).

---

## 7. The core mental model

If you understand this chain, you understand the whole system:

**chunk → embed → store → retrieve → rerank → augment → generate → evaluate**

Everything in the code is just implementing one of those steps.
