---
name: sut-bootstrap
description: Portable system-under-test environment bootstrap. Use when a repo's SUT environment needs to be set up, verified, or diagnosed on this machine (toolchain, runtimes, services, and health — not account credentials or API keys) — "set up this repo so I can run it", "bootstrap my local environment", "is my machine ready to run this stack?", "install the tools this project needs", "connect me to the <env> environment" — or when another skill (e.g. agentic-e2e) needs the SUT ready before driving it. Discovers requirements from the repo's own manifests, closes tool/version gaps (user-space first, suggest-only for privileged), authenticates to remote targets, and verifies the environment is actually usable. Fully project-agnostic — every repo-specific fact is derived live from the repo's own files and cached per-machine, never hardcoded in this document or shipped beside it.
allowed-tools: Bash, Read, Grep, Glob, Write
---

# SUT Environment Bootstrap

This skill makes a chosen environment **actually usable** for running and testing this repo's
system-under-test (SUT): it discovers what the project needs to run, closes any
tool/version/dependency gap (installing the safe ones, *suggesting* the privileged ones),
authenticates to the target if one is needed, and confirms the environment is healthy. It is
independently useful ("get this repo runnable on my machine / connect me to dev") and is the
**required prerequisite** of the `agentic-e2e` skill, which drives the SUT this skill
readies.

**Portability contract — read this first.** This file must never contain a port number, a service
name, a URL, a repo-specific file path, or any other repo-specific fact. Every such fact is
**derived** from the repo's own files at run time and persisted to a per-machine cache (below) so
later runs don't re-pay the derivation. Porting this skill to a different repo means copying this
one file unchanged (plus its sibling `agentic-e2e` skill file, if the pipeline is wanted too) — or
installing the plugin that carries them — nothing else. If you find yourself wanting to hardcode
something repo-specific here, it belongs in the derived cache, not in this document.

**Footprint: this file, nothing else** — delivered either committed in the repo
(`.claude/skills/sut-bootstrap/SKILL.md`) or installed on the machine as a plugin from a
marketplace; the contract is identical in both modes. One optional hook exists: a `catalog.yaml`
at **`.claude/skills/sut-bootstrap/catalog.yaml` in the target repo — normally absent** — which, if
a team ever commits one, overrides this skill's derivation with human-promoted, OS-partitioned
entries for tools whose derived install/suggest proved wrong or dangerous on a specific OS, plus
cloud auth recipes. The catalog is always resolved at that **repo** path regardless of where this
skill file itself loads from — a plugin installation is per-machine and replaced on update, so
nothing team-owned may live inside it. No such file ships and none is required; a missing catalog
means pure derive-first, which is the normal case. This skill never creates or edits a catalog —
recurring cross-machine landmines are first fixed at their true source (a project PR), and only
promoted to a catalog by a deliberate human PR when no source fix exists.

**Runtime root — the per-machine cache (never committed, shared with the pipeline).** Everything
repo- or machine-specific lives under `<repo-root>/.codezen/agentic-e2e/`. The single
`.codezen/agentic-e2e/cache.yaml` is shared between this skill and `agentic-e2e`, with clear
ownership: **this skill owns** the machine facts (OS/arch, resolved tool paths), the requirement
set, the SUT recipe, and any remote-environment coordinates; **the pipeline owns** run-proven
landmines (`sut_facts`), optional scenario definitions, and healing settings. Each skill
spot-verifies and re-derives only the entries it owns; neither overwrites the other's. On first run
in a repo, create `.codezen/agentic-e2e/` and ensure the repo's `.gitignore` covers it (a single
`.codezen/` line); propose that one-line `.gitignore` addition as a normal visible edit if
missing — never commit cache output.

**Derive, then cache — the core discipline.** This skill reads no hand-written tool manifest and no
`install_policy`. It *derives* required tools + version constraints from the project's own files
(0a) and *derives* how to install each from the ecosystem it found — preferring a version manager
or a user-space install, proposed at the permission prompt (0c). This works for any stack
(Python/Node/Go/Rust/JVM/…) with nothing pre-written. What makes later runs fast is the cache:
after a successful derivation, persist what was derived **and proven live**. Cache honesty is
absolute — a cached fact must carry how it was proven (which file it was read from, or which run
demonstrated it); never cache a guess. On a cache hit, spot-verify the load-bearing facts cheaply
(the named module/paths still exist, the manifest values still agree) and re-derive only what
drifted, updating the cache. Every install and suggest is for the **detected OS** (established up
front in 0a); the skill never reads or emits another OS's instructions.

