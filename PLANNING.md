# Citizen-Dev Platform — Planning Source of Truth

> **This document is the source of truth. A conversation is a working session against it.**
> Start each new window by having the assistant read this and reflect back its understanding
> *before* any work. End each session by editing this doc while the reasoning is fresh.
> Edit it; do not append to it. A doc that only grows becomes the poisoned context it was meant to prevent.
> Carry forward **decisions and their why**, not the conversation that produced them.

---

## 1. Frame (read this first)

We are building a platform that lets non-developer business users turn AI-built prototypes
into operable internal products, and that promotes apps to higher tiers based on objective
usage/impact data. It is run by **one principal engineer with no additional support staff, permanently.**
The project count is **unbounded**. We are competing against **shadow IT that already works**
for the people using it, so adoption is the real problem, not capability.

**The immovable constraints (when anything conflicts, these win):**
- **No-staff is permanent.** Per-app human cost must trend to zero.
- **Adoption beats capability.** The paved road must be ergonomically better than shadow IT or it's ignored.
- A genuinely **load-bearing system with zero support staff is a structural mismatch** no process fixes;
  the platform needs an explicit ceiling and exit ramp, not the pretense everything can live here.

> Gravity well to resist: every technical conversation drifts toward "the most capable design."
> Check detailed work against **no-staff** and **adoption** before accepting it.

---

## 2. First Principles (verbatim — preserve wording)

### Foundational constraints
- No-staff is permanent, so per-app human cost must trend to zero; you scale by constraining the environment, not by inspecting each app.
- Project count is unbounded, so nothing in the design may assume a number you could personally keep in your head.
- You are competing with shadow IT that already works for its users; adoption is the real problem, not capability. The paved road must *win on ergonomics* or it gets ignored.
- A genuinely load-bearing system with zero support staff is a structural mismatch no process fully fixes — so the platform needs an explicit ceiling and exit ramp, not the pretense that everything can live here.

