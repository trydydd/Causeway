# Build a Causeway app in Cursor (or any IDE agent)

This is the **dogfood path**: build a real application on the Causeway paved road
using nothing but the platform's interface — the scaffold, the schema, the agent
rules, and the `cwy` CLI. The point is to find where the road has potholes. If
something is confusing, that *is* the finding; note it (see "Friction log" at the
bottom).

You author the manifest and the app code (via the agent). The platform builds the
container and runs it. **You never write a Dockerfile.**

---

## 0. Prerequisites (one time)

1. **A container runtime.** Install [Rancher Desktop](https://rancherdesktop.io)
   (free, no admin/WSL2 reconfiguration). Start it and wait until it is running.
   Verify:

   ```sh
   docker info     # should print server info, not an error
   ```

2. **The Causeway CLI.** From a clone of this repo:

   ```sh
   pip install -e ./validator
   cwy --help       # should list: validate, build, run, up, down
   ```

That is the entire install. Everything below is the loop you repeat.

---

## 1. Start a project

A Causeway project is just a directory. Scaffold one with a single command:

```sh
cwy init my-app
cd my-app
```

`cwy init` creates the directory and lays down the starting `causeway.yaml`
(with its `name` pre-filled from the directory) plus the agent rule files
(`AGENTS.md` and `.cursorrules`) so your IDE agent picks up the Causeway rules
automatically. It does **not** scaffold any application code — that stays a blank
slate for you and the agent. Run it inside an existing empty directory (`cwy init`
with no name) to scaffold in place; it never overwrites an existing manifest.

---

## 2. Let the agent build it

Open the directory in Cursor and prompt the agent in plain language. For example:

> Build a small expense tracker: a web app where I can add an expense (amount +
> description), see the list, and delete one. Store the data in a local SQLite
> file so it survives restarts. Follow the Causeway rules in AGENTS.md.

The agent should:

1. **Fill in `causeway.yaml`** — name, description, `runtime`, `entrypoint`,
   `port`, `healthEndpoint`, `tier`, and — importantly — declare the SQLite store
   in `dataSources` and any env vars in `envVars`.
2. **Write the application code** (e.g. `app.py` + `requirements.txt`). Two rules
   the run loop depends on, both in AGENTS.md:
   - bind to `0.0.0.0` on the `port` you declared (not `127.0.0.1`);
   - serve the `healthEndpoint` so it returns HTTP 200.

Write the app however you like — there is no required framework. The guardrails
live in the manifest, not in your code.

---

## 3. Validate

```sh
cwy validate causeway.yaml --json
```

- **Exit 0** — valid; go to the next step.
- **Exit 1** — fixable. The JSON lists each field and how to fix it. Hand it back
  to the agent (or fix it) and re-run.
- **Exit 2** — a policy violation (e.g. a hardcoded secret, or `tier:
  load-bearing`). Do **not** auto-retry; read the message and resolve it
  deliberately.

---

## 4. Run and see it

```sh
cwy up
```

This builds the container (the platform writes the Dockerfile), starts it, waits
for your health endpoint to go green, and prints a URL:

```
✓ my-app is healthy

→ http://localhost:8080
```

Open the URL and use the app. **This behavioural check is the real verification** —
not reading the code. Logs stream to your terminal; press Ctrl-C to stop and
remove the container.

Other commands:

```sh
cwy build --show-dockerfile   # inspect the Dockerfile the platform generates (read-only)
cwy up -d                     # run in the background; stop with `cwy down`
cwy down                      # stop and remove the container
```

### Local environment variables

If your app needs config (a connection string, an API key), declare the **name**
in `envVars` in the manifest, then put the local value in a `.causeway.env` file:

```sh
# .causeway.env  — local only; do NOT commit (it is gitignored)
DATABASE_URL=sqlite:///./local.db
```

`cwy up` injects these at run time. They never go into the image, and a value in
any committed file (including the manifest) is a denied policy violation.

---

## What this loop does *not* do (by design)

Local `cwy up` is for **seeing your app run on your machine**. It is not
deployment. There is no auth proxy, no shared hosting, no real secrets manager,
and no promotion here — those are off-localhost concerns handled by the platform's
CI gate, which is intentionally out of this slice. (See PLANNING.md D33–D37.)

---

## Friction log (the actual deliverable)

As you go, jot down every place the paved road made you stop and think:

- Did the agent try to write a Dockerfile or hardcode a secret anyway?
- Was a `cwy validate` error message unclear or unactionable?
- Did `cwy up` fail in a way that didn't tell you what to do next?
- Was anything about the project layout or the manifest surprising?
- Where did you have to fall back to knowledge outside the platform's guidance?

Each of these is a fix to the schema descriptions, `AGENTS.md`, or an error
message — the things that make the road wider for the next builder.