---

## Invocation

**Primary: a normal interactive Claude Code chat in the repo.** Auto-discovered from
`.claude/skills/`; a dev just asks — "set up this repo locally", "verify my machine is ready to run
the stack", "bootstrap the dev environment". All args are optional words in the sentence. It is
also invoked *by* `agentic-e2e` as its Stage 0 — same contract either way.

- `env`: which environment to make usable — `local` (default) or a named remote env (e.g. `dev`).
  For `local` the target is the repo's own bring-up/test recipe; for a remote env the target
  coordinates come from the invocation itself, the cache, or the repo's own deploy files/docs
  discovered in 0a (see Authentication).
- `mode`: `setup` (default) runs the full 0a→0d flow and closes gaps; `verify` is a **strictly
  read-only readiness audit** — detect everything, report the gap set and the outcome, mutate
  nothing (no installs, no logins, no bring-up side effects beyond read-only probes). `verify` is
  what a caller uses as a cheap preflight, and what a human uses to answer "is this box ready?".
- `install`: optional gate override. Default (unset) proposes each auto-installable tool as a real
  command — in an interactive session the human approves/rejects it at the permission prompt; run
  non-interactively without approval, a privileged command just fails safe. `install=suggest-only`
  forces the print-don't-run path for regulated/locked boxes.
- `config=<path>`: a hand-supplied file with the same schema as the cache — honored verbatim,
  useful for CI or a locked-down box. Wins over the cache.

**Outcome contract.** Every invocation ends in exactly one of these, stated explicitly, plus the
gap report (below) — this is the interface callers (human or the pipeline) consume:
- **READY** — the environment is verified usable for the requested `env`; the cache holds the
  proven facts. Never claim READY without 0d's live verification actually passing.
- **HALT-RESUMABLE** — a gap needs a human action (a privileged install, a rejected prompt, a
  login on a non-interactive box); the exact "do X, then re-run" instruction was printed. This is
  a **normal, successful outcome** — not a failure. The next invocation re-checks and continues
  from where the gap was.
- **FAILED** — the environment cannot be made ready and no human action was identified that would
  fix it (or verification found the SUT itself broken); the specific evidence is in the report.
Never a false READY: an unverified environment is HALT-RESUMABLE or FAILED, never quietly passed.

---

## Situations this skill must handle

The same 0a→0d flow below covers all of these — listed so none is improvised around:

- **Fresh machine (cold):** nothing installed, no cache. Full derivation; one consolidated gap
  pass (never one halt per tool); user-space installs proposed at the prompt; privileged ones
  suggested; ends READY or HALT-RESUMABLE with every remaining manual step listed.
- **Warm machine (cache hit):** spot-verify cached facts, re-probe presence cheaply, re-derive
  only drift. Should be fast and mutate nothing.
- **Wrong version present:** the constraint-satisfying version is obtained *alongside* the system
  one (version manager / user-space, run-scoped selection) — the system default is never touched.
  A singleton tool that can't coexist is suggest-only.
- **Partially provisioned box:** some tools present, some missing, some wrong-version — the gap
  report covers the full set in one pass, each with its own resolution.
- **Regulated / locked-down box:** `install=suggest-only` — nothing is executed that mutates the
  machine; every step is printed for the owner to run. `mode=verify` additionally skips logins.
- **Non-interactive (CI/headless):** no permission prompt exists — user-space installs may still
  run if the harness allows them; anything needing approval or privilege fails safe to a printed
  instruction + HALT-RESUMABLE. Never hang waiting for input.
- **Remote env, first time:** requirement set seeded with the target's cloud/orchestrator CLIs;
  interactive login in place (not a halt); active context/subscription verified against the
  intended target; coordinates discovered live, then cached.
- **Remote env, warm session:** session-check first — a valid session skips login entirely; still
  verify the context points at the intended target before READY.
- **Manifest drift since cache:** a cached fact failing its spot-verify (version bump in the
  manifest, moved module) is re-derived and the cache updated — never patched to match the cache.
