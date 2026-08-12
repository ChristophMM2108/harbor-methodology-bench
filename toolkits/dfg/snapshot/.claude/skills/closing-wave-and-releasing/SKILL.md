---
name: closing-wave-and-releasing
description: 'Layer-shaped skill teaching the blessed end-to-end release recipe.

  Covers `dfg run ship-release --input VERSION=<x.y.z>` workflow composition,

  the three HITL pauses (release-prep PR, gate PR, publish confirmation),

  release-prep editing convention (CLAUDE.md + RELEASE-NOTES.md +

  ROADMAP-v0.6 + DISCIPLINE-CHANGELOG), the canonical authorization phrase

  `publish v<x.y.z>` (sub-papercut 11), `dfg release preflight` /

  `dfg release publish` / `dfg release audit`, capability mint receipts

  (version.bump, release.publish), the publish-events follow-up PR

  (W54-4 detached-HEAD auto-sync), and tag/GH-release verification.

  '
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Operator types \"ship v<x.y.z>\", \"release v<x.y.z>\"\
  , or invokes\n  `dfg run ship-release` / `dfg release publish`.\n- A wave's gate\
  \ has passed (WaveGatePass emitted) and the release ceremony\n  is the next ceremony\
  \ per `dfg flow next`.\n- The ship-release workflow is paused at one of the\
  \ 3 HITL boundaries\n  (release-prep PR, gate PR, publish confirmation) and the\
  \ operator\n  needs the recipe for the next handoff.\n"
