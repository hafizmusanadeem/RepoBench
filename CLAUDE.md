# CLAUDE.md — RepoBench Build Plan

## 1. Project Goal

Build RepoBench into a repository-specific coding-agent evaluation platform.

A user should be able to provide a Git repository URL and a task describing a feature to implement, a bug to fix, a failing test to resolve, or a refactor to perform. RepoBench should profile the repository, record its baseline test state, and run multiple coding agents against equivalent isolated copies of the same starting commit. It should evaluate each result, capture patches and execution metrics, compare the agents, and recommend the best agent for that repository and task type.

The product must answer:

> “For this repository and this kind of task, which coding agent is most likely to produce a correct change, at what cost, and how quickly?”

### Product principles

- **Do not rebuild from scratch.** Extend the current project and preserve working code, API contracts, and UI patterns.
- **Comparable runs:** every agent in an evaluation must receive the same task specification and equivalent repository state.
- **Honest evaluation:** record baseline failures before agents run; do not blame agents for failures that already existed.
- **Correctness before rankings:** a recommendation is only as trustworthy as patch capture, verification, and metric collection.
- **Repository-specific recommendations:** distinguish feature tasks from bug-fix tasks and disclose small sample sizes or low confidence.
- **Reproducibility:** persist repository URL/ref/commit, task, agent configuration, verification commands, run outcomes, and relevant logs.
- **Isolation and safety:** never execute untrusted repository setup or agent-generated code on the host. Treat Docker builds as untrusted code execution too; make network/build permissions explicit.
- **No fabricated metrics:** if token usage, cost, or a measurement is unavailable, store/display it as unknown rather than zero.
- **No external side effects without permission:** do not push branches, create remote PRs, publish packages, or change external resources unless explicitly requested.

## 2. Tech Stack and Current Folder Structure

First inspect the working tree. The uploaded project has these main components; filenames and implementation details may differ in the active checkout, so verify before editing.

### Stack

- **Backend:** Python 3.13+, FastAPI, Uvicorn, Pydantic, `inspect_ai`, optional `inspect-swe`.
- **Agent execution:** existing ReAct baseline plus CLI-agent adapters intended for Claude Code, Codex CLI, and Gemini CLI.
- **Evaluation:** Inspect AI task/runner patterns, Docker-based sandboxes, baseline tests, patch/test scoring.
- **Repository handling:** Git clone/cache and repository profiler.
- **Persistence:** SQLite-backed run/evaluation store (verify the active `backend/store.py`; migrate away from whole-file JSON persistence if the active checkout still uses it).
- **Frontend:** React, TypeScript, Vite, React Router, Tailwind CSS v4, Recharts.
- **Frontend API:** `frontend/src/lib/api.ts`.
- **Charts and comparisons:** Recharts and existing comparison/diff components.

### Expected structure

```text
.
├── agents/
│   ├── coding_agent.py
│   └── system_prompt.txt
├── backend/
│   ├── main.py                 # FastAPI routes and API composition
│   ├── schemas.py              # API/domain request and response models
│   ├── config.py               # configuration, models, pricing
│   ├── repos.py                # clone/cache/ref/commit handling
│   ├── profiler.py             # language/package/test/build detection
│   ├── sandbox.py              # isolated sandbox configuration
│   ├── taskbuilder.py          # task specification construction
│   ├── agents_registry.py      # agent definitions and adapter factory
│   ├── runner.py               # evaluation orchestration
│   ├── worker.py               # subprocess/worker entry point
│   ├── bg.py                   # background task support, if still used
│   ├── transcript.py           # logs, patch, and run metrics
│   ├── recommend.py            # aggregate metrics and recommendations
│   ├── store.py                # persistent storage
│   └── data/                   # runtime data; must be gitignored
├── benchmark/
│   ├── baseline.py             # clean-checkout baseline verification
│   ├── dataset.py
│   ├── scorer.py               # verification and regression scoring
│   ├── sandbox_utils.py
│   └── tasks/
├── frontend/
│   ├── src/
│   │   ├── lib/api.ts
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── NewEvaluation.tsx
│   │   │   ├── Evaluations.tsx
│   │   │   ├── EvaluationDetail.tsx
│   │   │   ├── Runs.tsx
│   │   │   └── RunDetails.tsx
│   │   └── components/
│   │       ├── ComparePanel.tsx
│   │       └── ui/
│   ├── package.json
│   └── vite.config.ts
├── pyproject.toml
├── .gitignore
└── CLAUDE.md
```

