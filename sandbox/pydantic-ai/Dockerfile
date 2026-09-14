# Sandbox image for repository = pydantic-ai.
#
# Build context is repos/pydantic-ai (see compose.yaml) -- your local clone
# of https://github.com/pydantic/pydantic-ai, with FULL git history (not a
# shallow clone), since Sample.setup does `git checkout <base_commit>` for
# whatever commit a given task needs.
#
# Every dependency any current task needs is installed here, at *build*
# time, while we still have network access. This matters for two reasons:
#   1. Sample.setup then only needs to `git checkout` + relink editable
#      installs, which is fast and needs no network.
#   2. compose.yaml sets network_mode: none, so the agent's bash/python
#      tools have NO internet access during the episode. Without that, an
#      agent could just look up the real upstream fix on GitHub instead of
#      writing one -- pip installs are the only legitimate reason this
#      container should ever talk to the network, and that happens here,
#      at build time, before any sample (and before any agent) exists.
#
# Adding a task that needs a package not listed below? Add it to the RUN
# line and rebuild this image (`docker compose build` from this directory).
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY . /repo
WORKDIR /repo

# Union of every current task's setup.command dependencies (see
# benchmark/tasks/task_001.yaml and task_002.yaml). "pyparsing<3.1" pins
# around a real, verified issue: unpinned pyparsing>=3.1 pulls a
# setName-deprecation warning through vcrpy -> httplib2, which pydantic-ai's
# own filterwarnings=["error"] policy turns into a test collection error
# that has nothing to do with the task at hand.
RUN pip install --no-cache-dir \
        -e ./pydantic_graph \
        -e "./pydantic_ai_slim[realtime]" \
        pytest anyio inline-snapshot dirty-equals httpx asgi-lifespan \
        pytest-mock pytest-recording devtools "pyparsing<3.1"

ENV BLOCKBUSTER_ENABLED=false

CMD ["tail", "-f", "/dev/null"]
