# FinQuery backend — assistant guide

Agentic RAG over company 10-Ks. Read [docs/finQueryArchitecture.md](docs/finQueryArchitecture.md) for the design; weekly plans are [docs/w1Plan.md](docs/w1Plan.md), [docs/w2Plan.md](docs/w2Plan.md), [docs/w3Plan.md](docs/w3Plan.md).

## Env & tuning log — keep it in sync

`docs/tuning.md` is a living table of every env var, its current value, and a
**confidence %** (how close to optimal, tied to an evidence level: `untested`
≤55%, `eyeballed` ≤80%, `RAGAS` up to 100%).

- **Before tuning or suggesting a value**, consult `docs/tuning.md` first.
- **Whenever you change an env var** (`app/config.py`, `.env`, `.env.example`),
  update the matching row + Changelog in `docs/tuning.md` in the same change.
- **When you test a config change** (run a query/comparison under a given
  config), append the call + result to `docs/tuning-runs.md` so it's recorded.
- Confidence is honest: only mark a value `RAGAS`/>80% once Week 3 RAGAS numbers
  back it. Never invent a precise % implying a measurement we don't have.

## Project constraints

- **Gemini is free-tier**: embeds capped ~100/min, `gemini-2.5-flash` 503s under
  load. Don't bulk-ingest all 8 reports at once; pace RAGAS runs.
- **Design rule**: new vendors go behind an interface in `app/core/interfaces.py`
  and are wired in `app/core/factory.py` — one class + one builder, gated by an
  `ENABLE_*` flag so the prior working path is always the fallback.
- Tests are fake-backed (`tests/fakes.py`) — run `pytest -q`, no infra needed.