### Existing implementation to reuse

Inspect these before writing anything new:

- `backend/repos.py`, `backend/profiler.py`, `backend/sandbox.py`
- `backend/agents_registry.py`, `agents/coding_agent.py`
- `backend/taskbuilder.py`, `benchmark/baseline.py`, `benchmark/scorer.py`
- `backend/runner.py`, `backend/worker.py`, `backend/transcript.py`
- `backend/recommend.py`, `backend/store.py`, `backend/schemas.py`, `backend/main.py`
- `frontend/src/lib/api.ts`, `NewEvaluation.tsx`, `EvaluationDetail.tsx`, `Evaluations.tsx`, `Runs.tsx`, `RunDetails.tsx`, `Dashboard.tsx`, `ComparePanel.tsx`
- `pyproject.toml`, `frontend/package.json`, `.gitignore`, and README files.

Do not assume a feature is absent merely because it needs improvement. Trace its full path from frontend → API → service/runner → storage → API response → frontend before changing it.

## 3. Step-by-Step Tasks in Order

## Task 0 — Establish the actual baseline and protect the working tree

### Work

1. Inspect repository status, tracked files, current branches, and uncommitted changes.
2. Read the project README and dependency manifests.
3. Map each user-facing workflow to its API route and backend implementation.
4. Identify which previously implemented features are complete, partial, or absent. Do not duplicate complete features.
5. Create a concise implementation checklist in your response or a local planning note; keep this `CLAUDE.md` as the governing plan.
6. Do not reset, clean, overwrite user work, or change dependency versions just to make the project easier to modify.

### Acceptance criteria

- A baseline report identifies the current Git state, key routes, and the actual storage implementation.
- Every item in the remaining tasks is marked **present and verified**, **present but incomplete**, or **missing** based on code inspection and tests.
- Existing uncommitted user changes are preserved.
- No remote push, PR, deployment, or other external side effect occurs.

### Commands Claude should run

```bash
git status --short --branch
git log -5 --oneline
git ls-files
find backend benchmark agents frontend/src -maxdepth 3 -type f | sort
cat pyproject.toml
cat frontend/package.json
```

Read the README and inspect the relevant files before deciding what to edit. If `find` is unavailable on the host, use the shell's equivalent.

---

## Task 1 — Make configuration and runtime behavior reliable

### Work

1. Check `.gitignore`: root-scope generic Python rules such as `lib/` and `lib64/` so they do not hide `frontend/src/lib/`. Ignore runtime state such as `backend/data/`, logs, caches, local databases, `.env`, and secrets.
2. Confirm `frontend/src/lib/api.ts` and `frontend/src/lib/utils.ts` are tracked and imports resolve correctly.
3. Check that runtime data directories are created safely at startup.
4. Check environment configuration and document required variables without committing secrets.
5. Confirm backend error responses are structured and do not expose secrets, raw environment variables, or sensitive filesystem paths.
6. Do not change dependency versions unless an observed compatibility problem requires it.

### Acceptance criteria

- `git check-ignore -v frontend/src/lib/api.ts` does not report that the source file is ignored.
- Runtime database/log files and secrets are ignored by Git.
- A clean checkout can install dependencies using the documented commands.
- Missing optional configuration produces an actionable error rather than a cryptic traceback.
- No API key, token, password, or local secret is committed.

### Commands Claude should run

```bash
git check-ignore -v frontend/src/lib/api.ts || true
git check-ignore -v backend/data/example.db || true
git status --short
```

After inspecting the manifests, run the appropriate backend and frontend dependency/install checks in Task 7.

---

## Task 2 — Finish arbitrary repository intake and profiling

### Work

