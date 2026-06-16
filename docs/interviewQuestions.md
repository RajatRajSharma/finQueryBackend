# FinQuery — Interview Questions & Topics

Questions an interviewer could ask about this project, grouped **Beginner → Intermediate → Hard**. Topics only (no answers) — use them to check what you can explain confidently. Grounded in the actual stack: FastAPI, Qdrant, Gemini, LlamaIndex, BM25, Cohere rerank, SSE, agent routing, RAGAS, Docker.

---

## Beginner — fundamentals & "what is this?"

1. What is RAG, and what problem does it solve over a plain LLM?
2. Walk me through your pipeline in one sentence: chunk → embed → store → retrieve → augment → generate.
3. What is an embedding? Why turn text into vectors?
4. What is a vector database, and why Qdrant here instead of a normal SQL DB?
5. Why do you chunk documents instead of embedding whole PDFs?
6. What is "top-k" retrieval and how did you pick k?
7. What are citations in your answer, and why do they matter for trust?
8. What is cosine similarity / nearest-neighbour search?
9. Why FastAPI? What does Pydantic give you?
10. What's the difference between `/health` (liveness) and `/health/ready` (readiness)?
11. How does a question flow from the React UI to an answer? (HTTP path)
12. What goes in `.env` and why are API keys never in the frontend?
13. What is "grounding," and how do you stop the model from making things up?
14. Why did the original scanned PDFs produce zero chunks? (text vs image PDFs)
15. What does the embedding dimension (768) have to do with the Qdrant collection?

## Intermediate — design, retrieval, API

16. Explain Dependency Inversion — how do your services avoid importing Gemini/Qdrant directly?
17. What is the "composition root" (factory.py) and why centralize vendor choice there?
18. How would you swap Gemini → OpenAI? How many files change, and why so few?
19. What design pattern is "one class per vendor behind an interface"? (Adapter / Strategy / Ports & Adapters)
20. Why separate domain models (`domain.py`) from API schemas (`schemas.py`)?
21. How do your tests run with no Qdrant, no API key, no PDFs? (fakes / interface-driven testing)
22. What is hybrid retrieval? Why combine dense vectors with BM25?
23. What does BM25 catch that embeddings miss? (exact terms, tickers, "Q4 2024")
24. How do you fuse dense + sparse results when their scores are on different scales? (normalize + weighted / RRF)
25. What does `HYBRID_ALPHA` control, and why did you keep it at 0.5?
26. What is a reranker (cross-encoder) and where does it sit in the pipeline?
27. Why over-fetch `RETRIEVE_CANDIDATES` (20) then rerank down to top-k (5)?
28. What is SSE, and why use it over WebSockets or plain JSON for streaming answers?
29. Why can't `EventSource` call `POST /query/stream`? How did you stream from a POST?
30. How do you send the answer tokens and then the citations over one SSE stream?
31. How do you map a vendor error (Gemini 429/503) to a clean HTTP 503 instead of a raw 500?
32. Why are rerank/hybrid/agent features behind `ENABLE_*` flags?
33. What's idempotent upsert in Qdrant, and why derive a UUID from the chunk id?
34. How does CORS work here, and why does the backend need `FRONTEND_ORIGIN`?
35. What does the Dockerfile do, and why a `.dockerignore`? Why run as non-root?
36. What's the difference between the per-minute and per-day Gemini quota?

## Hard — agents, evaluation, scaling, trade-offs

37. What makes this "agentic RAG" vs plain RAG? Describe the router (answer / clarify / web-search).
38. How does the agent decide a route, and what's the safe fallback if it fails?
39. Why is the web-search fallback opt-in and labelled distinctly from doc answers?
40. What is RAGAS? Explain faithfulness, answer relevancy, context precision, context recall.
41. Which metrics grade *generation* vs *retrieval*, and how does that tell you what to fix?
42. What does "LLM-as-judge" mean, and what are its risks/biases?
43. Why did faithfulness sometimes score 0.0 on Gemini? (non-OpenAI judge prompt-parsing quirk)
44. How did you keep RAGAS under the free-tier rate limit? (rate limiter + single worker + small sample)
45. Explain the multi-key rotation — when does it rotate, and why not retry an exhausted key?
46. Why does key rotation fix the *daily* cap but not the *per-minute* burst within one run?
47. Why cache `/evals` with a TTL, and why run it in the background instead of blocking the request?
48. What is a "baseline" run and how does it show the improvement story (before/after)?
49. How would you build a ground-truth eval set, and how do you avoid overfitting to it?
50. What's the dependency-pinning trap you hit with RAGAS + langchain, and how did you resolve it?
51. How would you scale this to thousands of documents / many users? (BM25 in-memory limit, Qdrant Cloud, stateless API)
52. Where does the BM25 index live, and what's its freshness trade-off after a new upload?
53. How would you handle multi-tenant isolation (one user's docs not leaking into another's)?
54. How do you evaluate/limit cost and latency in production? (caching, smaller models, batching)
55. What are the failure modes of RAG, and how does each metric or feature mitigate them?
56. How would you add streaming + reranking together without blocking the event loop?
57. What would you change for a production deploy (Qdrant Cloud, secrets, autoscaling, observability)?
58. How do you prevent prompt injection from a malicious uploaded document?
59. What are the trade-offs of chunk size (256 vs 512 vs 1024) on retrieval quality?
60. If answers are wrong, how do you diagnose whether it's retrieval or generation at fault?
61. How would you A/B test a retrieval change and prove it helped with numbers?
62. Why interface-driven design over "just call the SDK" — what does it cost vs buy?
63. How would you add conversation memory / multi-turn follow-ups to this RAG?
64. What's your strategy for table-heavy 10-K data that simple text chunking mangles?

## "Tell me about…" framing (behavioural + system)

65. Walk me through the hardest bug or limitation you hit and how you handled it.
66. What did you deliberately leave out, and why (scope discipline)?
67. If you had one more week, what would you improve first and why?
68. How did you keep a working slice at every step while adding features?
