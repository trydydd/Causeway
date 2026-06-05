# Causeway — Claude Code Guide

**Source code is the truth. If you have not read it, it does not exist — docs lie, memory lies, only the file is real.**

**Starting a new session? Read `.work/handoff.md` first.** It contains the
current state of the repo, what was built last, open maintenance traps, and
the exact commands to verify the environment is clean before touching anything.

**Read PLANNING.md second.** Every design decision has a numbered entry (D1–D32)
with a rationale. Conflicts with those decisions need a new decision entry, not
a unilateral change.

---

## Quick orientation

Phase 1 is complete. The repo contains a working JSON Schema, a CLI validator
(`cwy validate`), a scaffold template, tests, and CI. Nothing else is built yet.
See `.work/handoff.md` for the full state summary.

```sh
pip install -e ./validator pytest check-jsonschema  # first time only

pytest tests/ -v                                    # run tests
cwy validate scaffold/causeway.yaml --json          # smoke test the CLI
python docs/generate.py                             # regenerate derived files
check-jsonschema --check-metaschema schema/causeway-manifest.schema.json
```

---

## Repo structure

```
schema/
  causeway-manifest.schema.json   ← THE source of truth. Never generated.

scaffold/
  causeway.yaml                   ← pre-filled template; must pass cwy validate
  AGENTS.md                       ← universal agent instructions; the source
  .cursorrules                    ← GENERATED — do not edit
  .github/
    copilot-instructions.md       ← GENERATED — do not edit

validator/
  pyproject.toml                  ← entry point: cwy = causeway.cli:main
  src/causeway/
    cli.py                        ← click group; cwy validate subcommand
    validate.py                   ← two-pass orchestration, FieldError, ValidationResult
    classify.py                   ← five policy checks → denied errors
    loader.py                     ← YAML parser (strips yaml-language-server header)
    schema.py                     ← loads bundled schema; Draft202012Validator
    data/
      causeway-manifest.schema.json  ← GENERATED verbatim copy of schema/ — do not edit

docs/
  generate.py                     ← run after changing schema or AGENTS.md
  manifest-reference.md           ← GENERATED — do not edit

tests/
  fixtures/                       ← YAML files; one per error class
  test_validate.py                ← 26 pytest cases

.github/
  workflows/ci.yml                ← four-job pipeline

.work/
  gotchas.md                      ← non-obvious traps discovered in Phase 1
  handoff.md                      ← state summary for the next agent
```

---

## Rules that must not be broken

**Schema is source of truth.** Field names, enums, constraints, and descriptions
in `schema/causeway-manifest.schema.json` take precedence over everything. If
docs or validator logic disagrees with the schema, fix the other thing.

**Bundled schema is generated, not hand-copied.**
`validator/src/causeway/data/causeway-manifest.schema.json` is a verbatim copy
of the canonical schema, emitted by `python docs/generate.py`. The installed
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
`python docs/generate.py && git diff --exit-code`. If you edit a generated file
by hand, CI will revert your change. Edit the source instead.

**Phase 1 scope is enforced by convention.** Nothing outside the current artefacts
(schema, validator, scaffold, tests, CI) should be added until Phase 2 planning
is done. See PLANNING.md and CLAUDE.md's "Phase 1 scope boundary" section.

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
3. Run `python docs/generate.py` — regenerates the reference doc AND the bundled
   schema copy at `validator/src/causeway/data/causeway-manifest.schema.json`.
4. Update fixtures if the change affects valid/invalid instances.
5. Run `pytest tests/ -v`.

## Changing AGENTS.md

1. Edit `scaffold/AGENTS.md`.
2. Run `python docs/generate.py` — this regenerates `.cursorrules` and
   `copilot-instructions.md`.
3. Commit all three files together.

---

## CI jobs

| Job | Depends on | What it checks |
|-----|-----------|----------------|
| `validate-schema` | — | Schema is valid Draft 2020-12 |
| `validate-generated-files` | — | Generated files are not stale |
| `test-validator` | `validate-schema` | `pytest tests/ -v` |
| `validate-scaffold-manifest` | `test-validator` | `cwy validate scaffold/causeway.yaml` exits 0 |

---

## Phase 1 scope boundary

These are **not** in Phase 1 and should not be added:

- Container image builds (Dockerfiles, build pipelines)
- Deployment commands or a `cwy deploy` subcommand
- Auth proxy or identity management
- Telemetry or load-bearing promotion logic
- MCP server tooling
- `cwy promote`, `cwy contain`, or `cwy sunset` commands
- PyPI publication (manual step by the repo owner — do not automate)