1. Complete or verify the repository intake API, preferably `POST /api/repos` with a validated URL and optional ref.
2. Clone repositories into a controlled cache; support a branch, tag, or commit ref and record the resolved immutable commit SHA.
3. Validate URLs and refs. Reject unsupported protocols and unsafe local paths; prevent path traversal and repository-name collisions.
4. Reuse `backend/profiler.py` to detect language, package manager, dependency files, test/build/lint commands, and likely project root. Begin with markers such as `pyproject.toml`, `pytest.ini`, `package.json`, lockfiles, `go.mod`, `Cargo.toml`, and `pom.xml`.
5. Return detected commands as suggestions, not unquestionable truth. Allow users to edit test/build/lint commands before evaluation.
6. Handle monorepos and ambiguous/missing commands explicitly. Never silently invent a verification command.
7. Cache by canonical repository identity and resolved commit; do not trust a cached directory without checking its origin and state.

### Acceptance criteria

- A valid public Git URL can be registered and cloned to the configured cache.
- A requested ref resolves to a recorded commit SHA; invalid refs return a clear 4xx response.
- Unsupported schemes and local filesystem paths are rejected unless a deliberate, documented local-repository mode exists.
- Profiling returns detected files/language/package manager and proposed commands with confidence or explanatory notes.
- A repository with no recognizable test command is marked **verification not configured**, not automatically passed.
- Re-registering the same URL/ref reuses a verified cache or safely refreshes it without corrupting active runs.
- The frontend displays the repository profile and lets the user edit commands before starting an evaluation.

### Commands Claude should run

```bash
# Inspect current implementation and route contracts
rg -n "repo|clone|profile|test_command|build_command" backend frontend/src

# Use the project’s configured Python environment for syntax/tests after edits
python -m compileall backend benchmark agents
```

Add automated tests for valid URLs, invalid schemes, bad refs, clone failures, cache reuse, monorepos, and unknown test commands.

---

## Task 3 — Standardize tasks and baseline verification

### Work

1. Reuse `backend/taskbuilder.py` and existing schemas. Ensure tasks support:
   - **Feature:** a user-described behavior or capability.
   - **Bug:** an error description and optional stack trace.
   - **Failing test:** a test command or test identifier that should fail before the fix and pass after it.
   - **Refactor:** a constrained change with regression checks.
2. Every task must store a normalized task kind, user prompt, repository URL, base commit SHA, setup commands, verification commands, and applicable timeout/resource limits.
3. Run baseline verification on a clean copy of the exact base commit before any agent modifies its workspace.
4. Store baseline command, exit code, output, duration, and known failing tests. Separate baseline failures from newly introduced failures.
5. For bug/failing-test tasks, do not count an error message alone as proof of a fix. A meaningful verification command must exist.
6. If the target bug cannot be reproduced, mark the task as **not reproducible at baseline** and explain that result; do not silently award a pass.
7. Preserve existing task fixtures and scorer behavior unless tests demonstrate a defect.

### Acceptance criteria

- Each task is immutable after the evaluation starts, or the evaluation stores a full snapshot/hash of its task specification.
- Baseline results are persisted and linked to the exact repository commit.
- A baseline failure remains distinguishable from a regression introduced by an agent.
- Bug tasks whose verification command already passes at baseline cannot be marked as a successful fix solely because that command still passes.
- A task with no usable verification is labelled **unverified** or **needs human review**, never a verified pass.
- Feature, bug, failing-test, and refactor tasks can be created and validated through the API.

### Commands Claude should run

```bash
rg -n "TaskSpec|taskbuilder|baseline|verify_command|error_log|scorer" backend benchmark
```

Add unit tests for baseline-pass, baseline-fail, not-reproducible bug, missing verification, and pre-existing failures.

---

## Task 4 — Ensure genuinely different, reproducible coding agents

### Work

1. Reuse `backend/agents_registry.py` and `agents/coding_agent.py`. Keep the existing ReAct agent as a baseline.
2. Verify the installed `inspect_ai` and optional `inspect-swe` versions and inspect their actual adapter APIs before changing calls. Do not guess function names or signatures.
3. Make the agent registry return structured agent specs with stable ID, display name, adapter kind, model/provider, configurable options, availability status, and a clear unavailable reason.
4. Support Claude Code, Codex CLI, and Gemini CLI only when the relevant adapter, CLI, credentials, and provider configuration are actually available. Never represent an unavailable agent as runnable.
5. Use the same task prompt, base commit, resource policy, timeout policy, and verification policy for every agent in a comparison.
6. Run each agent in an isolated workspace/container derived from the same immutable base commit. One agent must never read or modify another agent’s workspace.
7. Apply concurrency limits and per-agent timeouts. Capture timeout, crash, adapter failure, and provider errors as distinct outcomes.
8. Do not log secrets or pass provider credentials into the untrusted repository container unnecessarily. Follow the adapter’s documented host/proxy model and verify network isolation rather than assuming it works.
9. Make optional CLI-agent installation reproducible using the existing project configuration.

