# Causeway

A platform that lets non-developer business users turn AI-built prototypes into operable
internal products, and promotes them to higher tiers based on objective usage and impact data.
Run by one engineer, no support staff, against an unbounded number of projects — so the design
optimizes for *operability by people who didn't build it* and for *winning adoption against
existing shadow IT*, not for maximum capability.

> **Design source of truth:** [`PLANNING.md`](./PLANNING.md) holds the frame, first
> principles, and every decision with its rationale (D1–D39). Read it before changing anything.

---

## What works today

Causeway is built in deliberate, staged slices. What ships right now is the **author loop** —
everything a builder needs to go from an idea to a container running on their machine:

- **`cwy init`** — scaffold a new project (a manifest + agent rules, never app code).
- **`cwy validate`** — check a `causeway.yaml` against the schema and platform policy.
- **`cwy build` / `run` / `up` / `down`** — the platform builds a container from the manifest
  and runs it on localhost. **You never write a Dockerfile.**

Deployment, auth, telemetry, and promotion are intentionally **not** built yet — they are
sequenced later by design (see the Scope boundary in [`PLANNING.md`](./PLANNING.md)).

## Quickstart

```sh
# Prerequisites: Python 3.12+ and a container runtime (e.g. Rancher Desktop) running.
pip install -e ./validator          # install the `cwy` CLI from this repo
cwy --help                          # init, validate, build, run, up, down

cwy init my-app && cd my-app        # scaffold a project
# ...describe your app to your IDE agent; it fills in causeway.yaml and writes the code...
cwy up                              # build and run it on localhost; `cwy down` to stop
```

The full walkthrough — building a real app on the paved road with an IDE agent — is in
[`docs/getting-started.md`](./docs/getting-started.md). The manifest field reference is in
[`docs/manifest-reference.md`](./docs/manifest-reference.md).

## Repository map

| Path | What it is |
|------|------------|
| [`PLANNING.md`](./PLANNING.md) | Design source of truth: principles + decision log |
| [`schema/`](./schema) | The manifest JSON Schema — the contract everything generates from |
| [`validator/`](./validator) | The `cwy` CLI: validate, init, and the local dev loop |
| [`scaffold/`](./scaffold) | The project template `cwy init` lays down (`causeway.yaml` + agent rules) |
| [`docs/`](./docs) | Getting-started walkthrough + generated manifest reference |
| [`CLAUDE.md`](./CLAUDE.md) | Contributor / agent guide: how the repo is wired and the rules that hold it together |