- **Conflicting declarations:** two project files disagree on a version — surface the drift and
  HALT-RESUMABLE; do not silently pick one.
- **Install failure:** diagnose from the actual stderr and emit a specific remediation —
  never a blind retry, never silent repair of unrelated privileged system state (see 0c).

---

## 0a — Establish the host, then discover the requirement set

**First, establish the host OS + architecture:** `os` = lowercased `uname -s` (`linux`, `darwin`, …),
`arch` = `uname -m` (normalize to `x64`/`aarch64` where relevant). Record it in the stack note. Every
detect/install/suggest decision below is generated *for this OS/arch*; the skill never reads or emits
another OS's instructions (see the OS invariant at the end of this file).

Then read the project's own declarations to learn (i) the real shape of the system, (ii) exactly which
tools + versions running it requires, and (iii) how the repo itself exercises the system end-to-end
(its own `make test` / compose file / integration-test suite — the SUT recipe a caller like the
`agentic-e2e` skill will drive). The manifests *are* the source of truth — do not trust a
hand-written list:
- **Shape / bring-up / SUT recipe:** `docker-compose*.yml`, `Makefile`, `.github/workflows/`, the
  repo's own README/docs/CONVENTIONS, existing integration-test base classes → services, how the
  system comes up, how the repo's own tests boot and drive it, what a remote `env` deploys onto.
  Decide the **SUT kind** from what you find: a compose-style running stack (bring up + drive over
  HTTP/MCP), or an integration-test SUT (the test framework boots the app itself — drive its wired
  entrypoints). Record the exact run command, test-source location and visibility constraints, and
  where behavioral assertions read persisted state (tables/DDL) — these become the cached SUT recipe.
- **Tools + version constraints — read them from the build manifests:**
  - JVM: `pom.xml` `<java.version>` / `<maven.compiler.release>`, `build.gradle` `sourceCompatibility`,
    `.tool-versions`, `.sdkmanrc`
  - Node: `package.json` `engines.node`, `.nvmrc`, `.tool-versions`
  - Python: `pyproject.toml` / `setup.cfg` `python_requires`, `.python-version`
  - Containers: `docker compose` image tags, `Dockerfile` `FROM` tags, Testcontainers usage in the
    test tree (⇒ the run needs a Testcontainers-capable container runtime)
  - A compose file present ⇒ the run needs `docker` + `docker compose`; a `make` target in the
    bring-up recipe ⇒ needs `make`; and so on — infer the tool from what the recipe actually invokes.
- **Version binds to the SUT, not the repo.** In a monorepo with per-module versions, the required
  version depends on which module the SUT recipe targets — resolve it for *that* module, never a
  repo-global guess.
- **Disagreement ⇒ surface, don't guess.** If two declarations conflict (`pom.xml` says 21, a
  `.tool-versions` says 17), record the drift and HALT-RESUMABLE — do not silently pick one.

Produce a **requirement set** — `{tool → version-constraint (exact major / `>=N` / any), source file}`
— plus a short stack note. This derived set, not any hand-written block, is what 0b checks. For a
remote env, seed it with the target's "which cloud/orchestrator" requirements (e.g. `kubectl`,
`helm`, `az`) — taken from the invocation, the cache, or the repo's own deploy files/docs discovered
above; these aren't inferable the way a compose file implies docker, so if none of those sources
names them, ask rather than guess.

## 0b — Detect (present? which version?)

For each tool in the requirement set, **derive** its presence and version directly: `command -v <tool>`
for presence, the tool's standard version flag (`<tool> --version` / `java -version`, etc.) for the
installed major. A probe can be overridden by this machine's cache (e.g. a runtime a previous run
installed off-PATH into a user-space dir, which the bring-up resolver must agree with) or by an
optional catalog entry for the detected OS, where one exists. Partition into three states, never just
present/missing:
- **present-ok** — installed and version satisfies the constraint.
- **wrong-version** — installed but version outside the constraint.
- **absent** — not installed.

Never assume presence from a previous run — this run may be on a different machine, which is exactly
why the cache is per-machine and why a cached "present" still gets a cheap re-probe. Detect **all**
tools first, then act on the whole gap set at once (0c), so a fresh box gets one consolidated pass,
not one halt per tool. In `mode=verify`, stop after 0b + a read-only 0d probe: emit the gap report
and outcome without resolving anything.