### Acceptance criteria

- `GET /api/agents` reports structured metadata and actual availability.
- An unavailable CLI is disabled in the UI with a clear reason.
- At least one configured agent completes an end-to-end evaluation.
- If credentials and supported CLIs are available, each configured adapter can run a smoke task; otherwise the corresponding agent is clearly reported as unconfigured rather than falsely marked successful.
- Each agent starts from the same recorded base commit and has a distinct isolated workspace.
- One agent’s file changes cannot leak into another agent’s run.
- Timeout and process failures are recorded without crashing the API server.
- No provider credential appears in logs, database records, frontend responses, or task prompts.

### Commands Claude should run

```bash
python --version
python -m pip show inspect-ai inspect-swe
```

Use the active environment's package manager if it is `uv` rather than `pip`. Inspect installed package documentation/source and CLI help before implementing or testing adapters. Do not invoke paid model calls until the user has configured credentials and explicitly enabled a smoke test.

---

## Task 5 — Make orchestration durable and safe

### Work

1. Trace `backend/main.py` → `backend/runner.py` → `backend/worker.py` → storage. Avoid long-running agent execution directly inside a request handler or the Uvicorn event loop.
2. Reuse the current worker/subprocess approach if sound; otherwise move execution into a supervised subprocess or worker process.
3. Ensure a server reload/restart does not corrupt stored evaluations. Persist queued/running/finished/error states and reconcile orphaned runs on startup.
4. Use bounded concurrency, task timeouts, process-group termination, and clear cancellation semantics.
5. Ensure each run has its own work directory, logs, patch artifact, and sandbox. Clean up temporary resources only after artifacts are safely stored.
6. Validate Docker image build and runtime behavior. Dependency installation may require network access during image build, but runtime agent containers should use the narrowest network permissions compatible with the agent adapter. Document the boundary.
7. Never run untrusted setup commands on the host. Do not mount host home directories, Docker sockets, SSH keys, or unrelated project directories into an agent container.
8. Add a configurable maximum repository size, run duration, output size, and concurrency cap where practical.

### Acceptance criteria

- Starting an evaluation returns a stable evaluation/run ID without waiting for the entire agent execution.
- API health/status endpoints remain responsive during a long-running evaluation.
- Every run reaches a terminal state (`passed`, `failed`, `errored`, `timed_out`, `cancelled`, or an equivalent documented state).
- A worker crash does not silently leave a run permanently “running”; startup reconciliation or a watchdog marks/retries it according to documented policy.
- Concurrent runs have separate workspaces and artifacts.
- Cancellation/timeout stops the relevant process and does not kill unrelated runs.
- Sandbox boundaries and any required network access are documented and covered by tests or explicit smoke checks.

### Commands Claude should run

```bash
rg -n "create_task|BackgroundTasks|subprocess|Popen|Semaphore|worker|timeout|cancel|docker" backend benchmark
```

Use a small local test repository for worker, timeout, cancellation, and concurrency tests. Do not use a valuable production repository for destructive tests.

---

## Task 6 — Capture reliable patches, transcripts, and metrics

### Work

1. Reuse `backend/transcript.py` and existing run schemas.
2. Capture the agent's patch and changed-file state before verification modifies the workspace. Include tracked and untracked files; `git diff` alone does not include untracked files.
3. Prefer a reproducible patch artifact plus a structured changed-file manifest. Handle binary files and oversized diffs explicitly.
4. Capture tool calls, failed tool calls, agent messages available through the adapter, final response, exit code, timestamps, and error/timeout details.
5. If the adapter exposes token usage and provider cost, persist the actual values. If cost must be estimated, record the pricing-table version and label the value as estimated.
6. Add or verify these metrics: wall-clock duration, tool-call count, failed tool-call count, files changed, additions, deletions, input/output tokens where available, cost where available, verification result, baseline comparison, and regression status.
7. Never use `0` to mean unknown. Use nullable fields plus a reason/source where necessary.
8. Avoid storing duplicate, unbounded logs in SQLite; use artifact files and store paths/metadata, with safe size limits and access controls.

