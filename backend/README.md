# RepoBench API

Evaluate coding agents on **any git repository** and get a recommendation for which one fits it best.

## Run
```bash
uv sync                      # or pip install -e .
uv run uvicorn backend.main:app --reload --port 8000
cd frontend && npm i recharts && npm run dev
```
Needs Docker, git, and credentials for each model you enable (e.g. `ANTHROPIC_API_KEY`).

## Flow
1. `POST /api/repos` clones the repo (full history), detects language/install/test commands (`profiler.py`), writes a Dockerfile + compose.yaml under `backend/data/sandboxes/<id>/`.
2. You edit the detected commands in the UI.
3. `POST /api/evaluations` builds the image once (network on), then runs every agent x repeat as its own `python -m backend.worker <run_id>` process (sandbox network off), `REPOBENCH_MAX_PARALLEL_RUNS` at a time.
4. Each run records the agent's diff, tokens, cost, regressions and transcript.
5. `GET /api/evaluations/{id}/recommendation` ranks agents (Wilson lower bound on pass rate, blended with median cost/time using the weights you set).

## Agents
```bash
REPOBENCH_MODELS=anthropic/claude-sonnet-4-6
REPOBENCH_CLI_AGENTS=claude_code:anthropic/claude-sonnet-4-6,codex:openai/gpt-5-codex,gemini:google/gemini-2.5-pro
pip install inspect-swe      # needed for the CLI agents
```
Other env vars: `REPOBENCH_PRICES` (cost table, check the defaults), `REPOBENCH_JUDGE_MODEL`, `REPOBENCH_RUN_TIME_LIMIT`, `REPOBENCH_MAX_PARALLEL_RUNS`, `REPOBENCH_CORS_ORIGINS`.

## Grading user tasks
- Bug kinds: the verify command must pass, and existing test files must not be edited or deleted.
- All kinds: the repo's test command must not regress against a baseline run captured before the agent starts (pre-existing failures are not blamed on the agent).
- Features: optional LLM review of the diff.

## Storage
`backend/data/repobench.db` (SQLite, WAL). The old `runs.json` is not migrated.

## Known limits
- No live transcript: it is saved when a run finishes.
- Test-failure comparison parses pytest / go / cargo / jest-style output; other runners fall back to "any failure after a clean baseline is a regression".
- Repos needing services (databases, network) at test time won't work in the offline sandbox.
