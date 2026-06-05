<!-- GENERATED — do not edit by hand. Run `python scripts/generate.py` to regenerate. -->

# Causeway Manifest Field Reference

Declares what an application needs; the platform compiles it into a container. This file is the consent surface — data scope and owner fields are shown to humans in plain language before deployment. Never declare infrastructure here; the platform handles containers, networking, and auth.

---

## `apiVersion` *(required)*

**Type:** `causeway/v1`

Schema version. Always set to 'causeway/v1'. Do not change this value — it pins the manifest to this schema version and enables safe schema evolution without breaking existing manifests.

**Examples:** `causeway/v1`

---

## `name` *(required)*

**Type:** string (pattern: `^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$`)

Unique application name. Must be lowercase letters, digits, and hyphens only — no uppercase, no underscores, no spaces. Used as the container image name and internal identifier. Length 3–40 characters. If validation rejects your name, remove uppercase letters, spaces, and underscores.

**Examples:** `expense-approvals`, `shift-planner`, `vendor-portal`, `stock-reconciler`

---

## `description` *(required)*

**Type:** string (min 20 chars, max 500 chars)

Plain-language description of what this application does, shown to the human reviewer as part of the consent surface. Write for a non-technical audience. Include what data it accesses and what business process it supports. This field is required to be meaningful — the reviewer uses it to understand data scope.

**Examples:** `Allows team leads to approve or reject expense reports submitted via the HR portal. Reads from the expenses database and sends approval notifications by email.`, `Generates a daily shift schedule for warehouse staff based on availability data from the HR system. Writes the final schedule to SharePoint.`

---

## `runtime` *(required)*

**Type:** `python3.11` | `python3.12` | `node20` | `node22`

The language runtime for this application. Choose the version your code targets. The platform uses this to select the correct golden base image — do not invent values outside this list. If your required version is missing, request it through the platform team rather than guessing an adjacent value.

**Examples:** `python3.12`, `node22`

---

## `entrypoint` *(required)*

**Type:** string (min 1 chars)

The command the platform runs to start your application inside the container. For Python apps using uvicorn: 'uvicorn main:app --host 0.0.0.0 --port 8080'. For plain Python: 'python app.py'. For Node: 'node server.js' or 'npm start'. Do not reference Dockerfile, docker-compose, or container configuration — the platform handles all of that.

**Examples:** `python app.py`, `uvicorn main:app --host 0.0.0.0 --port 8080`, `node server.js`, `npm start`

---

## `port` *(required)*

**Type:** integer (≥ 1024, ≤ 65535)

The TCP port your application listens on inside the container. Must be in the unprivileged range (1024–65535). The platform maps this to an external address — you do not choose the external port. Common choices: 8080, 3000, 5000. The value must match the port your entrypoint command binds to.

**Examples:** `8080`, `3000`, `5000`

---

## `healthEndpoint` *(required)*

**Type:** string (pattern: `^/`)

A URL path (starting with /) that the platform calls via HTTP GET to check if your application is healthy. Must return HTTP 200 when the application is ready to serve traffic. The path must start with /. Simple is better — '/health' returning JSON {"status": "ok"} is sufficient. The platform will not route traffic to your app until this endpoint returns 200.

**Examples:** `/health`, `/healthz`, `/api/health`, `/status`

---

## `tier` *(required)*

**Type:** `personal-team` | `business-process`

The blast-radius tier for this application, based on who is affected if it fails. 'personal-team': used by you and/or your immediate team; if it breaks, only you are affected. 'business-process': used across a business process; if it breaks, others outside your team are affected and work stops. Do NOT set this to 'load-bearing' — that tier does not exist in the manifest. Load-bearing status is determined by platform telemetry, not declared by the app author.

**Examples:** `personal-team`, `business-process`

---

## `dataSources` *(required)*

**Type:** array

All external data sources this application accesses. This is the consent surface — list every database, API, file store, or external service the application reads from or writes to. If the application accesses no external data, set this to an empty array []. The key must always be present. Omitting a data source is a policy violation — the human reviewer must be able to see the full data scope.