### Safety model (where trust actually sits)
- Safety lives in the platform, not in per-app cooperation or the agent's goodwill. Guarantees come from the gate, not from anyone getting it right.
- Sharp line between *guidance* (helps the agent get it right) and *enforcement* (guarantees wrong things don't ship). Never let guidance masquerade as enforcement.
- The author usually cannot vouch for AI-written code, so code-correctness review is relocated to the automated gate. The human reviews behavior and data scope; the platform reviews the code.
- Promotion stays gated through the CI/signing pipeline. No tool call, agent, or convenience path bypasses it.
- Separate *fixable* failures from *denied* (policy) failures. Automation may retry the first; it must never brute-force the second — that's your guardrail being attacked.

### Architecture (the technical spine)
- One OCI container image is the unit of compute; identical artifact local and deployed.
- "Same image" ≠ "same behavior" — parity is deliberate work on config interface, real backing services, and architecture (the repo+CI is the source of truth and builder, never the laptop).
- The platform owns the Dockerfile and golden base images so patching is central; users never author infrastructure.
- Auth lives at the edge via a forward-auth proxy against Okta; no app implements OIDC. Same proxy runs locally for parity.
- The container's *contract* (config in, port, health out) is identical across tiers even when the orchestrator differs, so deployment doesn't change behavior.
- Constrain the stack hard — narrowness is what makes whole-fleet reasoning and central maintenance possible.

### Interfaces (the three users: human, agent, platform)
- The manifest is the single surface where agent (author), platform (validator), and human (approver) meet.
- One schema is the single source of truth; docs, agent rules, and the validator all generate from it so they can't drift.
- "User doesn't write it" ≠ "user doesn't see it." Hide infrastructure; never hide data scope. The manifest is a consent surface, shown in plain language.
- The agent is a primary user — fast, fallible, unsupervised. Machine-consumability exists to tighten first-attempt accuracy and the self-correction loop. Error messages are an API consumed by a model.
- "Business user" is not one population. The front door is natural language in both cases — the personas differ by host environment: IDE-integrated agent (technical-enough, can install) and chat-native agent (non-technical builder, no install, lives in existing corporate tooling). Don't force either through the other's environment.
- The inference backend is swappable without loss of platform functionality. The scaffold, schema, rules, and validation CLI are the platform's interface to any agent — designed for the weakest capable backend, enhanced for stronger ones. No platform capability may depend on a specific agent host, IDE feature, or MCP client.
- The user's real verification is *behavioral* (run-and-see), not code review, so the dev loop must make run-and-see fast and obvious.

### Operations & lifecycle (what bites in 18 months)
- Instrument once: the same telemetry layer serves both operational monitoring and promotion data. Observable-by-default, or it won't happen.
- Usage data's primary job is the *risk alarm*, not the promotion ribbon — and they're the same signal. Crossing a threshold forces a decision (harden / contain / sunset), and "don't promote" is a valid outcome.
- Telemetry objectifies usage and health; it cannot objectify business impact (needs an owner declaration) and usage ≠ correctness (high-tier apps need real validation, not just green dashboards).
- Every promoted app has a named owner, a "what happens when they leave" answer, decommission criteria, and a registry entry. The inventory comes first — you can't manage what you can't see.
- Disposability is the maintenance and recovery strategy: scrap-and-rebuild a broken app, scrap-and-restart poisoned agent context. Cheap-to-kill beats cheap-to-fix when there's no one to do forensics.
- Every automated loop is an automated *spend* loop. Hard budget caps per-loop and per-project; cap exhaustion routes to the dead-end off-ramp.
- Design the dead end explicitly. A stuck user with no one to call must hit a detected, graceful off-ramp — never silent flailing, which sends them back to shadow IT.

### Adoption (the thing that decides if any of this matters)
- Launch with amnesty, not blame — you want disclosure of existing shadow IT, and blame kills disclosure.
- Sticks only work after the carrot is genuinely better; lock down alternatives too early and you drive it deeper underground.
- Treat the paved road's ergonomics as a product problem, continuously. Friction anywhere is an adoption leak.

### Meta-principle
- When two principles conflict in practice, the **foundational constraints win** (no-staff, adoption). Anything that quietly assumes more staff or more user patience than you have is the thing to cut, even when it's the more capable design.

---

## 3. Decisions Log (decision · why · rejected alternative)

| # | Decision | Why | Rejected alternative |
|---|----------|-----|----------------------|
| D1 | **Single OCI container image as the unit of compute**, identical local and deployed | "Deployment doesn't change behavior" requires the same artifact everywhere | Separate local/prod stacks; "works on my machine" risk |
| D2 | **Repo + CI is the source of truth and builder; the laptop never ships its image** | Apple Silicon is arm64, prod is amd64 — a locally-built artifact breaks in prod only; also enables scanning/signing | Promote the locally-built image |
| D3 | **Platform owns the Dockerfile and golden base images; users never author infra** | Central patching is what makes no-staff maintenance possible; AI-authored Dockerfiles are insecure/unpatched | Let the agent generate per-app Dockerfiles |
| D4 | **User-facing abstraction is a declarative manifest**, compiled into the container by the platform | Business users can't/shouldn't write infra; the manifest is also the human review + agent prompt surface | Expose Docker/compose directly |
| D5 | **Okta auth at the edge via forward-auth proxy** (oauth2-proxy/Pomerium pattern); no app implements OIDC | Token validation is security-critical and easy to botch; per-app auth is the complexity trap; SSO-for-free is an adoption carrot | Each app does its own OIDC |
| D6 | **Same proxy runs locally against an Okta dev tenant**; "dev auth" header-injection mode as a lower-friction fallback; a shared staging tier with the real proxy sits between laptop and prod | Local/prod parity for auth; header-injection doesn't exercise the real token flow so staging catches the gap | Auth only in prod |
| D7 | **Rancher Desktop** as the container runtime | Avoids Docker Desktop licensing cost and WSL2-admin requirements on locked-down corporate machines — both adoption blockers | Docker Desktop |
| D8 | **Bundle/smooth the runtime install via the platform CLI**; consider a hosted browser-based dev environment as a release valve | "Install a container runtime" defeats the least technical users; hosted dev is the *same artifact* in a third place, not a fork | Send users to configure WSL2 themselves |
| D9 | **One JSON Schema is the single source of truth**; docs, agent rules, and validator all generate from it | Hand-maintained parallel copies drift; a drifted rules file makes the agent emit invalid manifests | Separately maintained schema + AGENTS.md |
| D10 | **Manifest authored in YAML with `# yaml-language-server: $schema=` header**, enum-heavy, LLM-tuned `description`/`examples` | Schema descriptions and examples are the primary guidance mechanism for all agents regardless of host; the language-server header is an IDE-integrated enhancement (inline validation + autocomplete) that layers on top. Enums stop the agent inventing values; descriptions are what any model conditions on | Free-text-heavy schema; no editor integration |
| D11 | **Agent instruction files in the scaffold** (AGENTS.md + tool-specific rules) stated as *forbidden actions*; AGENTS.md is the universal layer; tool-specific rule files (.cursorrules etc.) are provider-specific enhancements generated from the same source — not the primary artefact | The agent's training data is saturated with the patterns we forbid (Dockerfiles, compose, hardcoded secrets); forbidding + a pre-filled scaffold makes the safe path the path of least resistance; keeping AGENTS.md universal ensures the rules apply regardless of inference backend | Rely on the agent's defaults; treat tool-specific rule files as the source of truth |
| D12 | **`platform validate --json` with structured errors + meaningful exit codes** | The agent's write→run→read-error→fix loop self-corrects well *only* with machine-readable, specific errors; error messages are an API consumed by a model | Human-oriented log output |
| D13 | **MCP server is an enhancement layer, read-and-validate-mostly; never a `deploy` tool** | Higher fidelity once the cheap path is proven, but a deploy tool is one a confused/injected agent can deploy *wrongly*; promotion stays gated through CI; also an extra install for the least technical | Give the agent a deploy tool; depend on MCP |
| D14 | **Code-correctness review is relocated to the automated gate**; the human reviews *behavior* (run-and-see) + *data scope* | Business users can't read a diff and judge correctness; making them do so makes them a rubber stamp | Expect the user to review code |
| D15 | **Manifest is shown to the human in plain language as a consent surface** (esp. data scope), even though the agent authors it | "User doesn't write it" ≠ "user doesn't see it"; data scope is a consent decision the human must make | Keep all bounds opaque/agent-only |
| D16 | **At least two front doors**: IDE for the technical-enough, a thinner surface for the rest | "Business user" isn't one population; forcing everyone through the IDE relocates support burden to "why is my screen full of red squiggles" | One IDE-only path |
| D17 | **Auto "retry with fresh context" as a first automated rescue for stuck loops**, bounded, terminating into the dead-end off-ramp | A stuck loop poisons context with its own failed attempts; a clean window discards the poison. Fixes *path-dependent* failures only | Let the agent keep digging; manual-only rescue |
| D18 | **Retry only *fixable* (correctness/capability) failures, never *denied* (policy) failures** | Auto-retrying a policy denial is a machine brute-forcing your own guardrail until something slips through | One undifferentiated retry path |
| D19 | **Subagent for a stuck step inside a healthy build; full fresh-window restart-from-scaffold when the whole app is in the hole** | Subagent's value is *context isolation* — parent keeps the durable plan, child thrashes in an isolated window and returns only a clean result or clean "I couldn't" | Always full restart; always same context |
| D20 | **Carry validated *facts* across any reset (goal, schema, scaffold, established constraints); never carry the failed *attempts/narrative*** | Re-injecting the failure transcript re-anchors the new agent on the framing that failed | Dump the transcript in to "help it learn" |
| D21 | **Vary something between retries** (decomposition, hint, model); **distinguish stuck from slow** via error-signature change | Identical dice → identical results; resetting an agent that's actually progressing throws away real ground | Blind identical retries |
| D22 | **Hard budget caps per-loop and per-project; cap exhaustion routes to the dead-end off-ramp** | Every automated retry is automated *spend*; a retry storm across many projects is runaway-shaped | Uncapped retries |
| D23 | **Tier apps by blast radius, not technical complexity** (personal/team · business-process · load-bearing); threshold-crossing is a *forced decision* (harden/contain/sunset) | Apps silently crossing into load-bearing without anyone deciding is the core danger; "don't promote" must be a valid, defensible outcome | Promote on impressiveness; complexity-based tiers |
| D24 | **Instrument once**: one telemetry layer serves both ops monitoring and promotion data, observable-by-default | If the user has to do anything to make an app observable, it won't happen; usage = the risk alarm and the promotion signal at once | Bolt analytics on later |
| D25 | **Launch with amnesty + an explicit invite to port existing shadow IT** | You want disclosure; blame kills disclosure; sticks only work after the carrot is genuinely better | Lock down alternatives first |
| D27 | **Two personas, both served by natural language interfaces in different host environments.** Technical-enough (can install): IDE-integrated agent (Cursor or equivalent). Non-technical builder (no install, lives in existing corporate tooling): chat-native agent (M365 Copilot web declarative agent or equivalent) with GitHub write capability via API plugin. Both doors share the same platform interface — scaffold, schema, rules, validation CLI. The inference backend is swappable (provider agnosticism). | These populations need different host environments, not different UX models. A step-by-step workflow or browser IDE is too heavy for the non-technical builder; a chat-only interface underserves the technical-enough user. | Single IDE-only door; hosted browser IDE as the thin door (same UX model, different install story — doesn't resolve the environment mismatch for chat-native users) |
| D26 | **Business-process is the platform ceiling; load-bearing is not a tier but the exit-ramp trigger.** Admission, trigger line, and enforcement are tier-specific (from D23). Personal/team: presumptive admission, no enforcement needed (blast radius contained). Business-process: declaration-driven crossing validated by telemetry, moderate enforcement (named owner + decommission criteria + registry entry required at intake). Load-bearing behaviour detected by telemetry: hard automatic containment — the platform structurally cannot sustain this tier with zero staff, so it does not offer it. The business-process→load-bearing trigger is telemetry-driven, not declaration-driven, because owners have incentive to avoid declaring the crossing. Specific telemetry signals and containment mechanics are implementation detail. | No-staff makes a genuine load-bearing tier structurally unsustainable; offering it defers the mismatch rather than resolving it. Tier-specific answers follow naturally from the blast-radius taxonomy already set in D23. | A unified threshold/enforcement mechanism across all tiers; a load-bearing tier with an internal threshold |

---

## 4. Open Questions / Live Tensions (do NOT let a fresh window quietly resolve these)

> These are the highest-value things in this doc. A new context will paper over them with a
> plausible default and resolve them in the wrong direction. Keep them open until *the owner* closes them.

- **OT3 — Logistics tooling specifically.** Almost certainly load-bearing; may not be appropriate for
  citizen-dev ownership at all. Decide its disposition explicitly rather than letting it drift into criticality.
- **OT4 — Correctness validation at high tiers.** Usage ≠ correctness; high-tier apps need *real* validation,
  not green dashboards. What that validation *is* (tests? human sign-off? domain checks?) is unspecified.
- **OT5 — Business-impact declaration.** Telemetry can't objectify impact; it needs an owner-declared
  statement. The *form* and *cadence* of that declaration is undecided. Risk: "promote on objective data"
  quietly becomes "we avoided the judgment call."
- **OT6 — Hosted dev environment.** Flagged as a release valve (D8) but not decided. It changes the
  install story materially for the least technical cohort. In or out?
- **OT7 — Stuck-vs-slow detection threshold.** D21 commits to the principle; the actual signal
  (how many unchanged error signatures = "stuck") is untuned.

---

## 5. Glossary (so terms don't quietly redefine across windows)

- **Paved road** — the sanctioned platform path; must be ergonomically better than shadow IT.
- **Manifest** — the short declarative file the agent authors and the human reviews; compiled into a
  container by the platform. The single surface where human, agent, and platform meet.
- **The gate** — the automated CI/signing pipeline that reviews code-correctness and enforces policy.
  Where safety actually lives. Nothing bypasses it.
- **Guidance vs enforcement** — guidance helps the agent get it right (advisory, in-IDE); enforcement
  guarantees wrong things don't ship (the gate). Guidance must never masquerade as enforcement.
- **Fixable vs denied failure** — fixable = correctness/capability (eligible for auto-retry);
  denied = policy (never auto-retried; that's attacking the guardrail).
- **Dead-end off-ramp** — the detected, graceful exit for a stuck user/agent with no one to call.
  Disposability (scrap-and-rebuild / scrap-and-restart), not debugging.
- **Forced decision** — when an app crosses a usage/blast-radius threshold, someone *must* choose:
  harden & promote, cap & contain, or sunset. "Don't promote" is valid.
- **Blast radius** — the basis for tiering: who/what breaks if this app fails. Not technical complexity.
- **Disposability** — the recovery and maintenance strategy: cheap-to-kill beats cheap-to-fix when
  there's no one to do forensics. Applies to apps *and* to poisoned agent context.

---

## 6. How to use this doc each session

1. **Open:** have the assistant read this doc and reflect back its understanding before any work.
   The read-back is your cheapest drift detector.
2. **Work** against it, not from memory.
3. **Close:** edit this doc while the reasoning is fresh — update decisions, move resolved tensions
   into the Decisions Log with their why, add new open questions. Edit; don't append.