sdlc_category: Release
loop_layer: L1-sprint
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE invoking `dfg run ship-release`. The skill prevents

  the agent from reinventing the release pipeline inline (which has

  shipped sub-papercuts #11, #3, #13 across W54-W63), and ensures the

  canonical `publish v<x.y.z>` authorization phrase is taught to the

  operator BEFORE the publish-confirmation pause (so the operator knows

  what to type to authorize the harness defense-in-depth gate).

  '
verified_at: 2026-05-17
forged_by: dfg-harness W67-2 layer-shaped-skills
---
# Closing the wave and releasing

## Why this skill exists

The blessed release path crystallized over W52-W63 with multiple sub-papercut
receipts. The current canon (W61-1 ship-release workflow) composes all the
discipline into one parameterized ceremony. Agents who reinvent it inline
miss:

- The 3-pause HITL structure (release-prep PR / gate PR / publish-confirm).
- The canonical `publish v<x.y.z>` phrase that authorizes the harness
  defense-in-depth gate (sub-papercut #11).
- The `dfg release audit` verification that produces the CLEAN receipt.
- The W54-4 publish-events follow-up PR that delivers the detached-HEAD
  auto-sync commits back to main.

This skill teaches the end-to-end recipe so the operator types one workflow
invocation and `dfg run-resume` three times instead of reconstructing the
pipeline by hand.

## The recipe

```bash
# 0. Prereq: wave gate already closed (WaveGatePass event in events.jsonl).
#    If not, run `dfg run wave-close --input CURRENT_WAVE=W<n>` first.
#    See sibling skill `shipping-wave-close-gate`.

# 1. Start the release ceremony — workflow drives version + 3 pauses
uv run dfg run ship-release --input VERSION=<x.y.z>

# 2. PAUSE #1 — release-prep PR
#    Workflow has run pre-flight + `dfg version bump <x.y.z>` and paused.
#    Operator (or follow-up agent) authors edits:
#      - docs/RELEASE-NOTES.md  (theme + receipts for <x.y.z>)
#      - CLAUDE.md              (status anchor)
#      - docs/ROADMAP-v0.6-proof-carrying-actions.md (if applicable)
#      - docs/DISCIPLINE-CHANGELOG.md
#    Stage version-bump diff + edits, commit on release/v<x.y.z>-prep
#    branch, push, open PR. Wait for CI green + merge.

uv run dfg run-resume <attempt_id>

# 3. PAUSE #2 — gate PR (skip if pre-closed; ceremony detects idempotency)
#    From a fresh worktree on release/v<x.y.z>-gate, author
#    .dfg/checkpoints/W<n>-gate.md, run `dfg wave close W<n> --no-hygiene
#    --json` (emits WaveGatePass), commit, push, open PR, merge.

uv run dfg run-resume <attempt_id>

# 4. PAUSE #3 — publish confirmation (sub-papercut #11)
#    Workflow is about to call `dfg release publish`. Operator must
#    reply with the canonical phrase to authorize the defense-in-depth
#    gate:
#
#        publish v<x.y.z>
#
#    The exact phrase is load-bearing; the gate matches it literally.
#    Without it the publish step refuses to run.

uv run dfg run-resume <attempt_id>

# 5. Workflow runs `dfg release publish` + `dfg release audit` automatically.
#    Tag is created at v<x.y.z>, GitHub release published, publish-time
#    events are emitted (CapabilityVerified for release.publish).

# 6. PAUSE #4 — publish-events follow-up PR (W54-4 detached-HEAD auto-sync)
#    Publish-time events were committed locally on the detached HEAD.
#    Push as chore/release-followup-v<x.y.z>-publish-events. Open PR with
#    title `chore(release-followup): deliver v<x.y.z> publish-time events
#    to main`. After merge the release ceremony is COMPLETE.

uv run dfg run-resume <attempt_id>
```

## The canonical authorization phrase (sub-papercut #11)

Before pause #3 (publish confirmation), teach the operator the exact phrase:

> `publish v<x.y.z>`

This is the harness defense-in-depth gate per sub-papercut #11. The
`dfg release publish` command refuses to run unless the operator has
typed the literal phrase (substituting the actual version). The phrase is:

- Lower-case `publish` (not `PUBLISH`, not `Publish`).
- Exact `v<x.y.z>` (e.g., `publish v0.5.34` — not `0.5.34`, not `v.0.5.34`).
- No trailing punctuation.

The phrase is the operator's load-bearing authorization. The skill MUST
teach it BEFORE the pause hits, not as a recovery step after the publish
refuses.

## Release-prep editing convention

The release-prep PR edits 4 (sometimes 3) canonical files:

1. **`docs/RELEASE-NOTES.md`** — add the new `## v<x.y.z>` entry with
   theme + receipts. This is the canonical release narrative.
2. **`CLAUDE.md`** — update the "Current state anchor" paragraph to
   cite the new version + wave closure.
3. **`docs/ROADMAP-v0.6-proof-carrying-actions.md`** — only if this
   release advances the roadmap. Mark completed waves; update next-wave.
4. **`docs/DISCIPLINE-CHANGELOG.md`** — add the wave's discipline scars
   + retirements + new §amendments.

`dfg version bump <x.y.z>` (which the ceremony runs automatically before
pause #1) updates `pyproject.toml` (the canonical version source per
ADR-019 §amendment-9 / §amendment-12). The 4 doc edits go in the same
release-prep PR alongside the auto-bumped pyproject diff.

## Capability mint receipts

Two capabilities mint during a successful release:

| Consumer | Minted when | Verification |
|---|---|---|
| `version.bump` | `dfg version bump <x.y.z>` (pre pause #1) | `dfg version verify` |
| `release.publish` | `dfg release publish` (after pause #3) | `dfg release audit <x.y.z>` |

`dfg release audit <x.y.z> --wave W<N>` produces the CLEAN receipt that
the release is structurally honest (tag exists, GH release exists,
WaveGatePass is recorded, capability is verified).

## Tag + GitHub release verification

After successful publish:

```bash
# Tag is created locally and pushed
git tag --list 'v<x.y.z>'

# GitHub release is published — verify URL
gh release view v<x.y.z>

# Canonical URL
echo "https://github.com/korzainc/dfg-harness/releases/tag/v<x.y.z>"

# Audit produces the CLEAN receipt
uv run dfg release audit <x.y.z> --wave W<N>
```

## Discipline checks

1. **Never `git tag` directly.** Only `dfg release publish` mints the tag
   through the blessed path (W53 keystone). Manual tagging bypasses the
   capability mint and breaks `dfg release audit`.
2. **Never `gh release create` directly.** Same reasoning.
3. **Never skip the gate PR.** The release ceremony refuses to publish
   without a WaveGatePass event. If `pause-for-gate-pr` returns
   idempotent (gate pre-closed), that's fine; if no gate exists, the
   publish step fails.
4. **Never paste the publish-confirmation phrase early.** The phrase is
   the operator's authorization. Authoring agents teach it; only the
   operator types it.
5. **Always run `dfg release audit` after publish.** If audit returns
   anything other than CLEAN, the release has a structural defect that
   must be fixed before claiming "released".

## Composing with sibling skills

- `running-ceremony-workflows` — covers the `dfg run` + `dfg run-resume`
  mechanics this skill orchestrates.
- `shipping-wave-close-gate` — covers the gate authoring at pause #2.
- `authoring-retro` — covers the per-unit retros that must exist before
  the wave gate (which must exist before the release).

## Authority

- `kit/ceremonies/ship-release.yaml` is the canonical workflow.
- W61-1 keystone — parameterized ship-release ceremony.
- W53 keystone — `dfg release publish` capability consumer.
- W55-2 keystone — `version.bump` capability consumer.
- W54-4 keystone — publish-events detached-HEAD auto-sync.
- Sub-papercut #11 — canonical `publish v<x.y.z>` phrase (recurring
  receipt across W54-W63).
- `dfg release --help` is canonical CLI shape.

## Trust and calmness pre-release route

Before closing a wave or resuming a release ceremony, run the trust/calmness bundle:

```bash
uv run dfg status --json
uv run dfg actor whoami --json
uv run dfg actor verify --id <actor> --json
uv run dfg permit release.publish --actor <actor> --json
```

Interpret this bundle as advisory-plus-policy, not decoration:

- `dfg status --json` exposes calmness and capability nudges; resolve required or high-signal situational nudges before claiming the wave is calm.
- `dfg actor verify` distinguishes registered posture from self-asserted actor strings. Unknown or unverified actors should not be treated as authorization for release.publish.
- `dfg permit release.publish --actor <actor>` is the policy-facing check before the operator types `publish v<x.y.z>`.
- `dfg run wave-close --input CURRENT_WAVE=W<N>` now runs `dfg retro replan-suggest --mode lightweight` advisory by default. Do not run a separate, heavier retro harvest unless status/next or the operator asks for it.
- If `dfg history` reports lifecycle scars, either resolve them or file an explicit history-pardon artifact before using calmness as a release claim.

This keeps release work boring in the best way: identity known, policy posture checked, retros harvested, scars either resolved or explicitly pardoned.
