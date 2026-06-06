# Causeway — Agent Handoff

**Branch:** `claude/continuation-Ar2Qh`
**Phase:** Phase 1 complete (merged, PR #1). Phase 2 started — the **local dev
loop** is built and proven end-to-end.
**Last work:** (1) Refactored agent rule files to be *derived* at `cwy init` from
one extensible registry instead of bundled (D39); the generator moved from
`docs/generate.py` to `scripts/generate.py`. (2) Rewrote the human-facing
`README.md` (status + quickstart + repo map). Decisions D33–D39 in PLANNING.md.

---

## What exists now

**Phase 1 (write→validate→fix):**

1. `schema/causeway-manifest.schema.json` — Draft 2020-12 source of truth.
2. `validator/` — `cwy validate [PATH] [--json]`, two-pass (denied then fixable),
   exit 0/1/2, five policy checks.
3. `scaffold/` — `causeway.yaml`, `AGENTS.md`, generated `.cursorrules` +
   `.github/copilot-instructions.md` (both derived from `AGENTS.md` via `rules.py`).
4. `scripts/generate.py` — idempotent generator (reference doc, repo rule files,
   bundled schema + scaffold sources). In `scripts/`, NOT `docs/` (no code in a
   docs dir); it imports `causeway.rules`, so CI installs the package first.
5. `causeway/rules.py` — the agent-rule registry (`RULE_FILES` + `render`): the
   single `AGENTS.md`→tool-rule-file transform, shared by `cwy init` and the
   generator (D39), so the repo's rule files and init's output can't drift.
   Adding a host (Windsurf, Cline, …) is one `RuleFile` entry.

**Phase 2 slice 1 — project scaffolding + the local dev loop:**

6. `cwy init [NAME]` (`scaffold.py`) — scaffolds a new project: writes the two
   bundled sources (`causeway.yaml` name-prefilled, `AGENTS.md`), then **derives**
   `.cursorrules` + `.github/copilot-instructions.md` from the bundled `AGENTS.md`
   via `rules.py`. Never app code (D37/D38/D39). Only the two sources are bundled
   into `data/scaffold/`; rule files are derived. Verified to ship in a built
   wheel. Removes the manual mkdir+copy friction the first dogfood run surfaced.
7. `validator/src/causeway/build/`
   - `dockerfile.py` — pure `render_dockerfile(manifest, has_deps)` + `BASE_IMAGES`
     (1:1 with the runtime enum). Golden-tested, no runtime needed.
   - `runner.py` — `docker`/`nerdctl` wrapper: runtime detection, ephemeral build
     context, run with port + `.causeway.env` injection, health poll, teardown.
8. `cli.py` — subcommands `init`, `validate`, `build` (+`--show-dockerfile`),
   `run`, `up` (+`-d`), `down`. Build is gated on `cwy validate` first (0/1/2).
9. Tests: `test_build.py` (renderer/gate/dry-run/runtime/env + 2 opt-in
   `@integration`), `test_init.py` (init behaviour + bundled-source drift guard),
   `test_rules.py` (registry + transform), `test_validate.py`. `conftest.py` skips
   integration cleanly without a daemon; `tests/build_fixtures/{py,node}-health/`
   are smoke-test apps (NOT user examples). 63 unit tests green.
10. `pytest.ini` — `integration` marker; default `-m "not integration"`.
11. `docs/getting-started.md` — build-your-own-app walkthrough (dogfood path).
12. `README.md` — human-facing front door: what works today, quickstart, repo map.

**Proven:** both Python and Node fixtures build and run as real containers,
health-check green, and serve HTTP 200 (`pytest -m integration`). The sandbox
proof used a registry mirror (see gotchas #12) — irrelevant on a real machine.

---

## State of decisions

D1–D36 stand. Recent:

- **D37** a Causeway project is just a directory; app authoring is unconstrained.
- **D38** `cwy init` scaffolds manifest + agent rules only (no app code); removes
  first-touch friction.
- **D39** tool rule files are *derived* at init from one extensible registry
  (`rules.py`), not bundled; generator moved out of `docs/` into `scripts/`.

D12 note still applies (CLI is `cwy`).

---

## What is NOT done (still out — needs a planning decision)

- Deployment / `cwy deploy` (promotion stays in CI — D2, D13)
- Auth proxy / identity (off-localhost — D5/D6)
- Real secrets manager (local is `.causeway.env` only — D36)
- Telemetry / load-bearing promotion
- Platform-maintained image registry + digest pinning (D35 graduation step)
- MCP server; `cwy promote`/`contain`/`sunset`
- **PyPI publication** — owner (willard.hucks@gmail.com) does this manually.
  Package `causeway-platform`, entry point `cwy`. Do not automate.

---

## How to pick up work

```sh
git checkout claude/continuation-Ar2Qh
pip install -e ./validator pytest check-jsonschema

# Verify green (all should pass):
pytest tests/ -v                                    # unit suite (integration opt-out)
check-jsonschema --check-metaschema schema/causeway-manifest.schema.json
cwy validate scaffold/causeway.yaml --json
python scripts/generate.py && git diff --exit-code  # generated files not stale

# Verify scaffolding (init derives the rule files):
cwy init /tmp/demo-app && cwy validate /tmp/demo-app/causeway.yaml

# Verify the build loop (needs a running container runtime):
pytest tests/ -m integration -v
# or manually:
cwy up tests/build_fixtures/py-health -d && curl localhost:8080/health
cwy down tests/build_fixtures/py-health
```

---

## Open maintenance traps

- **`.gitignore` `build/` swallows the source package.** Re-included via
  `!validator/src/causeway/build/`. If new files under `build/` don't show in
  `git status`, that's why (gotchas #11).
- **Base-image map vs schema enum** must stay in lockstep —
  `test_base_image_map_covers_schema_runtimes` guards it.
- **Bundled scaffold SOURCES vs canonical scaffold** must stay in lockstep —
  `test_bundled_scaffold_matches_canonical` + the generated-files CI job guard it.
  Edit `scaffold/` (or the `rules.py` registry), then `python scripts/generate.py`.
  Only `causeway.yaml` + `AGENTS.md` are bundled now; rule files are derived
  (gotchas #14).
- **This sandbox's git origin is a fixed proxy path** authorized only for
  `trydydd/Causeway` (capital C). Do not "fix" the cosmetic `repository moved`
  notice by changing the URL — lowercasing or pointing at github.com directly
  breaks auth (gotchas #15). Push promptly and verify the remote: the container
  can rewind the local tree between turns; only pushed commits survive.
- Integration tests are **not** in CI by design (daemon + registry pulls →
  nondeterministic). They are the local/dogfood proof.

---

## Key files to read first

1. `PLANNING.md` — decisions D1–D39. Read before changing anything.
2. `CLAUDE.md` — repo structure, rules, the local dev loop section.
3. `.work/gotchas.md` — non-obvious traps (#11–#15).
4. `docs/getting-started.md` — how a builder uses the paved road end-to-end.
