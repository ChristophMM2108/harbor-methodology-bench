---
name: agentic-e2e
description: Portable agentic end-to-end testing pipeline. Use when asked to E2E-test a change against the live system — a PR, a branch, a commit range, or uncommitted working-tree changes, of any type (bug fix, feature, refactor, perf optimization, docs/comments) — "test my PR end-to-end", "run agentic e2e", "verify this change/diff against the running stack", "check this PR for regressions", "test my uncommitted changes". Analyzes a diff (plus any linked ticket/PR context), classifies the change to select the right proof obligation, generates a targeted test, has an isolated auditor agent quality-gate it, executes it against a real local environment with a bounded healing loop, and reports mechanically-verified evidence. Fully project-agnostic — every repo-specific fact is derived live from the repo's own files and cached per-machine, never hardcoded in this document or shipped beside it.
allowed-tools: Bash, Read, Grep, Glob, Write
---

# Agentic E2E Testing Pipeline

This skill implements a 6-stage pipeline: **Analyze → Plan → Generate → Audit → Execute+heal → Report**.

**REQUIRED PREREQUISITE SKILL: `sut-bootstrap`.** Environment bootstrap — tool/version discovery
and installs, remote-target authentication, health verification — is that skill's whole job; this
pipeline invokes it as its Stage 0 and consumes its outcome (see Stage 0 below). This pipeline
never improvises its own bootstrap.

**Portability contract — read this first.** This file must never contain a port number, a service
name, a URL, a repo-specific file path, or any other repo-specific fact. Every such fact is
**derived** from the repo's own files at run time (by `sut-bootstrap`, and by Stage 1 here) and
persisted to a per-machine cache (below) so later runs don't re-pay the derivation. Porting this
skill to a different repo means copying two files unchanged — this one and the `sut-bootstrap`
skill file — or installing the plugin that carries them both; nothing else. If you find yourself
wanting to hardcode something repo-specific here, it belongs in the derived cache, not in this
document.

**Footprint: two skill files, nothing else.** The pipeline is this file plus its prerequisite
`sut-bootstrap` skill file, delivered either committed in the repo
(`.claude/skills/agentic-e2e/SKILL.md` + `.claude/skills/sut-bootstrap/SKILL.md`) or installed on
the machine as a plugin from a marketplace — the contract is identical in both modes. The optional
human-committed `catalog.yaml` override hook is always resolved **in the target repo** (never
inside a plugin installation, which is per-machine and replaced on update) and is documented in the
`sut-bootstrap` skill.

**Runtime root — the per-machine cache (never committed, shared with `sut-bootstrap`).**
Everything repo- or machine-specific lives under `<repo-root>/.codezen/agentic-e2e/`:
- `.codezen/agentic-e2e/cache.yaml` — the **derived knowledge cache**, shared between the two skills with
  clear ownership: `sut-bootstrap` owns the machine facts, requirement set, SUT recipe, and
  remote-env coordinates; **this pipeline owns** run-proven landmines (`sut_facts`), optional
  scenario definitions, and healing settings. Each skill spot-verifies and re-derives only the
  entries it owns; neither overwrites the other's. This is the ONE file the pipeline is allowed to
  write outside a run directory.
