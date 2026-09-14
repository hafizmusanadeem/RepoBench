# Repos for evals

Each repository a task references needs a **full, local git clone** (not
shallow, not a tarball) here, named to match the task's `repository` field
and the `REPOSITORIES` mapping in `benchmark/dataset.py`:

```
repos/
  pydantic-ai/     <- your local clone of pydantic/pydantic-ai
```

Full history is required because `Sample.setup` runs `git checkout
<base_commit>` for whatever commit a given task pins, and different tasks
against the same repository pin different commits.

This directory is the Docker **build context** for the matching
`sandbox/<repository>/Dockerfile` (see `sandbox/pydantic-ai/compose.yaml`),
so:

- Don't add a `.dockerignore` here that excludes `.git` -- the sandbox needs
  it.
- If you already have the repo cloned elsewhere on your machine, either
  clone fresh here or symlink: `ln -s /path/to/your/pydantic-ai repos/pydantic-ai`.
- After updating the clone (e.g. `git fetch` to pick up a new base_commit
  you want to target), rebuild the image: `docker compose -f
  sandbox/pydantic-ai/compose.yaml build`.

To add a new repository: clone it here, add
`sandbox/<name>/{Dockerfile,compose.yaml}` (copy the pydantic-ai ones as a
starting point), and add an entry to `REPOSITORIES` in
`benchmark/dataset.py`.