### Acceptance criteria

- A run that creates, modifies, deletes, or adds files produces a patch/manifest that represents those changes accurately.
- Untracked files are included in the manifest and, where text-compatible, in the patch.
- Metrics match independently calculated values for a small known test patch.
- Missing token/cost data remains unknown and is not presented as a measured zero.
- Every metric has a documented source and unit.
- Patch and transcript artifacts remain available after the worker exits and are associated with the correct run.
- Sensitive values are redacted from logs where feasible.

### Commands Claude should run

```bash
rg -n "git diff|git status|model_usage|token|cost|tool_call|transcript|patch" backend benchmark agents
```

Add tests using a fixture repository that includes a new file, a modified file, a deleted file, and a failed tool call.

---

## Task 7 — Verify storage, API contracts, and dependency health

### Work

1. Inspect `backend/store.py` and confirm the actual implementation. If SQLite is already in use, verify transaction handling, schema initialization, indexes, and concurrent access instead of migrating again.
2. Ensure evaluations, runs, task specs, baseline results, agent specs, recommendations, votes, and artifact references persist across restarts.
3. Add migrations or versioned schema initialization if the database schema changes over time.
4. Validate all API inputs with Pydantic and return consistent error responses.
5. Check all frontend API methods against actual backend routes and response models. Fix mismatches at the correct boundary rather than adding unsafe frontend casts.
6. Ensure list endpoints are ordered and paginated or bounded; do not return arbitrarily large logs/diffs in dashboard responses.
7. Keep generated database/log/artifact files out of version control.

### Acceptance criteria

- Stored evaluations/runs survive a backend restart.
- Two concurrent run updates do not overwrite each other or corrupt the database.
- Invalid payloads return useful 4xx responses; unexpected server errors return safe 5xx responses.
- Every frontend API call maps to an implemented route with a matching request/response contract.
- Schema initialization works on a fresh database and a previously created database.
- Runtime data is not committed to Git.

### Commands Claude should run

```bash
rg -n "@app\\.|@router\\.|def .*evaluation|def .*run|def .*recommend|vote|sqlite|CREATE TABLE" backend
```

Then run the backend test suite and API contract tests using the project's documented environment.

---

## Task 8 — Complete the frontend workflow

### Work

1. Reuse the current React pages and components. Do not replace the design system or create duplicate pages.
2. Ensure `NewEvaluation.tsx` supports:
   - Repository URL and ref.
   - Repository profile preview.
   - Editable setup/build/test/lint/verification commands.
   - Task kind, description, and optional error/stack trace.
   - Multi-select agent selection.
   - Number of repetitions/epochs.
   - Concurrency/timeout settings only if the backend supports them.
3. Ensure `Evaluations.tsx` lists evaluations with repository, commit, task type, agents, state, and creation time.
4. Ensure `EvaluationDetail.tsx` presents the recommendation, ranking table, success and regression outcomes, confidence/sample-size warnings, median time/cost, and run links.
5. Use Recharts only where it improves interpretation. Label axes, units, and sample sizes. Do not imply a statistical certainty the data does not support.
6. Ensure `ComparePanel.tsx` compares patches from runs on the same evaluation/base commit and clearly indicates missing patches or failed runs.
7. Ensure `RunDetails.tsx` displays state, transcript/log availability, patch, verification details, errors, and metrics. If live logs are not implemented, say results refresh/persist after completion; do not claim fake live streaming.
8. Ensure `Dashboard.tsx` includes accurate totals, status counts, and per-agent breakdowns based on backend aggregates.
9. Add loading, empty, validation, unavailable-agent, API-error, timeout, and partial-results states.
10. Make layouts usable on narrow screens and ensure tables/diffs can scroll without breaking the page.

### Acceptance criteria

- A user can complete the entire workflow from repository URL to evaluation results without editing JSON or calling APIs manually.
- The UI prevents submission when required fields are invalid and explains why.
- The user can review/edit detected commands before execution.
- Evaluation and run states update accurately and stop polling when terminal.
- Comparison never mixes runs from different evaluations/base commits without an explicit warning.
- Recommendation rationale, sample size, unknown metrics, and failures are visible.
- No button is decorative or inert; all visible actions work or are disabled with a reason.
- `npm run build` succeeds with no TypeScript errors.