## 0c — Resolve the gap (the safety gate)

The gate is **the permission layer itself**, not a config flag. Every install is a real command Claude
proposes; in an interactive session the human sees and approves/rejects it at the prompt — that approval
*is* "may this machine be mutated." The arg `install=suggest-only` forces the print-don't-run path.
Universal defaults regardless: **prefer user-space over `sudo`; never mutate the system's existing
default tool in place; never hang on an interactive `sudo` prompt** (`sudo -n true` first — if it would
prompt, fall to the suggest path).

**Derive the install.** Work the install out yourself from the ecosystem discovered in 0a, then
propose it at the gate — every stack (Python/Node/Go/Rust/JVM/…) has a standard install path:
- Prefer, in order: **a version manager already present** (pyenv/uv/nvm/sdkman/asdf) → **a user-space
  install** (a release binary into a `PATH` dir the user owns, or the tool's officially-published
  `curl … | sh`) → **the OS package manager**. Always the user-space / no-sudo option first.
- If an optional `catalog.yaml` exists at the repo's `.claude/skills/sut-bootstrap/` path (see
  Footprint), consult the **`catalog.<os>` block for the detected OS only** (never another OS's
  block) as an override: where an entry exists its `install`/`suggest`/`side_by_side` wins; where
  none exists (the normal case — usually no catalog exists at all), **derive**. Any suggest/halt instruction you emit is **generated live for the
  detected OS** — never a frozen string, never another OS's command (no `apt-get` on macOS, no
  `brew` on Linux).

**present-ok** → nothing to do.

**wrong-version** → obtain the *right* version alongside the existing one; never upgrade/downgrade the
system tool in place. In preference order:
1. **Already on the box elsewhere** — a matching version under a root the bring-up resolver scans
   (SDKMAN candidates, a user-space runtime dir, `/usr/lib/jvm`) → select it for this run only
   (run-scoped `*_HOME`/`PATH`), default untouched. (If the repo's own bring-up scripts have such a
   resolver, 0b's presence probe must agree with what it scans.)
2. **Version manager present** (pyenv/uv/nvm/sdkman/asdf) → install the correct version side-by-side via
   the manager, select it for the run only.
3. **No manager** → user-space install of the correct version into a run-scoped dir + point the run at it.
4. **A tool that can't coexist** (a singleton daemon/engine — you can't run two) → do **not**
   auto-swap; **suggest** the version change and HALT-RESUMABLE.
5. Can't obtain it (unsupported OS/arch, needs privilege) → HALT-RESUMABLE with the exact instruction.

**absent** →
- **Reversible / user-space** (a version manager or a user-space install path exists) → propose it at
  the gate. Ran → re-detect once → present? continue : diagnose (below).
  Rejected / `install=suggest-only` / no approval → print the manual step + HALT-RESUMABLE.
- **Privileged / off-box / a singleton daemon** (cloud login, cluster creds, a daemon needing `sudo` —
  the derivation lands on `sudo` with no user-space path) → print the exact command as a **suggest** +
  HALT-RESUMABLE.
- **No install path can be worked out at all** → emit a suggest naming the tool + its source file, and
  HALT-RESUMABLE.

**When an install fails, diagnose — don't loop or silently work around it.** Capture the actual stderr,
name the concrete cause, and emit a specific HALT-RESUMABLE remediation (e.g. "apt `update` failed on
repository X's corrupt/unsigned key — run `<exact fix>`, then re-run"), never a bare "install failed", a
blind retry, or an auto-repair of unrelated privileged system state (a broken third-party apt/yum repo,
a bad keyring, global config) that this task did not create. A failed install re-runs `detect` once to
confirm, then reports.

Always emit a **gap report**: present / installed-now / must-do-manually (with the exact command for
each). If this run had to diagnose and work around a landmine, route the learning to its right home:
a **machine-specific quirk** → this machine's cache; a **project defect** (e.g. a stale version pin
that breaks tooling on current systems) → flag the exact project fix in the report so it becomes a
normal PR to the repo — the workaround is cached, but the report must say the real fix belongs in the
project; a **genuinely cross-machine scar with no source fix** → describe it in the report, tagged
with the detected OS, as a candidate for a human-committed `catalog.yaml` — but **never create or
edit a catalog yourself**; promotion is a deliberate human PR.

