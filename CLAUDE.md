# Causeway — Claude Code Guide

**Source code is the truth. If you have not read it, it does not exist — docs lie, memory lies, only the file is real.**

**Starting a new session? Read `.work/handoff.md` first.** It contains the
current state of the repo, what was built last, open maintenance traps, and
the exact commands to verify the environment is clean before touching anything.

**Read PLANNING.md second.** Every design decision has a numbered entry (D1–D39)
with a rationale. Conflicts with those decisions need a new decision entry, not
a unilateral change.

---

## Quick orientation

Phase 1 (write→validate→fix) is complete. The first Phase 2 slice — the **local
dev loop** (`cwy build`/`run`/`up`/`down`: the platform builds a container from
the manifest and runs it on localhost) — is built and proven end-to-end for the
Python and Node runtimes. See `.work/handoff.md` for the full state summary.

```sh
pip install -e ./validator pytest check-jsonschema  # first time only

pytest tests/ -v                                    # run tests (integration opt-out by default)
pytest tests/ -m integration -v                     # real build+run+health tests (needs a daemon)
cwy validate scaffold/causeway.yaml --json          # smoke test the validator
cwy up tests/build_fixtures/py-health -d            # smoke test the build loop; then `cwy down ...`
python scripts/generate.py                          # regenerate derived files
check-jsonschema --check-metaschema schema/causeway-manifest.schema.json
```

---

## Repo structure

```
schema/
  causeway-manifest.schema.json   ← THE source of truth. Never generated.

scaffold/
  causeway.yaml                   ← pre-filled template; must pass cwy validate
  AGENTS.md                       ← universal agent instructions; the source of the rules
  .cursorrules                    ← GENERATED from AGENTS.md (rules.py) — do not edit
  .github/
    copilot-instructions.md       ← GENERATED from AGENTS.md (rules.py) — do not edit

validator/
  pyproject.toml                  ← entry point: cwy = causeway.cli:main
  src/causeway/
    cli.py                        ← click group; validate + init + build/run/up/down
    validate.py                   ← two-pass orchestration, FieldError, ValidationResult
    classify.py                   ← five policy checks → denied errors
    loader.py                     ← YAML parser (strips yaml-language-server header)
    schema.py                     ← loads bundled schema; Draft202012Validator
    rules.py                      ← agent-rule registry: AGENTS.md → tool rule files (D39)
    scaffold.py                   ← cwy init: writes sources + derives rule files (D38/D39)
    build/                        ← local dev loop (Phase 2). NOTE: un-ignored in .gitignore
      dockerfile.py               ← pure Dockerfile renderer + base-image map (D34/D35)
      runner.py                   ← docker/nerdctl wrapper: build, run, health poll, teardown
    data/
      causeway-manifest.schema.json  ← GENERATED verbatim copy of schema/ — do not edit
      scaffold/                   ← GENERATED bundle for cwy init: SOURCES only
                                    (causeway.yaml, AGENTS.md) — do not edit; from scripts/generate.py

scripts/
  generate.py                     ← run after changing schema/AGENTS.md/scaffold (was docs/)

docs/
  manifest-reference.md           ← GENERATED — do not edit
  getting-started.md              ← build-your-own-app-in-Cursor walkthrough (hand-written)

tests/
  fixtures/                       ← YAML files; one per validate() error class
  build_fixtures/                 ← tiny health-only py/node apps; smoke-test the build loop
  test_validate.py                ← validator pytest cases
  test_build.py                   ← build-loop tests (unit + opt-in @integration)
  test_init.py                    ← cwy init + bundled-scaffold drift guard
  conftest.py                     ← docker_ready fixture (skips integration without a daemon)

pytest.ini                        ← integration marker; default addopts = -m "not integration"

.github/
  workflows/ci.yml                ← four-job pipeline

.work/
  gotchas.md                      ← non-obvious traps discovered while building
  handoff.md                      ← state summary for the next agent
```

---

## Rules that must not be broken

**Schema is source of truth.** Field names, enums, constraints, and descriptions
in `schema/causeway-manifest.schema.json` take precedence over everything. If
docs or validator logic disagrees with the schema, fix the other thing.

**Bundled schema is generated, not hand-copied.**
`validator/src/causeway/data/causeway-manifest.schema.json` is a verbatim copy
of the canonical schema, emitted by `python scripts/generate.py`. The installed
package loads it via `importlib.resources` (it can't see the repo's `schema/`).
Two guards stop it drifting: the `validate-generated-files` CI job and the
`test_bundled_schema_matches_canonical` test. Never edit it by hand — edit the
canonical schema and regenerate.

**Exit codes are an external contract.** 0 = valid, 1 = fixable only, 2 = at
least one denied. Agent self-correction loops depend on this. Do not change.

**`fixable` vs `denied` is an agent-loop decision, not a style choice.** Denied
errors block auto-retry (D18). Adding or changing a check's type requires a new
entry in PLANNING.md, not just a code change.

**Generated files are enforced by CI.** `validate-generated-files` runs
`python scripts/generate.py && git diff --exit-code`. If you edit a generated file
by hand, CI will revert your change. Edit the source instead.

**Scope is enforced by convention.** The build is deliberately staged. The local
dev loop is in; deploy/auth/telemetry/promotion are NOT (see "Scope boundary"
below and PLANNING.md). Adding anything from the boundary list needs a planning
decision first.