### Commands Claude should run

```bash
cd frontend
npm install
npm run build
```

Return to the repository root after frontend verification.

---

## Task 9 — Implement trustworthy recommendations and repeated trials

### Work

1. Reuse `backend/recommend.py` and the existing evaluation/recommendation schemas.
2. Aggregate results by agent, task kind, repository, and evaluation configuration.
3. Report verified success rate, regression rate, median duration, median measured/estimated cost, run count, and uncertainty/sample-size warnings.
4. Use a Wilson confidence interval for a binary success rate if the implementation is statistically correct and the denominator is clearly defined.
5. Use repeated trials/epochs only where the underlying runner guarantees independent isolated runs from the same base commit. Do not count retries as independent samples unless the policy explicitly defines them.
6. Add user-adjustable scoring weights only after the component metrics and normalization are documented. Validate weights and make the effect of changing them visible.
7. If a composite score is used, disclose its formula and inputs. Do not rank an agent on cost/speed when its correctness evidence is insufficient.
8. Add a minimum-evidence policy. With too few verified runs, return “insufficient evidence” or “provisional recommendation” rather than an unjustified winner.
9. Treat unverified, timed-out, errored, and missing-metric outcomes consistently and document how each affects the ranking.

### Acceptance criteria

- Recommendations are computed from persisted run records, not frontend-only calculations.
- Results can be filtered/split by task kind and repository.
- The API includes agent name, verified run count, success rate, uncertainty interval, regression rate, median time, median cost where available, score/formula, and a rationale.
- Small samples produce an explicit low-confidence/insufficient-evidence warning.
- An agent with no verified successes cannot win solely because it is cheap or fast.
- Changing scoring weights changes the displayed score according to the documented formula, without changing raw measured metrics.
- Repeated trials use the same task/base commit and isolated workspaces.

### Commands Claude should run

```bash
rg -n "recommend|Wilson|median|successRate|regression|weight|epoch|repeat" backend benchmark frontend/src
```

Add deterministic unit tests for ranking, ties, zero runs, all failures, unknown cost, small sample sizes, and task-kind filtering.

---

## Task 10 — Add live progress only after correctness is stable

### Work

1. First determine whether the installed Inspect AI version exposes a suitable event/log hook for incremental transcript updates.
2. Prefer a documented event/hook API. If none fits, poll persisted partial run state or tail a supported log format safely.
3. Use Server-Sent Events only if it integrates cleanly with the existing FastAPI/frontend architecture; ordinary polling is acceptable for the MVP.
4. Ensure partial logs are appended incrementally and bounded in size.
5. Do not expose internal chain-of-thought. Show only user-facing assistant messages and tool events that the adapter permits, with secrets redacted.
6. Keep final patch capture and scoring independent of the streaming channel so dropped connections cannot change evaluation results.

### Acceptance criteria

- The UI shows truthful queued/running/completed/failed/timed-out states.
- If live progress is implemented, new events appear without a full page reload and reconnecting clients can resume from a cursor or safely reload recent events.
- Disconnecting the browser does not cancel the evaluation.
- Streaming failure does not affect run completion or stored results.
- No UI copy claims to show a live transcript unless events are actually persisted and delivered incrementally.
- Sensitive values are not emitted in event streams.

### Commands Claude should run

```bash
rg -n "StreamingResponse|EventSource|SSE|transcript|log|poll|inspect_ai" backend frontend/src
```

Use the installed Inspect AI documentation/source to confirm supported hooks before coding.

---

## Task 11 — Security, resource limits, and operational documentation

### Work

1. Review repository URL validation, Git command construction, shell invocation, path handling, archive extraction, and Docker arguments for injection/path traversal risks.
2. Pass subprocess arguments as argument arrays instead of interpolated shell strings wherever possible.
3. Enforce repository, output, log, timeout, disk, memory, and concurrency limits where supported.
4. Ensure container privileges are minimized; do not mount the host Docker socket or secrets. Document any unavoidable risk.
5. Add redaction for credentials in logs and safe handling of `.env` files.
6. Document supported operating systems, Docker requirements, environment variables, provider setup, optional CLI agents, data locations, cleanup, and known limitations.
7. Explain that repository image builds and dependency installers execute untrusted code and must be treated as a security boundary.