### Authentication (remote targets only)

Authentication (only a remote target such as a cluster env; the `local` env never hits this) is
**interactive-first**. The *how* — the login/verify commands — is **derived** from the provider's own
standard CLI (an optional catalog's `auth_providers.<provider>` recipes override, where one exists);
the *target coordinates* (which subscription/cluster/namespace) come from the invocation, the cache,
or the repo's own deploy files/docs discovered in 0a — never from this file:
- Valid session already exists (the provider's session-check command) → skip login, continue.
- Interactive + not logged in → run the interactive login in place (browser or device code). This is
  **not** a halt: the human completes it and the run continues.
- Non-interactive + machine credentials present in env → use the provider's non-interactive login.
- Non-interactive + no credentials → print the exact login instruction and HALT-RESUMABLE.
- After login, **verify the active context/subscription matches the intended target** before continuing
  — an already-open session may point at the wrong account.
- **Discover deploy coordinates rather than freezing them.** A coordinate the target can tell you (a
  resource group, a cluster endpoint) is queried live post-login, never hardcoded anywhere.

Never embed a secret in this file or the cache — reference it by env-var name only.

## 0d — Verify ready

Confirm the environment is usable before claiming READY: for a local running-stack SUT, that the
bring-up recipe comes up healthy at its health check; for an integration-test SUT, that the
prerequisites its test bases need (a container runtime, a fallback database) are actually reachable;
for a remote env, that the context is reachable and the deployed service answers its ready signal.
If it cannot be made ready, stop and report the specific reason — never hand a caller a half-up
environment.

Also confirm the **test toolchain can actually reach the container runtime it needs** — a healthy SUT
is not enough if tests can't run against it. Two real, generalizable gaps to check/handle: (a) a
container client whose API version is too old for the installed engine (e.g. a project's pinned
Testcontainers/docker-java negotiating an API below the engine's documented minimum) — detect the
mismatch and **suggest bumping the client** rather than silently editing the SUT's build; (b) the
runtime socket not discoverable by that client. When a container-based test path is blocked this way
but a running deployment is reachable, record **driving the same contract over its real protocol
(HTTP/MCP) against the live SUT** as the equivalent, runtime-independent path in the stack note — so
a caller knows why the container path is unavailable and what to use instead.

**Cache write.** On a cold run (or after any drift-triggered re-derivation), persist the proven facts
to `.codezen/agentic-e2e/cache.yaml` now — the SUT recipe and requirement set with their source files, plus any
machine-specific resolutions (a run-scoped runtime path, a verified daemon setting) — each entry naming
its evidence. `mode=verify` writes nothing.

**Output:** the outcome (READY / HALT-RESUMABLE / FAILED), the stack note, the requirement set, and
the gap report — handed to whoever invoked this skill (a human, or the `agentic-e2e` skill
as its Stage 0).

---

## Non-negotiable invariants

- Never a false READY — READY requires 0d's live verification to have actually passed, with the
  evidence citable.
- `mode=verify` mutates nothing: no installs, no logins, no cache writes, only read-only probes.
- Never cache a guess. Every `.codezen/agentic-e2e/cache.yaml` entry this skill owns names its source (a
  repo file) or its proof (a live probe's actual output). A cached fact that fails its spot-verify
  is re-derived, not patched.
- Never commit the cache; never write outside `.codezen/agentic-e2e/` except the one-line `.gitignore`
  addition proposed on first run.
- Prefer user-space over `sudo`; never mutate the system's existing default tool in place; never
  hang on an interactive `sudo` prompt.
- Never create or edit a `catalog.yaml` — a project defect is flagged for a project PR, a
  machine-specific quirk lives in this machine's cache, and a genuinely unfixable cross-machine scar
  is only ever promoted to a catalog by a deliberate human PR.
- **OS invariant.** Establish the host OS first (0a, `uname`). Every install and every suggest you
  emit is for the **detected OS/arch**, generated live — never a frozen string, never another OS's
  command. If an optional catalog exists, read **only** its `catalog.<detected-os>` block; never read,
  merge, or emit another OS's block. A tool or OS with no catalog entry — the normal case — is
  **derived**, never an error.