**Item fields:**

  #### `name` *(required)*
  **Type:** string (pattern: `^[a-z0-9][a-z0-9-]*[a-z0-9]$`)

  Internal reference name for this data source. Used in documentation and env var declarations. Lowercase letters, digits, and hyphens only.

  **Examples:** `expenses-db`, `hr-api`, `sharepoint-lists`, `email-relay`

  #### `type` *(required)*
  **Type:** `postgres` | `mysql` | `mssql` | `sqlite` | `rest-api` | `graphql` | `sharepoint` | `blob-storage` | `email` | `other`

  The type of data source. Use the most specific matching value. 'rest-api' covers any HTTP/HTTPS API. 'blob-storage' covers S3, Azure Blob, GCS, and similar object stores. Use 'other' only when no value fits and explain in the description field.

  **Examples:** `postgres`, `rest-api`, `sharepoint`

  #### `access` *(required)*
  **Type:** `read` | `read-write` | `write`

  The access mode this application uses against this data source. 'read': queries only, never modifies. 'read-write': both queries and modifies data. 'write': only appends or writes, never queries. Declare the minimum access your application actually needs — the human reviewer will compare this against the code's actual behaviour.

  **Examples:** `read`, `read-write`

  #### `description` *(required)*
  **Type:** string (min 10 chars)

  Plain-language description of what data this application accesses from this source and why. Shown to the human reviewer. Write for a non-technical audience — explain the business purpose, not the technical mechanism.

  **Examples:** `Reads approved expense records to generate the monthly summary report`, `Writes the finalised shift schedule for review by warehouse managers`

---

## `envVars` *(required)*

**Type:** array

Environment variables this application requires at runtime. Declare every variable the code reads from the environment. Do NOT put values here — only the variable name, a plain-language description, and whether it is required. Values are injected by the platform at runtime from a secrets manager. Putting a value here (e.g. DATABASE_URL=postgres://...) is a policy violation.

**Item fields:**

  #### `name` *(required)*
  **Type:** string (pattern: `^[A-Z][A-Z0-9_]*$`)

  Environment variable name. Must be UPPERCASE with underscores — the universal convention. Do not include a value or an equals sign. Examples: DATABASE_URL, API_KEY, SMTP_HOST. If your variable name contains lowercase letters, rename it to uppercase.

  **Examples:** `DATABASE_URL`, `API_KEY`, `SMTP_HOST`, `SHAREPOINT_TENANT_ID`

  #### `description` *(required)*
  **Type:** string (min 5 chars)

  What this variable contains and what it is used for. Helps the platform operator inject the correct value.

  **Examples:** `PostgreSQL connection string for the expenses database`, `API key for the HR system REST API`, `SMTP hostname for sending approval notification emails`

  #### `required` *(required)*
  **Type:** boolean

  true if the application will fail to start without this variable. false if the application has a safe fallback default and can run without it.

  **Examples:** `True`, `False`

---

## `owner` *(optional)*

**Type:** object

Required when tier is 'business-process'. Identifies the named human responsible for this application's behaviour, correctness attestation, and lifecycle decisions. This must be a person — not a team name, a role, or a distribution list. The named owner is contacted when telemetry triggers a forced decision (graduate / contain / sunset).

**Fields:**

  #### `name` *(required)*
  **Type:** string (min 2 chars)

  Full name of the named owner — the person who attests to this application's behavioural correctness and will be contacted at graduation-threshold events. Must be a person's name, not a team or role.

  **Examples:** `Jane Smith`, `Marcus Okonkwo`, `Priya Chandrasekaran`

  #### `email` *(required)*
  **Type:** string (format: email)

  Email address of the named owner. Used for forced-decision notifications — graduate, contain, or sunset. Must be a personal address that reaches the named owner directly.

  **Examples:** `jane.smith@company.com`

  #### `decommissionCriteria` *(required)*
  **Type:** string (min 20 chars)

  Plain-language description of when and how this application should be retired. Required to prevent apps from persisting past their useful life with no one responsible for them. Be specific — give a condition that can be evaluated objectively.

  **Examples:** `When the new ERP system's expense approval module is live and data has been migrated`, `When usage drops below 5 active users per month for 3 consecutive months`, `When the logistics team's migration to the supported vendor platform is complete`

  #### `graduationPath` *(required)*
  **Type:** string (min 20 chars)

  Named destination if telemetry signals this application has become load-bearing. Required at business-process tier so there is always an answer to 'what happens when this becomes critical'. The platform engineering team is the default graduation destination for apps that prove their value.

  **Examples:** `Hand off to the IT Operations team for formal support and SLA`, `Replace with a supported feature in the HR vendor platform and migrate data`, `Graduate to the platform engineering team for hardening and formal ownership`

---

## Conditional requirements

When `tier` is `business-process`, the following additional fields are required:

- `owner`

