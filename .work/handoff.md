# Causeway — Agent Handoff

**Branch:** `claude/continuation-Ar2Qh`
**Phase:** Phase 1 complete (merged, PR #1). Phase 2 started — the **local dev
loop** is built and proven end-to-end.
**Last work:** Added `cwy build`/`run`/`up`/`down` — the platform builds a
container from the manifest and runs it on localhost (run-and-see). Decisions
D33–D37 in PLANNING.md.

---

## What exists now

**Phase 1 (write→validate→fix):**

1. `schema/causeway-manifest.schema.json` — Draft 2020-12 source of truth.
2. `validator/` — `cwy validate [PATH] [--json]`, two-pass (denied then fixable),
   exit 0/1/2, five policy checks.
3. `scaffold/` — `causeway.yaml`, `AGENTS.md`, generated `.cursorrules` +
   `copilot-instructions.md`.
4. `docs/generate.py` — idempotent generator (reference doc, rule files, bundled
   schema copy).

**Phase 2 slice 1 — project scaffolding + the local dev loop (NEW):**

4b. `cwy init [NAME]` (`scaffold.py`) — scaffolds a new project: `causeway.yaml`
   (name pre-filled) + `AGENTS.md` + `.cursorrules`, never app code (D37/D38).
   Scaffold files are bundled into `data/scaffold/` by `docs/generate.py` and
   loaded via importlib.resources (the installed CLI can't see repo `scaffold/`).
   Verified to ship in a built wheel. Removes the manual mkdir+copy friction the
   first dogfood run surfaced.

5. `validator/src/causeway/build/`
   - `dockerfile.py` — pure `render_dockerfile(manifest, has_deps)` + `BASE_IMAGES`
     (1:1 with the runtime enum). Golden-tested, no runtime needed.
   - `runner.py` — `docker`/`nerdctl` wrapper: runtime detection, ephemeral build
     context, run with port + `.causeway.env` injection, health poll, teardown.
6. `cli.py` — new subcommands `build` (+`--show-dockerfile`), `run`, `up`
   (+`-d`), `down`. Build is gated on `cwy validate` first (same 0/1/2 contract).
7. `tests/test_build.py` — 21 unit tests (renderer, gate, dry-run, runtime
   detection, env parsing) + 2 opt-in `@integration` tests (real build+run+curl).
   `tests/conftest.py` skips integration cleanly without a daemon.
   `tests/build_fixtures/{py-health,node-health}/` — tiny health-only apps, used
   only to smoke-test the loop (NOT user examples).
8. `pytest.ini` — registers the `integration` marker; default `-m "not
   integration"` so the suite is runtime-free by default.
9. `docs/getting-started.md` — build-your-own-app-in-Cursor walkthrough (the
   dogfood path).

**Proven:** both Python and Node fixtures build and run as real containers,
health-check green, and serve HTTP 200 (`pytest -m integration`). The sandbox
proof used a registry mirror (see gotchas #12) — irrelevant on a real machine.

---

## State of decisions

D1–D32 stand. Added:

- **D33** local dev loop is run-and-see, not deploy (no `cwy deploy`).
- **D34** platform renders the Dockerfile into an ephemeral context;
  `--show-dockerfile` for transparency.
- **D35** POC golden base images = official `-slim` tags, 1:1 with the runtime enum.
- **D36** local env via gitignored `.causeway.env`, injected at run time only.
- **D37** a Causeway project is just a directory; app authoring is unconstrained.
- **D38** `cwy init` scaffolds manifest + agent rules only (no app code), from a
  package-bundled scaffold; removes first-touch friction.

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
python docs/generate.py && git diff --exit-code

# Verify scaffolding:
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
- **Bundled scaffold vs canonical scaffold** must stay in lockstep —
  `test_bundled_scaffold_matches_canonical` + the generated-files CI job guard
  it. Edit `scaffold/`, then `python docs/generate.py`. `.cursorrules` is bundled
  as `cursorrules` (no dot) for package_data; init writes the dot back (gotchas #14).
- Integration tests are **not** in CI by design (daemon + registry pulls →
  nondeterministic). They are the local/dogfood proof.

---

## Key files to read first

1. `PLANNING.md` — decisions D1–D37. Read before changing anything.
2. `CLAUDE.md` — repo structure, rules, the local dev loop section.
3. `.work/gotchas.md` — non-obvious traps (#11–#13 are from this slice).
4. `docs/getting-started.md` — how a builder uses the paved road end-to-end.
