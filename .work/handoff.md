# Causeway — Agent Handoff

**Branch:** `claude/planning-alignment-ot1-atJlb`
**Phase:** 1 complete, pushed. Phase 2 not started.
**Last commit:** `d9692cd` — "Implement Phase 1: schema, validator (cwy validate), scaffold, and CI"

---

## What was built in this session

Phase 1 is the write→validate→fix loop proof-of-concept. All three artefacts
are present and working end-to-end:

1. **`schema/causeway-manifest.schema.json`** — Draft 2020-12 source of truth.
   All fields have LLM-tuned descriptions and examples. `if/then` enforces the
   `owner` block at `business-process` tier.

2. **`validator/`** — `pip install -e ./validator` → `cwy validate [PATH] [--json]`.
   Two-pass: schema validation (fixable) then policy checks (denied). Exit 0/1/2.
   Five policy checks: hardcoded secrets, load-bearing tier, dataSources omitted,
   envVar name contains value, owner missing at business-process tier.

3. **`scaffold/`** — `causeway.yaml` template (passes `cwy validate`), `AGENTS.md`
   (universal forbidden-action list + self-correction loop), generated
   `.cursorrules` and `copilot-instructions.md`.

4. **`docs/generate.py`** — idempotent generator. Run it after changing the
   schema or `AGENTS.md`. CI fails if generated files are stale.

5. **`tests/`** — 26 pytest cases. All pass. Coverage: happy paths, all fixable
   error classes, all five denied policy checks, file/parse errors, precedence,
   JSON contract.

6. **`.github/workflows/ci.yml`** — four jobs. Has not run on GitHub yet (push
   just happened — check Actions tab).

7. **`CLAUDE.md`** — codebase guide.

---

## State of decisions

All 32 decisions from PLANNING.md stand. One was updated:

- **D12 updated:** CLI is `cwy validate` (not `platform validate`) — avoids
  collision with other tools on corporate machines. The rationale and contract
  (structured JSON, exit codes) are unchanged.

---

## What is NOT done (Phase 2+)

See PLANNING.md and the "Phase 1 scope boundary" section of CLAUDE.md. Nothing
from this list should be started without reading the relevant planning decisions:

- Container image builds
- Deployment / `cwy deploy` subcommand
- Auth proxy
- Telemetry and load-bearing promotion
- MCP server
- `cwy promote`, `cwy contain`, `cwy sunset` commands
- **PyPI publication** — the owner (willard.hucks@gmail.com) handles this
  manually. The package name to register is `causeway-platform`. The entry
  point is `cwy`. Do not attempt to automate this.

---

## Open maintenance trap to address in Phase 2

The bundled schema at `validator/src/causeway/data/causeway-manifest.schema.json`
is a **manual copy** of `schema/causeway-manifest.schema.json`. There is no
automated check that they match. Every time the canonical schema is updated,
the copy must also be updated. Consider adding a test or making `schema.py`
load from the repo root in editable mode.

---

## How to pick up work

```sh
git checkout claude/planning-alignment-ot1-atJlb
pip install -e ./validator pytest check-jsonschema

# Verify everything is green
pytest tests/ -v
check-jsonschema --check-metaschema schema/causeway-manifest.schema.json
cwy validate scaffold/causeway.yaml --json
python docs/generate.py && git diff --exit-code
```

All four should succeed before making any changes.

---

## Key files to read first

1. `PLANNING.md` — decisions and rationale (D1–D32). Read before changing anything.
2. `CLAUDE.md` — repo structure, rules, and local dev commands.
3. `.work/gotchas.md` — non-obvious implementation traps discovered in Phase 1.
