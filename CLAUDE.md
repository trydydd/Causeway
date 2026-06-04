# Causeway — Codebase Guide

Read PLANNING.md first. Every design decision has a numbered entry (D1–D32)
with a rationale. If you are about to change something that conflicts with a
decision, re-read that entry before proceeding.

---

## What this repository is

Phase 1 of the Causeway citizen-dev platform. It contains three tightly
coupled artefacts that prove the core agent loop:

1. **Schema** — `schema/causeway-manifest.schema.json` — the single source of
   truth for what a valid manifest looks like. Everything else derives from it.

2. **Validator** — `validator/` — a Python CLI (`cwy validate`) that reads a
   manifest and returns structured JSON output with meaningful exit codes.
   This is what an agent calls in its write→validate→fix loop.

3. **Scaffold** — `scaffold/` — a pre-filled `causeway.yaml` template that
   passes validation out of the box, plus `AGENTS.md` (the universal agent
   instruction file) and generated tool-specific rule files.

Phase 1 does **not** include container builds, CI/CD pipelines, auth proxy,
deployment, telemetry, or promotion machinery. Those are Phase 2+.

---

## Repository structure

```
schema/
  causeway-manifest.schema.json   ← THE source of truth — never generated
scaffold/
  causeway.yaml                   ← pre-filled template; must pass cwy validate
  AGENTS.md                       ← universal agent instructions — the source
  .cursorrules                    ← GENERATED from AGENTS.md (do not edit)
  .github/
    copilot-instructions.md       ← GENERATED from AGENTS.md (do not edit)
validator/
  pyproject.toml
  src/causeway/
    cli.py                        ← click entry point: `cwy validate`
    validate.py                   ← two-pass orchestration → ValidationResult
    classify.py                   ← policy checks → denied errors
    loader.py                     ← YAML parser
    schema.py                     ← loads bundled schema; Draft202012Validator
    data/
      causeway-manifest.schema.json  ← schema bundled with the package (copy)
docs/
  generate.py                     ← generates manifest-reference.md + rule files
  manifest-reference.md           ← GENERATED from schema (do not edit)
tests/
  fixtures/                       ← YAML files for each error class
  test_validate.py                ← pytest suite
.github/
  workflows/
    ci.yml                        ← four-job CI pipeline
```

### Generation dependency chain

```
schema/causeway-manifest.schema.json
  └─ docs/generate.py ──► docs/manifest-reference.md
scaffold/AGENTS.md
  └─ docs/generate.py ──► scaffold/.cursorrules
                      └─► scaffold/.github/copilot-instructions.md

schema/ ──► validator/src/causeway/data/  (manual copy — keep in sync)
```

**Never hand-edit a generated file.** Edit the source and run
`python docs/generate.py`.

---

## Key rules

- **Schema is source of truth.** Field names, enums, and constraints in the
  schema take precedence over anything else. If docs or validator logic
  disagrees with the schema, the schema wins and the other artefact must be
  updated.

- **Policy check types are a contract.** The distinction between `fixable`
  (schema/correctness) and `denied` (policy violation) is what determines
  whether an agent may auto-retry. Changing a check's type requires a new
  decision entry in PLANNING.md.

- **Exit codes are a contract.** 0 = valid, 1 = fixable only, 2 = at least
  one denied. Breaking this breaks agent self-correction loops. Do not change
  exit codes without updating PLANNING.md and all callers.

- **Generated files are enforced by CI.** `validate-generated-files` job runs
  `python docs/generate.py && git diff --exit-code`. A stale generated file
  fails CI.

- **Bundled schema must be kept in sync.** `validator/src/causeway/data/` is
  a copy of `schema/`. When you update `schema/causeway-manifest.schema.json`,
  also copy it to the data directory.

---

## Local development

```sh
# Install the validator in editable mode
pip install -e ./validator

# Validate a manifest
cwy validate causeway.yaml --json

# Run the test suite
pytest tests/ -v

# Regenerate docs and rule files
python docs/generate.py

# Verify generated files are up to date
python docs/generate.py && git diff --exit-code

# Validate the schema itself against Draft 2020-12
check-jsonschema --check-metaschema schema/causeway-manifest.schema.json
```

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

These are explicitly **not** in Phase 1 and should not be added until Phase 2+:

- Container image builds (Dockerfiles, build pipelines)
- Deployment commands or a `cwy deploy` subcommand
- Auth proxy or identity management
- Telemetry or load-bearing promotion logic
- MCP server tooling
- The `cwy promote`, `cwy contain`, or `cwy sunset` commands
- PyPI publication (manual step, performed by the repo owner)
