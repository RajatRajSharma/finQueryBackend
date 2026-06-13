# FinQuery — Evaluation Module (RAGAS)

> **What this doc is:** explains how FinQuery measures whether its RAG answers are actually good, using RAGAS metrics. This is the project's standout feature — most portfolio RAG projects skip evaluation entirely. Read finQueryArchitecture.md first for the overall system.

---

## 1. Why evaluation matters

After the system answers a question, you can't just eyeball it and say "looks right." The evaluation module runs a set of **test questions** through the pipeline and scores the results on specific quality dimensions using **RAGAS** (Retrieval-Augmented Generation Assessment).

Cleverly, RAGAS uses an **LLM as a judge** to score the outputs — you are using AI to grade your AI. Each score runs from 0 to 1, higher is better.

**Why this is the differentiator:**
- It shows engineering maturity — you treat the AI system like software that needs testing, not a magic box.
- It gives a concrete improvement story: *"I added reranking and faithfulness went from 0.78 to 0.93."* That measurable result is far stronger on a resume than "built a RAG app."

---

## 2. The evaluation flow

<svg width="100%" viewBox="0 0 680 600" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="FinQuery evaluation module flow">
<defs><marker id="arrowE" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888780" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
<style>
.tsE{font-family:sans-serif;font-size:12px;fill:#5F5E5A}.thE{font-family:sans-serif;font-size:14px;font-weight:500}.arrE{stroke:#888780;stroke-width:1.5;fill:none}
</style>
<rect x="180" y="20" width="320" height="56" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text class="thE" x="340" y="44" text-anchor="middle" fill="#2C2C2A">1. Test question set</text>
<text class="tsE" x="340" y="62" text-anchor="middle">~20 Q + ground-truth answers (data/eval)</text>
<line x1="340" y1="76" x2="340" y2="98" class="arrE" marker-end="url(#arrowE)"/>
<rect x="180" y="100" width="320" height="72" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text class="thE" x="340" y="124" text-anchor="middle" fill="#0C447C">2. Run through query pipeline</text>
<text class="tsE" x="340" y="146" text-anchor="middle" fill="#185FA5">For each question, collect:</text>
<text class="tsE" x="340" y="164" text-anchor="middle" fill="#185FA5">question, answer, retrieved contexts</text>
<line x1="340" y1="172" x2="340" y2="194" class="arrE" marker-end="url(#arrowE)"/>
<rect x="180" y="196" width="320" height="56" rx="8" fill="#FAEEDA" stroke="#BA7517" stroke-width="0.5"/>
<text class="thE" x="340" y="220" text-anchor="middle" fill="#633806">3. RAGAS scores each result</text>
<text class="tsE" x="340" y="238" text-anchor="middle" fill="#854F0B">LLM-as-judge grades 3 metrics</text>
<line x1="340" y1="252" x2="340" y2="282" class="arrE" marker-end="url(#arrowE)"/>
<rect x="40" y="284" width="190" height="76" rx="8" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
<text class="thE" x="135" y="308" text-anchor="middle" fill="#085041">Faithfulness</text>
<text class="tsE" x="135" y="330" text-anchor="middle" fill="#0F6E56">Is the answer backed</text>
<text class="tsE" x="135" y="348" text-anchor="middle" fill="#0F6E56">by the chunks?</text>
<rect x="245" y="284" width="190" height="76" rx="8" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
<text class="thE" x="340" y="308" text-anchor="middle" fill="#085041">Answer relevancy</text>
<text class="tsE" x="340" y="330" text-anchor="middle" fill="#0F6E56">Does it address</text>
<text class="tsE" x="340" y="348" text-anchor="middle" fill="#0F6E56">the question?</text>
<rect x="450" y="284" width="190" height="76" rx="8" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
<text class="thE" x="545" y="308" text-anchor="middle" fill="#085041">Context precision</text>
<text class="tsE" x="545" y="330" text-anchor="middle" fill="#0F6E56">Did retrieval pull</text>
<text class="tsE" x="545" y="348" text-anchor="middle" fill="#0F6E56">relevant chunks?</text>
<line x1="135" y1="360" x2="318" y2="402" class="arrE" marker-end="url(#arrowE)"/>
<line x1="340" y1="360" x2="340" y2="402" class="arrE" marker-end="url(#arrowE)"/>
<line x1="545" y1="360" x2="362" y2="402" class="arrE" marker-end="url(#arrowE)"/>
<rect x="180" y="404" width="320" height="72" rx="8" fill="#EAF3DE" stroke="#639922" stroke-width="0.5"/>
<text class="thE" x="340" y="428" text-anchor="middle" fill="#27500A">4. Aggregate + show scores</text>
<text class="tsE" x="340" y="450" text-anchor="middle" fill="#3B6D11">GET /evals returns averages,</text>
<text class="tsE" x="340" y="468" text-anchor="middle" fill="#3B6D11">React dashboard displays them</text>
<text class="tsE" x="40" y="515">Each score is 0 to 1. Higher is better. Aim to show 0.9+ faithfulness.</text>
<text class="tsE" x="40" y="538">Run this whenever you change chunking, retrieval, or prompts to prove improvement.</text>
</svg>

**Step-by-step:**
1. **Test question set** — A fixed set of ~20 questions with known correct ("ground-truth") answers, stored in `data/eval/`.
2. **Run the pipeline** — Each question goes through the normal query pipeline. For each, capture three things: the question, the answer the system produced, and the contexts (chunks) it retrieved.
3. **RAGAS scores** — RAGAS uses an LLM judge to grade each result on the three metrics below.
4. **Aggregate + display** — Scores are averaged and exposed via `GET /evals`; the React `EvalDashboard.tsx` shows them as score cards or a bar chart.

---

## 3. The three metrics (in plain terms)

### Faithfulness — the headline metric
Checks whether every claim in the answer is actually supported by the retrieved chunks, or whether the LLM made something up (hallucinated). If the system says "Apple's revenue grew 8%" but no retrieved chunk mentions that, faithfulness drops. High faithfulness means "my system doesn't lie."

### Answer relevancy
Does the answer actually address the question asked? You can have a faithful answer that rambles about something tangential — this catches that.

### Context precision
Grades **retrieval specifically**, not the answer. Of the chunks pulled back, how many were genuinely relevant? Low precision means hybrid search + reranking is dragging in noise, which points you at fixing retrieval rather than the prompt.

### The useful split
- **Faithfulness + answer relevancy** grade the *generation* (the LLM's answer).
- **Context precision** grades the *retrieval* (Qdrant + BM25 + Cohere).

So if answers are bad, the scores tell you *which half of the pipeline* to fix.

---

## 4. What you build

Core of `services/evaluation.py` — assemble a dataset (test questions, the answers the pipeline produced, and the contexts it retrieved), then hand it to RAGAS:

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from datasets import Dataset

def run_evaluation(eval_records):
    # eval_records: list of {question, answer, contexts, ground_truth}
    dataset = Dataset.from_list(eval_records)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
    )
    return result  # averaged scores per metric
```

The `eval_records` come from running the ~20 test questions through the normal query pipeline and capturing what it returned.

### Test-question file format (`data/eval/questions.json`)

```json
[
  {
    "question": "What was Apple's total net sales for the fiscal year?",
    "ground_truth": "Apple reported total net sales of $X billion."
  },
  {
    "question": "What are the main risk factors Tesla lists?",
    "ground_truth": "Tesla lists supply chain, regulatory, and competition risks, among others."
  }
]
```

(The `contexts` and `answer` fields are filled in automatically when you run each question through the pipeline — you only hand-write `question` and `ground_truth`.)

---

## 5. Practical notes

- **API usage:** RAGAS calls an LLM to do the grading, so running evals consumes API calls. With Gemini's free tier and only ~20 test questions, this stays well within free limits — just don't run it in a tight loop.
- **When to run:** Run evals whenever you change chunking strategy, retrieval settings, or prompts. The before/after scores are how you prove an improvement actually helped.
- **What to screenshot for your README:** the eval dashboard showing your scores (aim for 0.9+ faithfulness). This is strong, concrete evidence the system works.

---

## 6. Interview talking points

- "I didn't just build RAG — I measured it. Faithfulness, answer relevancy, and context precision via RAGAS."
- "The metrics are diagnostic: generation metrics vs a retrieval metric, so I know which half to fix."
- "Adding Cohere reranking improved context precision and faithfulness measurably." *(Fill in your real before/after numbers once you run it.)*