**The build package is un-ignored in `.gitignore`.** `causeway/build/` is real
source, but `.gitignore` ignores every `build/` dir (a setuptools artifact
convention). A `!validator/src/causeway/build/` negation re-includes it. If you
add a file under `build/` and `git status` doesn't show it, that's why — check
`git check-ignore -v <path>`. (See gotchas.md #11.)

---

## Validation architecture

Two-pass pipeline in `validate.py`:

```
Pass 1: classify.py → policy checks → denied FieldErrors
Pass 2: schema.py  → jsonschema    → fixable FieldErrors
                                      (fields already in denied set are skipped)
```

The key non-obvious detail: jsonschema's `if/then` errors report with
`absolute_path = deque([])`. For `required` validator errors, extract the
missing field name from `error.message` using a regex, not from the path.
See `.work/gotchas.md` for the full explanation.

---

## Adding a new policy check

1. Write the check function in `classify.py`. Return `list[FieldError]` with
   `type="denied"`. Add a comment explaining the policy reason.
2. Append the function to `ALL_CHECKS` at the bottom of `classify.py`.
3. Add a fixture file in `tests/fixtures/` and a test in `test_validate.py`
   that asserts exit code 2 and the expected denied field.
4. Add a decision entry in PLANNING.md (required — see rule above).

## Changing the schema

1. Edit `schema/causeway-manifest.schema.json`.
2. Run `check-jsonschema --check-metaschema schema/causeway-manifest.schema.json`.
3. Run `python scripts/generate.py` — regenerates the reference doc AND the bundled
   schema copy at `validator/src/causeway/data/causeway-manifest.schema.json`.
4. Update fixtures if the change affects valid/invalid instances.
5. Run `pytest tests/ -v`.

## Changing AGENTS.md or the scaffold manifest

1. Edit `scaffold/AGENTS.md` (or `scaffold/causeway.yaml`).
2. Run `python scripts/generate.py` — regenerates the repo's `.cursorrules` +
   `copilot-instructions.md` (derived from AGENTS.md via `rules.py`) AND the
   bundled `cwy init` sources under `validator/src/causeway/data/scaffold/`.
3. Commit the source and all generated files together. `test_init.py` and the
   `validate-generated-files` CI job fail if anything drifts.

## Adding an agent host (e.g. Windsurf, Cline)

Append one `RuleFile(path, label, preamble)` to `RULE_FILES` in
`validator/src/causeway/rules.py`, then run `python scripts/generate.py`. Both
the repo's `scaffold/` copy and what `cwy init` writes update from that one entry.

---

## Starting a project (`cwy init`)

`cwy init [NAME]` scaffolds a new project — `causeway.yaml` (name pre-filled) +
`AGENTS.md` + the tool rule files, never app code (D37/D38). Only the genuine
sources (`causeway.yaml`, `AGENTS.md`) are bundled into the package and loaded via
importlib.resources (the installed CLI can't see the repo's `scaffold/`, D9); the
rule files are **derived** from the bundled `AGENTS.md` via `rules.py` (D39), so
they match the repo's generated copies by construction. Logic is in `scaffold.py`;
it refuses to overwrite an existing manifest.

---

## The local dev loop (`cwy build`/`run`/`up`/`down`)

The run-and-see path (D33). The platform renders a Dockerfile per runtime family
into an **ephemeral** build context and builds it — the user's project never
contains a Dockerfile (D34). Architecture:

```
cli.py (build/run/up/down)
  └─ build/dockerfile.py  → render_dockerfile(manifest, has_deps)   # pure, golden-tested
  └─ build/runner.py      → detect_runtime → build_image → run_container
                            → wait_healthy → stream/stop            # docker/nerdctl CLI
```

- **Base images** are pinned `-slim` tags mapped 1:1 from the `runtime` enum
  (D35). `test_base_image_map_covers_schema_runtimes` fails if the map and the
  schema enum drift — keep them in lockstep.
- **Env injection** is local-only from a gitignored `.causeway.env` (D36); values
  are injected at `docker run` and never enter the image.
- **The renderer is pure** (manifest + `has_deps` → text), so it is unit-tested
  without a runtime. Anything touching the daemon is in `runner.py`.

Adding a runtime: extend the schema `runtime` enum first, then add the base image
to `BASE_IMAGES`, and (if a new language family) a branch in `render_dockerfile`
plus an entry in `DEPENDENCY_FILE`. Update the golden tests.

Integration tests (`@pytest.mark.integration`) build and run real containers;
they skip cleanly without a daemon (`docker_ready` fixture) and are opt-out by
default (`pytest.ini`). Run them with `pytest -m integration`.

---

## CI jobs

| Job | Depends on | What it checks |
|-----|-----------|----------------|
| `validate-schema` | — | Schema is valid Draft 2020-12 |
| `validate-generated-files` | — | Generated files are not stale |
| `test-validator` | `validate-schema` | `pytest tests/ -v` (validate + build **unit** tests; integration is opt-out) |
| `validate-scaffold-manifest` | `test-validator` | `cwy validate scaffold/causeway.yaml` exits 0 |

Integration build tests are intentionally **not** in CI: they need a daemon and
registry pulls, which would make CI nondeterministic (Docker Hub rate limits).
They are the local/dogfood proof. Run them on a machine with a runtime.

---

## Scope boundary

**In (built):** the validator (`cwy validate`), project scaffolding (`cwy init`),
and the local dev loop (`cwy build`/`run`/`up`/`down`).

**Out — do not add without a planning decision:**

- Deployment / a `cwy deploy` subcommand (promotion stays in CI — D2, D13)
- Auth proxy or identity management (off-localhost; D5/D6)
- Real secrets manager (local is `.causeway.env` only — D36)
- Telemetry or load-bearing promotion logic
- A platform-maintained image registry / digest pinning (D35 graduation step)
- MCP server tooling
- `cwy promote`, `cwy contain`, or `cwy sunset` commands
- PyPI publication (manual step by the repo owner — do not automate)