- `.codezen/agentic-e2e/runs/<run-id>/` — per-run evidence (logs, audit verdict, report) and generated test
  files (unless the cached SUT recipe requires generating into the app's own test tree — see Stage 3).
On first run in a repo, create `.codezen/agentic-e2e/` and ensure the repo's `.gitignore` covers it
(a single `.codezen/` line); propose that one-line `.gitignore` addition as a
normal visible edit if missing — never commit cache or run output. Cache honesty is absolute — a
cached fact must carry how it was proven (which file it was read from, or which run demonstrated
it); never cache a guess; on a cache hit, spot-verify the load-bearing facts cheaply and re-derive
only what drifted.

**Mechanical, falsifiable pass/fail — the core discipline.** The agent's own belief that something
works is never the gate. A green result only counts after the *same, unmodified* test has
demonstrably shown red — and what the red must look like depends on the change type, which Stage 1
classifies and Stage 5 enforces as the matching **proof form**: a fix or behavior change must fail
on `base` and pass on `head`; a behavior-preserving change (refactor, perf, cleanup) must pass on
*both* and show red under a deliberate, reverted perturbation; new behavior must pass on `head` and
show red under perturbation (fail-on-base is vacuous there — it fails for absence, not behavior); a
non-behavioral change (comments, docs, formatting) has nothing to gate and is reported as exactly
that, never forced through a pass/fail it cannot meaningfully take. Never report success on the
basis of the agent's summary alone — always cite the actual command output, HTTP status, database
row, or log line that proves it.

---

## Invocation

**Primary: a normal interactive Claude Code chat in the repo.** The skill is auto-discovered —
from the repo's `.claude/skills/` or from an installed plugin, whichever carries it; a dev just
asks — "run agentic e2e on my PR", "test this diff end-to-end, base=<sha> head=<sha>" — no paths
needed. All args are optional words in the sentence.

**Headless/CI variant** (same contract, non-interactive):

```
claude -p "Run the agentic-e2e pipeline (skill: agentic-e2e). \
Args: base=<sha> head=<sha> [ticket=<TICKET-ID>] [env=local|dev] [config=<path>]." \
  --output-format json
```

**Cache/config self-location.** Resolve the repo facts yourself — never ask for them unless
resolution is ambiguous: (1) an explicit `config=<path>` arg wins (a hand-supplied file with the
same schema as the cache — honored verbatim, useful for CI or a locked-down box); (2) else load
`.codezen/agentic-e2e/cache.yaml` when present, spot-verify its load-bearing facts, and re-derive only what
drifted; (3) else this is a first run on this machine — run fully derive-first (Stage 0/1 discover
everything from the repo's own manifests), **write the cache at the end of the run**, and say in the
report that this was a cold derivation. Load the resolved cache/config before anything else.

- `base` / `head`: a git ref range defining the diff to analyze. If omitted and the working tree is
  dirty, the diff is the **uncommitted work itself** — base = `HEAD`, head = a snapshot of the
  working tree (built without touching the developer's checkout — see Setup); nobody has to commit
  just to get tested. Announce that mode in one line before proceeding. If omitted and the tree is
  clean, default to `HEAD~1..HEAD`.
- `ticket`: optional — a linked issue/ticket ID (Linear, Jira, GitHub Issue, etc.) or a PR description
  string. When present, use it to understand *intent* ("what was this change trying to do"), not just
  *which lines changed* — the two are not the same thing and intent materially changes what a good
  test looks like (see Stage 1).
- `env`: which environment to bootstrap and test against — `local` (default) or a named remote env
  (e.g. `dev`). Forwarded to `sut-bootstrap`, which owns bring-up recipes, remote coordinates, and
  authentication. If omitted, use `local`.
- `install`: optional gate override, forwarded to `sut-bootstrap` (its default proposes each
  auto-installable tool at the permission prompt; `install=suggest-only` forces the
  print-don't-run path for regulated/locked boxes).
The same invocation shape is used whether a human runs this locally, CI runs it on a PR, or it runs
post-merge — only who supplies the ref range/ticket and where the facts come from differ. Never
branch on "am I in CI" inside this file; if CI needs different behavior (a lower healing cap, a
pinned config), that arrives via `config=<path>`, not here.

---

## Setup (before Stage 1)

1. Resolve the cache/config (above). From it (or from a cold derivation) you need: the SUT recipe
   (`sut`), any scenario definitions (`scenarios`, optional — with none, this run is purely
   diff-driven), the healing cap (`healing.max_iterations`, default 5), and the run directories
   (default `evidence_dir` = `.codezen/agentic-e2e/runs`, `generated_dir` = the run directory's `generated/`
   subdir unless the cached SUT recipe overrides it — see Stage 3).
2. Generate a `run-id` (a short unique string — timestamp-based is fine, but do not use a live clock
   call inside this skill's own reasoning; derive it from the invocation's own metadata or an
   incrementing counter file under `.codezen/agentic-e2e/.run-counter` if no run-id was supplied).
3. **If head is the uncommitted working tree** (see Invocation), first materialize it as a real
   commit-ish *without mutating the developer's checkout, index, or stash in any way*: build a
   synthetic commit through a temporary index — e.g.
   `GIT_INDEX_FILE=<tmpfile> git add -A && GIT_INDEX_FILE=<tmpfile> git write-tree`, then
   `git commit-tree <tree> -p HEAD -m "agentic-e2e snapshot"` — which captures tracked *and*
   untracked (non-ignored) files and leaves the developer's own index untouched. Use the resulting
   commit id as `<head-ref>` everywhere below, and record it in the report as the exact snapshot
   tested. Never `git stash push`, never `git checkout`/`git reset` in the developer's checkout,
   never ask them to commit first.
   Create an isolated git worktree for this run: `git worktree add .codezen/agentic-e2e-worktrees/<run-id> <head-ref>`.
   All work for this run — bring-up, test generation, execution, healing — happens inside that
   worktree, using its own compose project name (see Stage 5) so concurrent or sequential runs never
   collide on container/volume/network *names*. The worktree itself only isolates files — it does not
   by itself isolate host ports. If the SUT recipe's compose file binds fixed host ports (check its
   own docs/comments), true concurrent runs are still not supported; see the repo's own documented
   parallel-run limitation before assuming otherwise. Remove the worktree at the end of the run
   regardless of outcome (`git worktree remove`), unless the invocation explicitly asks to keep it
   for debugging.
   If the repo has submodules (a `.gitmodules` file at repo root), run
   `git submodule update --init --recursive` inside the new worktree path before any bring-up command
   executes — `git worktree add` does not populate submodule content by default, and a bring-up recipe
   that depends on a submodule's checked-out files will otherwise fail against an empty directory.
4. Do not spawn a nested orchestrator/container that itself launches a separate execution context for
   later stages. The Generate → Audit → Execute+heal loop for a given scenario stays inside one bounded
   context (one `claude -p` session, or one container invoking the environment's bring-up tooling) —
   never an orchestrator container spinning up its own separate inner container to do the same job.

---

## Stage 0 — Environment readiness (delegated to `sut-bootstrap`)

**Runs after Setup and before anything executes.** Default position is before Stage 1 — but when
Stage 1 can classify from the diff alone (it usually can), Stage 0 MAY be deferred until Stage 2 has
scheduled at least one executable scenario; a run that ends "nothing to test (non-behavioral)" then
skips bootstrap entirely, and its report must state that environment readiness was not verified this
run. This pipeline does not bootstrap environments itself —
it invokes the **`sut-bootstrap`** skill and consumes its outcome contract:

1. **Cheap preflight:** invoke `sut-bootstrap` with `mode=verify` (strictly read-only) for the
   requested `env`, forwarding the `install`/`config` args as given. On a warm cache this is a
   fast spot-verify that mutates nothing.
2. **Close gaps:** if the preflight reports gaps, run `sut-bootstrap` in its full `setup` mode —
   its permission-prompt gate, user-space-first installs, authentication flow, and health
   verification all apply exactly as specified in that skill. Already READY → nothing to do.
3. **Consume the outcome:**
   - **READY** → take the stack note, requirement set, SUT recipe, and gap report; continue to
     Stage 1 (and surface the gap report in the Stage 6 report).
   - **HALT-RESUMABLE** → halt this run, reprinting the bootstrap's exact "do X, then re-run"
     instruction. A halted bootstrap is a **normal, successful outcome** — not a failure of the
     pipeline, and never reported as a verdict about the change under test. The next invocation
     re-checks and continues from where the gap was.
   - **FAILED** → skip to Report with an **environment-failure** classification: name the specific
     environment cause with its evidence, and never let it masquerade as a test result for the
     change under test.
4. **If the `sut-bootstrap` skill is not available** — neither in this repo's `.claude/skills/`
   nor from an installed plugin — halt with the exact instruction to add it (one file beside this
   one in-repo, or the plugin that carries this pipeline carries it too). Never inline-improvise a
   bootstrap in its place — the derivation rules and safety gates live there.

### Remote environment runs (`env` other than `local`)

A named remote env (e.g. `dev`) is **head-only verification**, never the mechanical gate:

- **The mechanical proof gate — whichever form Stage 1 declared — always runs locally.** A shared
  remote runs one deployed image at a time — never deploy, relabel, or otherwise construct the
  `base` state or a perturbation on it. Run the proof-form legs in this run's local worktrees
  exactly as for `env=local`, then verify `head` against the remote.
- **Prove deployed == head before asserting anything.** Use evidence the target itself can give you
  (the registry's image digest, the deploy workflow's run logs for the head sha). If it cannot be
  proven, the report must say so and every remote claim is downgraded accordingly — never assume it.
- **Writes are consent-gated, scoped, and cleaned up.** Before any mutating call, list the exact
  fixtures to be created with their paired cleanup commands and wait for explicit approval. Every
  fixture this run creates, it deletes — cleanup is mandatory pass or fail, and shown in the report.
- **Report honestly.** Remote evidence is labeled **head-only verification on `<env>`** — it
  complements, never replaces, the local regression proof. The skill never deploys to or
  reconfigures a shared remote env; it tests what is already deployed there.

---

## Stage 1 — Analyze

**Input:** the diff between `base` and `head`, plus `ticket` if supplied.

1. Read the diff. Identify which files/functions/modules actually changed.
2. If `ticket` was supplied, read whatever context is available for it (a ticket description, a PR
   body, commit messages) to understand *intent* — what problem was this change trying to solve, not
   just what lines moved. A diff that flips a comparison operator reads very differently once you know
   it was meant to "add a 30-second refresh buffer" versus "fix an off-by-one."
3. Cross-reference the repo's own design docs (discovered during the `sut-bootstrap` derivation, or
   listed in the cache as `reference_docs`) for anything that describes expected behavior for the
   affected area, so generated tests assert against documented intent, not guesses.
4. **Classify the change and declare its expected delta — before anything is generated.** Tag each
   distinct claim the diff makes (a mixed diff gets one tag per claim, attached to its scenario —
   never one tag for the whole diff) as one of:
   - **fix / behavior-change** — `base` and `head` should observably differ. Declare the exact
     expected delta up front: which call, at which boundary, changes from what to what (status code,
     row value, error code, log line).
   - **refactor / perf** — behavior is *claimed preserved*; the expected delta is **none**, and that
     preservation claim is itself the thing under test. Declare the behavior that must hold on both
     sides, plus one concrete **perturbation** (a small, scoped breaking edit to the changed code)
     under which the test must go red — that is what will prove the test is a real instrument.
   - **new-behavior** — a surface that does not exist on `base` at all. Declare what `head` must
     observably do, plus a perturbation for the red story; fail-on-base proves nothing here (it
     fails for absence, not for behavior).
   - **non-behavioral** — comments, docs, formatting, renames with zero observable surface: nothing
     to test. Say so explicitly and skip to Report with a "nothing to test (non-behavioral)" result —
     don't force a scenario where none is warranted, and never manufacture a pass/fail for it.
   The declared type + expected delta go into the affected-surface note and select the Stage 5
   proof form. When genuinely unsure between refactor and behavior-change, prefer
   **fix / behavior-change** — the stricter form fails loudly rather than passing vacuously.
5. Produce an **affected-surface note**: which real, running endpoints/tables/flows this change could
   plausibly break, and a risk tag (e.g. security/credential-adjacent, data-integrity, routing,
   cosmetic). This note is per-diff — never a static, memorized list of routes. Check the cache's
   `sut_facts` (landmines previous runs proved) and account for any that intersect the affected
   surface.
6. If anything in the diff contradicts a documented contract or spec (e.g. code and doc disagree on a
   field name, an error code, a stage name), record that drift explicitly in the affected-surface
   note. Do not silently pick one source over the other — surface the disagreement so a human sees it
   in the final report.

**Output:** the affected-surface note, handed to Stage 2.

---

## Stage 2 — Plan

1. Take Stage 1's affected-surface note and produce a prioritized scenario list (P0/P1/P2). Security-,
   credential-, or auth-adjacent risk is always P0 regardless of how small the diff looks.
2. If the resolved cache/config lists fixed scenarios (`scenarios`, optional), schedule each of them
   as well — they encode invariants someone decided are worth standing coverage, run additively, and
   are never a substitute for the diff-driven scenarios from step 1. **With none listed — the normal
   case — the run is purely diff-driven**; do not invent a standing scenario that nobody asked for.
3. If Stage 1 found nothing testable and no fixed scenarios are listed, report "nothing to test."

**Output:** an ordered list of scenarios to generate, each tagged with its source (`diff-driven` or
`baseline`), its priority, and its declared change type + proof form from Stage 1 (a `baseline`
scenario is always fix-shaped: it must be demonstrably able to fail).

---

## Stage 3 — Generate

For each scheduled scenario, write one real, runnable, compilable test file — never prose, never a
description of a test, an actual file that a test runner can execute. Match the test style/framework
the repo itself uses — the cached SUT recipe names an example file (`test_style`) discovered during
the `sut-bootstrap` derivation — so generated tests look like something a human on this team would
have written, not a foreign convention.

Every repo file consulted during generation — entities/DDL, test base classes, helper fixtures,
conventions — is read **from this run's head worktree**, never from the developer's checkout: on an
explicit `base`/`head` range the checkout may sit on a different lineage entirely, and a test
generated against the wrong lineage fails to compile for reasons that say nothing about the change.

**Ground every assertion in real, observable state — never in a mock of the thing under test:**
- Drive the actual running system over its real interface — for a running-stack SUT that is its base
  URL over its real protocol (HTTP, MCP, etc.); for an integration-test SUT the test itself boots the
  app, so drive its wired entrypoints (an autowired facade, a TestRestTemplate). Either way, do not
  mock the component whose behavior is in question.
- Before asserting on persisted columns, read the actual DDL/entity the cached SUT recipe names for
  the real column names, types, and value formats (enum case, arrays, nullability) — never guess
  formats, and prefer correlating rows by the fixture's own identifiers over row counts or "latest
  row" when the table has other writers.
- When a diff touches a database write path, read the actual persisted row back via the mechanism the
  SUT recipe names (an in-test datasource query for an integration-test SUT, a DB helper for a
  running stack) rather than trusting an HTTP status code — a 200 only proves the call was accepted,
  not that what got stored is correct.
- For a diff-driven test specifically, deliberately construct the fixture at the *exact boundary* the
  diff introduced or touches (e.g. a value one unit before/after a threshold, a timestamp seconds from
  an expiry window) — a fixture that's comfortably far from the boundary will pass regardless of
  whether the diff's logic is right, which defeats the point of the test.
- For a fixed scenario (if the cache/config lists any), follow that scenario definition's own
  fixture/assertion contract exactly — these are meant to be stable across runs, not regenerated from
  scratch each time.

Every generated test file is written under `.codezen/agentic-e2e/runs/<run-id>/generated/` — **unless** the
cached SUT recipe records a `generated_test_path_override` (a derived, evidence-backed fact: e.g. an
integration-test SUT whose generated tests must live in the module's own test source tree to compile
against its test-scope dependencies and see its fixtures). An override target inside the app's source
tree is always throwaway-per-run: removed at teardown, never committed, and covered by the
`.gitignore` line the first run proposed. Do not write into a service's own source tree if the repo's
conventions forbid it (check for a root `CONVENTIONS.md` or equivalent before assuming it's safe).

**Output:** one or more generated test files, handed to Stage 4.

---

## Stage 4 — Audit

**This runs as a genuinely separate, context-isolated invocation** — in an interactive session, a
fresh-context subagent (the Agent/Task tool, no shared conversation history); headless, a fresh
`claude -p` process. Either way it must share no history with the agent that ran Stage 3.
**If no isolated context can be spawned at all**, the audit MAY run inline as a last resort, but then
`audit-verdict.json` and the Stage 6 report MUST both carry a first-class `audit_isolated: false`
flag with the reason — an inline audit is a weaker check and must never be presented as the
isolated one. It receives only:
- The scenario's contract (what it's supposed to prove — Stage 1/2's affected-surface note, priority,
  declared change type + expected delta, and the declared perturbation where the proof form has one;
  or the fixed scenario's own definition).
- The generated test file(s) themselves, **read from the run worktrees** — never the developer's
  checkout (same lineage rule as Stage 3).
- The cached SUT recipe's public surface (how tests run, where state is read — what each piece does,
  not Stage 3's reasoning) and any repo conventions relevant to test placement.

It explicitly does **not** receive Stage 3's reasoning/conversation — this is what makes "contract-only
access" real: the generator can't argue its way past the auditor by referencing context the auditor
never saw.

Checks to perform, and reject with a specific reason if any fail:
1. Does the test assert against a live response/state from the real running system, not a mock or a
   hardcoded expected value with no real call behind it?
2. For DB-backed assertions: does it read the real row via the real datasource/helper, not assume a
   value?
3. Does the test have a genuine red story for its declared proof form — for a fix/behavior-change
   scenario, an assertion that fails on `base`; for a refactor/perf or new-behavior scenario, an
   assertion that must fail under the scenario's declared perturbation — or is every assertion
   trivially true regardless of the system's behavior? Where the form has a perturbation, audit the
   perturbation too: it must break the *changed code* (never the test, never unrelated code) and be
   small enough that the test going red under it is attributable.
4. For diff-driven tests specifically: does the fixture actually sit at the boundary condition the
   diff touches, or is it a "safe," far-from-the-edge value that would pass either way?
5. Is the test hermetic — does it clean up any state it created (registrations, seeded rows) so
   repeated runs don't accumulate cross-run interference?

The audit is a **static review**: the auditor never executes tests, legs, or builds — Stage 5 owns
all execution. Anything an auditor executes anyway is discarded and never counts as gate evidence.

On `REJECT`, return the verdict and reason to Stage 3 as the *only* new input (not a shared history) —
Stage 3 revises the test in light of the verdict alone, without being able to relitigate what it
already argued. A revised test re-enters an **isolated** audit before Stage 5 — the same auditor
continued where the harness allows, else a fresh isolated one; when the revision is exactly the fix
the auditor itself prescribed, the fresh round may scope itself to verifying the prescription was
applied verbatim. If no isolated re-audit is possible at all, proceed only with
`reaudit_skipped: true` plus the reason recorded in `audit-verdict.json` and the report — a green
execution never substitutes for the audit. On `PASS`, proceed to Stage 5.

**Output:** a verdict (`PASS`/`REJECT` + reasons) written to `.codezen/agentic-e2e/runs/<run-id>/audit-verdict.json`.

---

## Stage 5 — Execute + heal

For each audited-and-passed test:

1. **Bring up the environment** using exactly the cached/derived SUT recipe — never a hand-rolled
   alternative. For a compose-style SUT, that is its bring-up command scoped to a per-run project name
   so this run's containers/volumes never collide with a developer's own environment or another run.
   For an integration-test SUT, the test framework boots the app itself — "bring-up" is only ensuring
   its prerequisites (e.g. the local database the tests fall back to when a container runtime is
   unavailable), per what the SUT recipe names.
2. **Run the scenario's declared proof form** (from Stage 1). Rules common to every form: every leg
   runs the *same, unmodified* test file — before accepting the final green, diff the test file
   against the version that produced the red; any change to the test itself between legs is invalid,
   reject rather than accept. A failure for an unrelated reason (connection refused, unrelated
   exception, timeout) is never gate evidence — return to Stage 4 as a rejected test, not a healing
   trigger. Base and perturbation states are only ever constructed in this run's isolated worktree,
   never in the developer's checkout.
   - **fix / behavior-change:** execute against `base` (or, if there is no real "pre-fix" commit —
     e.g. a from-scratch run against a fixed scenario — construct a deliberately reverted single
     change in the isolated worktree only). It **must fail with the specific, expected failure
     signature** declared in Stage 1 — a wrong status code, a missing/incorrect DB row, an
     unmediated direct call succeeding when it shouldn't. Then execute against `head`, unmodified:
     it must now pass.
   - **refactor / perf:** execute against `base` — it **must pass**. Green-on-base *is* the
     behavior-preservation claim under test; a red here means the change is not behavior-preserving
     after all — reclassify the scenario as fix/behavior-change, rerun under that form, and flag the
     mislabeling prominently in the report, never shrug it off. Execute against `head` — must pass.
     Then **calibrate the instrument**: apply the scenario's declared perturbation (Stage 1) to the
     changed code in the head worktree, run the test — it **must fail with the declared signature**;
     revert the perturbation and run once more — green again. The perturbation is what licenses the
     pass-on-both verdict (it proves this test *can* go red); it never evaluates the change itself,
     never touches the test file, and never outlives the run. A perf claim beyond "behavior
     preserved" (latency, throughput) counts as verified only if actually measured — otherwise
     report behavior-preservation only and say explicitly that the perf delta was not measured.
   - **new-behavior:** execute against `head` — must pass. Then the perturbation red leg exactly as
     above: red with the declared signature, revert, green again. The base behavior (the surface
     being absent — a 404, a compile error) MAY be shown as context, never as gate evidence.
3. **Healing.** If a leg that must pass does not, propose and apply a minimal fix, rebuild only the
   affected component(s), and retry — up to the healing cap (default 5), and always hard-capped below
   Claude Code's documented 8-consecutive-Stop-hook-block ceiling regardless of what any config says.
   A must-fail leg that stays green is never "healed" into failing — that is a rejected test; return
   it to Stage 4. Every iteration's logs/traces/evidence get written under
   `.codezen/agentic-e2e/runs/<run-id>/` — this is what makes iterating cheap: nothing here touches shared
   infrastructure, only this run's disposable environment.
4. **One narrow check when healing touched the run.** If healing fired (one or more iterations), do a
   single, deterministic re-execution of the final passing leg against a clean state (e.g. a fresh
   `down -v && up --build`, or fresh containers for an integration-test SUT) to rule out cached-state
   artifacts — one re-execution, not another agentic loop. If every leg landed on its expected
   outcome with zero healing iterations, skip it and record the skip in the report ("clean first
   pass — fresh-state re-run not required").
5. **Tear down** the environment for this run once all scenarios for this run have executed, whether
   they passed or not — for a running-stack SUT that is its down/destroy command; for an
   integration-test SUT it is removing the generated test files from the app's test tree and
   stopping any helper containers this run started.

**Output:** per-scenario pass/fail + full evidence trail, handed to Stage 6.

---

## Stage 6 — Report

Write `.codezen/agentic-e2e/runs/<run-id>/report.md`:

- One entry per scenario: id, source (`diff-driven`/`baseline`), the declared change type and the
  proof form that licensed the verdict (fail-on-base→pass-on-head; pass-on-both + perturbation red;
  pass-on-head + perturbation red; or "nothing to test (non-behavioral)"), pass/fail, iteration count
  if healing ran, and whether the fresh-state re-run happened or was skipped as a clean first pass.
- If `head` was an uncommitted working-tree snapshot, say so and cite the synthetic commit id from
  Setup — a reader must be able to tell exactly which state was tested, and that it was not a pushed
  ref.
- Real evidence for each — actual HTTP status, actual DB row JSON, actual log excerpt, not a summary
  of what supposedly happened. If it can't be shown, say so rather than asserting it. For a
  perturbation leg, show the perturbation diff itself alongside the red output — the reader must see
  that the break was in the changed code, not in the test.
- The generated test file's location, so a human can read the real code.
- Any drift found in Stage 1 (code vs. documented contract) as an explicit call-out block, even if it
  didn't block the scenario itself.
- Whether this run was a cold derivation or a cache hit, and any cache updates it wrote (new SUT
  facts, drift corrections) — each with its evidence.
- An explicit **"not checked"** section listing anything structurally out of scope for this run —
  never let the report imply broader coverage than what actually ran.

Then update `.codezen/agentic-e2e/cache.yaml`: append any landmine this run *proved* (a failure signature +
its root cause + the evidence, e.g. "surefire reruns share the JVM/database — correlate fixtures by
per-invocation ids"), correct any cached fact the run demonstrated was stale, and never write a
speculation. The cache is this machine's memory, not a report — keep entries short, sourced, and
deletable.

Format the report so it can be pasted directly as a PR comment or CI check output.

---

## Non-negotiable invariants (apply at every stage)

- Never accept "the agent says it passed" as a result — every reported pass must cite the actual
  external evidence produced.
- A green result counts only after the same, unmodified test has shown red in the form its change
  type demands (Stage 1/Stage 5) — and a non-behavioral change is reported as "nothing to test,"
  never pushed through a gate it cannot meaningfully take.
- Never mutate the developer's own checkout, index, or stash. Testing uncommitted work uses the
  temporary-index snapshot from Setup; base states and perturbations exist only inside this run's
  isolated worktree and are reverted/removed with it.
- A perturbation calibrates the test, never evaluates the change: it targets the changed code, never
  the test file, is shown in the report next to its red output, and is reverted (with green
  re-confirmed) before any verdict is issued.
- Never cache a guess. Every `.codezen/agentic-e2e/cache.yaml` entry names its source (a repo file) or its
  proof (a run's actual output). A cached fact that fails its spot-verify is re-derived, not patched.
- Never commit the cache or run output; never write outside `.codezen/agentic-e2e/` except (a) a
  cache-recorded `generated_test_path_override` target (throwaway-per-run, removed at teardown) and
  (b) the one-line `.gitignore` addition proposed on first run — and nothing into a service's own
  source tree without the repo's conventions (`CONVENTIONS.md`/`CLAUDE.md`) confirming it's safe.
- Everything environment-touching runs under the `sut-bootstrap` skill's own invariants (no false
  READY, OS-scoped instructions only, catalog immutability, user-space before `sudo`, no unattended
  privilege) — delegating to it never relaxes them, and this pipeline never bypasses it to mutate a
  machine directly.
