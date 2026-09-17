"""RepoBench API: a thin FastAPI connection layer over the existing
evaluation framework (agents/, benchmark/, evals/).

It doesn't reimplement any evaluation logic -- it just:
  - lists the tasks already defined in benchmark/tasks/*.yaml
  - lists the models available to run (REPOBENCH_MODELS env var)
  - launches real inspect_ai evaluations (evals.repobench.repobench) in the
    background and tracks their status
  - turns a finished run's inspect_ai EvalLog into the plain JSON shape the
    React frontend renders (see frontend/src/lib/api.ts)

See backend/README.md for how to run this alongside the frontend.
"""

from __future__ import annotations

import sys
from pathlib import Path

# agents/, benchmark/, and evals/ are plain top-level packages, not an
# installed distribution -- evals/repobench.py does the same sys.path
# bootstrap for itself. We do it here too so `backend` is importable (and
# in turn can import `evals`/`benchmark`) no matter how uvicorn is invoked
# (`uvicorn backend.main:app`, a console script, a different cwd, etc).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
