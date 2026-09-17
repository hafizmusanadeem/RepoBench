# RepoBench API

A thin FastAPI layer over the existing evaluation code (`agents/`,
`benchmark/`, `evals/`). It doesn't reimplement any evaluation logic — it
lists the tasks already defined in `benchmark/tasks/*.yaml`, launches real
`evals.repobench.repobench` runs through `inspect_ai.eval_async`, and turns
the resulting `EvalLog` into the JSON the frontend renders.

## Running it

From the project root, with the project's own dependencies installed
(`uv sync` or `pip install -e .`) plus this API's two extra deps:

```bash
pip install fastapi "uvicorn[standard]"
uv run uvicorn backend.main:app --reload --port 8000
```

Whatever running a task from the CLI already requires, running it from here
requires too: Docker for the per-repository sandbox, the repository cloned
under `repos/<name>` (see `repos/README.md`), and credentials for whichever
model you pick in the "Agent" dropdown (e.g. `ANTHROPIC_API_KEY` for
`anthropic/claude-sonnet-4-6`). If any of that's missing, a run finishes
with `status: "error"` and a message explaining why — it won't crash the
server or hang.

## Connecting the frontend

In dev, `frontend/vite.config.ts` proxies `/api/*` to `http://localhost:8000`
automatically — just run both:

```bash
uv run uvicorn backend.main:app --reload --port 8000   # terminal 1
cd frontend && npm run dev                              # terminal 2
```

For a build that talks to a backend hosted somewhere else, set
`VITE_API_BASE_URL` (see `frontend/.env.example`).

## Endpoints

| Method | Path                     | Purpose                                          |
| ------ | ------------------------ | ------------------------------------------------- |
| GET    | `/api/tasks`              | Tasks from `benchmark/tasks/*.yaml`               |
| GET    | `/api/agents`              | Models offered in the "Agent" dropdown            |
| GET    | `/api/runs`                | Run history, newest first                         |
| GET    | `/api/runs/{run_id}`       | One run, including its tool-call transcript        |
| POST   | `/api/runs`                | Start a run: `{taskId, agent, maxToolCalls}`       |
| GET    | `/api/dashboard/metrics`   | Totals/pass/fail/running for the dashboard cards   |

## Configuration

Both are optional environment variables:

- `REPOBENCH_MODELS` — comma-separated inspect_ai model strings for the
  "Agent" dropdown. Defaults to `anthropic/claude-sonnet-4-6`.
- `REPOBENCH_CORS_ORIGINS` — comma-separated allowed origins. Defaults to
  `http://localhost:5173` (Vite's default dev port).

## Storage

Run history lives in `backend/data/runs.json`, a flat JSON file (see
`backend/store.py`) — enough to survive a backend restart without adding a
database dependency. `backend/data/` is gitignored. Swap `store.py` for a
real database later without touching any callers (`main.py`/`runner.py`
only use `list_runs` / `get_run` / `create_run` / `update_run`).

Each completed run's full transcript is cached directly on its record when
the evaluation finishes, so reading a run back doesn't need to re-parse
inspect_ai's own `.eval` log files (also written, to `backend/data/logs/`,
in case you want to open a run in `inspect view` separately).

## A note on tool names

The transcript shows the agent's real tools — `bash`, `text_editor`,
`think`, and the `react()` agent's own submit tool (see
`agents/coding_agent.py`) — not placeholder names. `RunDetails.tsx` renders
each of these argument shapes directly.
