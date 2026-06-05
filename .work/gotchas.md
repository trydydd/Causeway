# Causeway — Discovered Gotchas

Things that bit me during Phase 1 that aren't in the docs or would take a
competent engineer >15 minutes to diagnose.

---

## 1. jsonschema `if/then` errors report on the wrong field path

**Impact:** High — caused duplicate denied+fixable errors for the same field.

When a Draft 2020-12 `if/then` condition fires (e.g., `tier == business-process`
requires `owner`), jsonschema reports the `required` error from the `then` branch
with `error.absolute_path = deque([])` (empty — it's at root) and
`error.absolute_schema_path = deque(['then', 'required'])`.

If you naively turn the schema path into a field path you get `"then.required"`,
not `"owner"`. This means:

- Your denied-field deduplication set contains `"owner"`.
- The schema error path is `"then.required"`.
- They don't match, so the fixable schema error is NOT suppressed.
- The user sees both a `denied` and a `fixable` error for the same missing field.

**Fix:** For `required` validator errors, extract the missing property name from
`error.message` using a regex (`'([^']+)' is a required property`), not from
`error.absolute_path` or `error.absolute_schema_path`. This gives you `"owner"`
regardless of whether the error came from a top-level `required` or a `then.required`.

See `validator/src/causeway/validate.py::_jsonschema_path`.

---

## 2. `python -m package.cli` doesn't call `main()` without a `__main__` guard

**Impact:** Medium — tests pass with exit code 0 and empty stdout, silently.

When you run `python -m causeway.cli`, Python executes the module but a click
`@click.group()` decorated function is just a function definition — it doesn't
get called. Tests written as:

```python
subprocess.run([sys.executable, "-m", "causeway.cli", "validate", ...])
```

...return exit code 0 with empty stdout. This looks like a valid run but
`json.loads("")` raises, and if you swallow the exception you get a false pass.

**Fix:** Add `if __name__ == "__main__": main()` to `cli.py`, AND use the
installed entry point (`cwy`) in tests rather than the module invocation.
Both are needed: the guard for `python -m` usage, the entry point for tests
that reflect real user invocation.

---

## 3. `setuptools.backends.legacy:build` doesn't exist in common environments

**Impact:** High — `pip install -e` fails immediately.

The pyproject.toml build-backend `"setuptools.backends.legacy:build"` is a newer
setuptools API not present in Python 3.11 environments with setuptools < 68.3.
The error is:

```
ModuleNotFoundError: No module named 'setuptools.backends'
```

**Fix:** Use `"setuptools.build_meta"` — the stable, universal backend. It works
across all setuptools versions that support PEP 517.

---

## 4. `check-jsonschema --check-metaschema` does NOT validate `if/then` semantics

**Impact:** Medium — false confidence after schema validation.

The metaschema check only verifies that your schema is structurally valid JSON
Schema (i.e., it doesn't use unknown keywords). It does NOT check:

- Whether your `if/then` condition actually triggers correctly.
- Whether the `if` clause's `required: ["tier"]` guard prevents the condition
  from triggering when `tier` is absent.
- Whether enum values in `if.properties.tier.const` match your actual enum.

You have to test `if/then` with actual instance documents — bad instances that
should fail, and good instances that should pass. The metaschema check is
necessary but not sufficient.

---

## 5. jsonschema `iter_errors()` suppresses sub-schema errors for `if/then`

**Impact:** Medium — you may miss errors from the failing `then` branch.

For `if/then`, jsonschema reports errors from the failing `then` branch directly
in `iter_errors()` — they bubble up as top-level errors. This is correct but
surprising.

For `oneOf`/`anyOf`/`allOf` it's different: you get one top-level error
("... is not valid under any of the given schemas") and the per-branch errors
are in `error.context`. Iterating `iter_errors()` only gives you the top-level
error, not the specific field failures inside. You'd need to recurse into
`error.context` to get actionable messages.

We don't use `oneOf`/`anyOf`/`allOf` in this schema precisely to avoid this.
If you add them later, change the error-mapping logic.

---

## 6. The bundled schema used to be a manual copy — RESOLVED

**Status:** Fixed. Kept here because the underlying constraint still matters.

`validator/src/causeway/data/causeway-manifest.schema.json` must exist as a
copy because the installed package loads it via `importlib.resources`
(`schema.py`) and has no access to the repo's canonical `schema/` directory.
Loading from the repo root in dev-mode was rejected: it would make the editable
install behave differently from a PyPI install, masking exactly this bug.

It is now a **generated artifact**: `docs/generate.py` writes the canonical
schema text verbatim to the bundled path. Two guards prevent drift:
- `validate-generated-files` CI job (`python docs/generate.py && git diff
  --exit-code`) — fails the build if the committed copy is stale.
- `test_bundled_schema_matches_canonical` in `tests/test_validate.py` — fast
  local signal with a message pointing at `python docs/generate.py`.

If you ever change `schema.py`'s loading strategy, re-check that the bundled
copy is still what the *installed* package reads.

---

## 7. ruamel.yaml safe mode is YAML 1.2 — `yes`/`no` are NOT booleans

**Impact:** Low for this schema, high if schema gains boolean-like string fields.

PyYAML (YAML 1.1) treats `yes`, `no`, `on`, `off` as boolean `True`/`False`.
ruamel.yaml in safe mode (YAML 1.2) treats them as strings. This means
`required: yes` in a manifest would be parsed as the string `"yes"`, not `True`,
and would fail the `"type": "boolean"` schema check.

Not a current bug (we use `required: true` in all fixtures and docs), but if
anyone writes `required: yes` by habit, they'll get a confusing schema error.
The error message from jsonschema is `'yes' is not of type 'boolean'` — clear
enough, but the root cause (YAML version) is non-obvious.

---

## 8. `git diff --exit-code` in `validate-generated-files` CI job checks ALL files

**Impact:** Low — can produce confusing CI failure messages.

The CI job runs:
```sh
python docs/generate.py
git diff --exit-code
```

This checks ALL files in the working tree for modifications, not just the
generated ones. If a previous CI step modifies any file (unlikely in a clean
checkout, but possible if setup scripts touch files), this job fails for
unrelated reasons.

For stricter CI, scope the diff to the specific generated paths:
```sh
git diff --exit-code docs/manifest-reference.md \
  scaffold/.cursorrules \
  scaffold/.github/copilot-instructions.md
```

---

## 9. The `name` field regex requires minimum 3 characters, not 2

**Impact:** Low — UX surprise for short app names.

The pattern `^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$` enforces:
- First char: `[a-z0-9]` (1 char)
- Middle: `[a-z0-9-]{1,38}` (1–38 chars, no hyphens at edges)
- Last char: `[a-z0-9]` (1 char)

Minimum total: 3. A 2-character name like `"my"` fails silently (no middle
section). The schema description says "3–40 characters" but someone who tries
`name: hr` will get a pattern error without an obvious explanation.

If you ever want to allow 2-char names, the regex needs to change to:
`^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$` — but this allows single-char names
too and the edge cases multiply. Easier to just document the 3-char minimum
clearly.

---

## 10. Secret detection regex must anchor to avoid false positives on common words

**Impact:** Medium — false positive denied errors destroy trust in the tool.

The pattern `(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}` has a 20-character minimum
to avoid triggering on `"Bearer authentication"` or `"Bearer token format"` in
description text. Similarly, `(?i)password\s*=\s*\S+` requires an `=` sign —
matching `"password=secret"` but not `"set a password"`.

If you add new patterns, test them against all fixture YAML files and the
scaffold template description text. The most common failure mode is a
description field that contains a technical word that looks like a secret
prefix but isn't.

The false negative risk (missing a real secret) is higher than false positive
risk for this use case — an agent that embeds a secret and doesn't get caught
is worse than an agent that gets a false denied and asks the user. Err on the
side of flagging.

---

## 11. `.gitignore`'s `build/` silently swallows the `causeway.build` package

**Impact:** High — would ship a package that imports fine locally (editable
install) but is missing from the repo, breaking a fresh clone and CI.

The repo `.gitignore` has `build/` (the setuptools artifact convention), which
is **unanchored** — it matches a directory named `build` *anywhere*, including
the new source package `validator/src/causeway/build/`. After creating the
package, `git status` showed `cli.py` modified but none of the new `build/*.py`
files. They were invisible, not absent.

**Fix:** re-include the source package with a negation after the broad ignore:

```gitignore
build/
!validator/src/causeway/build/
```

A negation works here because no *parent* of the re-included dir is itself
ignored. Diagnose this class of problem with `git check-ignore -v <path>` — it
prints the exact `.gitignore` line and pattern doing the ignoring. Any future
directory literally named `build`, `dist`, etc. that is real source will hit the
same trap.

---

## 12. Docker Hub anonymous pull rate limits break builds on shared/CI IPs

**Impact:** High for verification — base-image pulls fail with `503 Service
Unavailable` or `You have reached your unauthenticated pull rate limit`, which
looks like a network outage but is rate-limiting on the shared egress IP.

In the build sandbox (and on busy CI runners) anonymous Docker Hub pulls of
`python:3.x-slim` / `node:x-slim` get throttled. The 503 first appears mid-layer,
so it masquerades as a flaky CDN. It is not the build loop failing — it is the
registry refusing the pull.

**Workaround for local/CI proof:** point the daemon at a pull-through mirror,
which does not touch the user's Dockerfiles (they still reference
`python:3.12-slim`):

```sh
dockerd --registry-mirror https://mirror.gcr.io      # Google's Docker Hub mirror
```

On a normal developer machine this does not arise — a single first pull caches
locally. This is purely a shared-IP artifact; do **not** "fix" it in the build
code. It is also exactly why integration tests are kept out of CI (see CLAUDE.md
"CI jobs").

---

## 13. Shell-form `CMD` triggers buildkit's `JSONArgsRecommended` warning

**Impact:** Low (cosmetic) but it is noise in the run-and-see output, which
erodes trust — a warning the builder didn't cause and can't act on.

The manifest `entrypoint` is a free-form shell command (`uvicorn main:app
--host 0.0.0.0 --port 8080`, `npm start`), so the obvious render is shell-form
`CMD uvicorn ...`. Buildkit warns that shell form doesn't forward OS signals
(JSONArgsRecommended).

**Fix:** render JSON exec form wrapping a shell, JSON-encoding the entrypoint so
quotes/specials are safe:

```python
lines.append(f'CMD ["sh", "-c", {json.dumps(entrypoint)}]')
```

This silences the warning while keeping shell semantics (args, `npm start`, etc.)
working verbatim. See `build/dockerfile.py`. Don't naively `.split()` the
entrypoint into exec-form args — that breaks any entrypoint relying on the shell.