### Acceptance criteria

- Invalid URL/ref/path inputs cannot escape the configured cache or artifact directories.
- No subprocess command is built by unsafe string concatenation when arguments can be passed separately.
- Configurable limits are enforced or explicitly documented as unsupported.
- No secrets are included in frontend payloads, normal logs, or stored task data.
- A new developer can follow the README to configure and start the application.
- Known security limitations are explicitly documented; do not claim a sandbox is secure merely because it uses Docker.

### Commands Claude should run

```bash
rg -n "shell=True|os\\.system|subprocess|Popen|docker run|mount|env_file|\\.env|clone|extract" backend benchmark agents
```

Use existing lint/security tooling if configured. Do not install a new large security toolchain without a clear need.

---

## Task 12 — End-to-end validation and release checklist

### Work

1. Create/use a tiny local fixture repository with:
   - A known passing test suite.
   - A reproducible bug and verification command.
   - A feature task with an acceptance test.
   - A task that causes a regression.
   - A task that times out or returns an error.
2. Exercise the API/UI workflow from repository registration through recommendation.
3. Test one agent first. Test other agents only when their CLIs and credentials are configured and the user has approved any potentially billable smoke test.
4. Confirm that all runs use the same base commit and that patches/metrics match the actual workspace changes.
5. Test server restart recovery, concurrent evaluations, and unavailable-agent behavior.
6. Fix failures at their source and rerun the smallest relevant test before the full suite.
7. Do not push, deploy, publish, or open a PR unless the user explicitly asks.

### Acceptance criteria

- A new user can register a repository, inspect/edit the profile, create a task, select available agents, start an evaluation, and view the final results.
- Baseline results are recorded before agent execution.
- Each agent runs in isolation from the same base commit.
- Correct fixes pass verification; unchanged bugs do not pass merely because a command exits successfully at baseline; regressions are detected.
- Patch artifacts include new and modified files.
- API/UI display consistent evaluation states and stored results survive restart.
- Recommendation metrics are reproducible from stored records and disclose insufficient evidence.
- Backend tests pass, frontend TypeScript/build passes, and the end-to-end fixture workflow passes.
- Any tests not run, adapters not configured, or limitations are listed explicitly in the final report.

### Commands Claude should run

Start with repository-specific test commands discovered from the manifests and README. Typical checks, only if compatible with the active environment, are:

```bash
# From repository root
python -m compileall backend benchmark agents

# Run the configured backend test suite; use the project’s actual test command.
python -m pytest

# Frontend
cd frontend
npm install
npm run build
```

Do not assume `pytest` is installed or that tests are located in a conventional directory. Inspect the project first, then use the actual configured test commands. Run the full end-to-end fixture only after focused tests pass.

---

## Definition of Done

RepoBench is ready for an MVP release only when all of the following are true:

- [ ] Users can evaluate a Git repository and a feature/bug/refactor task through the UI.
- [ ] The exact repository commit and baseline state are stored.
- [ ] Multiple configured agents run independently from the same base commit.
- [ ] Verification distinguishes agent-caused fixes, regressions, pre-existing failures, and unverified results.
- [ ] Patches, logs, statuses, and available metrics persist and are retrievable.
- [ ] The dashboard, evaluation detail, run detail, and compare view reflect backend truth.
- [ ] Recommendations disclose sample size and uncertainty and do not overstate confidence.
- [ ] Frontend build and backend tests pass in the project's actual environment.
- [ ] Security boundaries, setup instructions, environment variables, and limitations are documented.
- [ ] No code has been pushed or deployed without explicit authorization.

## Execution Instructions for Claude Code

Work through tasks in order. At the start of each task:

1. Inspect the current implementation and tests.
2. State briefly which requirements are already satisfied and what is missing.
3. Make the smallest coherent changes; preserve unrelated user work.
4. Add or update tests for each behavior changed.
5. Run focused checks, then the relevant broader checks.
6. Report changed files, commands actually run, results, and anything blocked by missing credentials, dependencies, Docker, or external access.

Do not mark an acceptance criterion complete unless evidence supports it. Do not invent test results. Do not start a paid model call without explicit user authorization. Do not push, deploy, publish, or alter remote resources without explicit user authorization. If a requirement is ambiguous or would require a destructive action, stop and ask before proceeding.
