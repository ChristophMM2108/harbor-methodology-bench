---
name: brainstorm
description: Use when starting a new feature, designing a new system, or refining an underspecified ask — any time a spec is needed before implementation. Symptoms include "build me X" without "for whom" or "why now", missing success criteria, multiple stakeholders with possibly-conflicting intent, or being tempted to write code on implicit assumptions.
argument-hint: "<feature-description | github-issue-URL | filepath>"
user-invocable: true
allowed-tools: Read Write Edit Bash Glob Grep
---

# CodeZen Brainstorm

Take a vague idea and turn it into a structured spec through dialogue. The user chooses upfront whether the finished spec publishes to Linear (with a pointer file in the repo) or stays local in this repo only.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, or scaffold any project until you have presented the spec and the user has approved it. This applies to every project regardless of perceived simplicity.
</HARD-GATE>

## Loading constraints

This skill needs an interactive user. Do NOT run in:
- CI pipelines or scheduled runs
- `/loop` or autonomous-loop contexts
- Any non-TTY environment

If you can't have live back-and-forth with a human, stop and tell the user the ask is underspecified — don't guess.

## Quick Reference

| Step | Purpose | Hard stop if… |
|---|---|---|
| 0a — Resolve hook | Find `publish-spec.sh` | hook not on disk |
| 0b — Parse args | Derive `FEATURE_DESCRIPTION` + `FEATURE_SLUG` | empty input, no clarification |
| 0c — Journal | Prepare `.brainstorm/`, gitignore | — |
| 0d — Publish target | Ask user: Linear or local; check config if Linear | user wants Linear but won't configure |
| 1 — Explore | Read files, commits, project type | — |
| 2 — Interview | Hypothesis + guess-attached questions | 6+ rounds without confidence rising |
| 3 — Restate intent | 6-line restate with mandatory Out-of-Scope | user won't give explicit yes |
| 4 — Approaches | Propose 2–3 with trade-offs | — |
| 5 — Design sections | Present + approve each | — |
| 6 — Compose spec | Frontmatter + body + appendix | — |
| 7 — Publish | Single hook call; parse JSON | — |
| 8 — Wrap up | Next steps, no auto-handoff | — |

---

## Step 0a — Resolve the publish hook path

```bash
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]] && [[ -f "${CLAUDE_PLUGIN_ROOT}/hooks/publish-spec.sh" ]]; then
    PUBLISH_HOOK="${CLAUDE_PLUGIN_ROOT}/hooks/publish-spec.sh"
elif [[ -f "plugin/hooks/publish-spec.sh" ]]; then
    PUBLISH_HOOK="plugin/hooks/publish-spec.sh"
else
    echo "ERROR: publish-spec.sh not found. Is codezen-lite installed as a Claude Code plugin?"
    exit 1
fi
```

Store `PUBLISH_HOOK` for use in Steps 0d and 7.

---

## Step 0b — Parse `$ARGUMENTS`

Derive `FEATURE_DESCRIPTION` and `FEATURE_SLUG`.

- **GitHub issue URL** (`https://github.com/<owner>/<repo>/issues/<n>`):
  ```bash
  gh issue view <n> --repo <owner>/<repo> --json title,body,comments
  ```
  Use title + body as `FEATURE_DESCRIPTION`. Slug = slugified title (lowercase, hyphens, ≤50 chars).

- **Filepath** (starts with `./`, `/`, `../`, or exists on disk):
  Read the file. Use contents as `FEATURE_DESCRIPTION`. Slug = filename without extension.

- **Plain text**: use `$ARGUMENTS` directly. Slug = first 4–5 meaningful words, slugified.

- **No arguments**: ask *"What would you like to brainstorm? Give me a short feature description, a filepath, or a GitHub issue URL."* Don't proceed until they answer.

Also derive `FEATURE_TITLE` — a human-readable title (e.g., "User Authentication System"). For GitHub-issue input this is the issue title verbatim. For filepath/plain-text, derive a clean title from the description.

---

## Step 0c — Prepare journal and gitignore

```bash
mkdir -p .brainstorm
JOURNAL=".brainstorm/conversation-${FEATURE_SLUG}.md"
touch "${JOURNAL}"

if [[ ! -f .gitignore ]] || ! grep -q '^\.brainstorm/' .gitignore 2>/dev/null; then
    echo ".brainstorm/" >> .gitignore
fi
```

---

## Step 0d — Choose publish target (and verify if Linear)

Ask the user explicitly. Don't infer from environment.

> "Where should the finished spec land?
>
>   1. Publish to Linear (with a pointer file committed to this repo) — for team-visible specs
>   2. Local only (`docs/specs/${FEATURE_SLUG}.md` in this repo) — for personal, internal, or draft specs"

Wait for an explicit answer. Store `PUBLISH_TARGET=linear` or `PUBLISH_TARGET=local`.

### If `PUBLISH_TARGET=local`:

Skip the configuration check entirely. Proceed to Step 1.

### If `PUBLISH_TARGET=linear`:

Verify Linear is configured:

```bash
bash "${PUBLISH_HOOK}" --check
```

**Exit 0 (LINEAR_CONFIGURED):** proceed to Step 1.

**Exit 1 (LINEAR_NOT_CONFIGURED):**

Show the user what the check reported (it lists the specific missing pieces — `CODEZEN_SERVER_URL`, `curl`, `jq`, etc.), then offer three options:

> "Linear publishing isn't configured yet. To enable, set:
>
> ```
> ! export CODEZEN_SERVER_URL=https://codezen.<your-org>.com
> ```
>
> (Env vars set via `! …` in this session persist into subsequent commands.)
>
> How would you like to proceed?
>
>   1. Configure now — I'll wait while you run the export
>   2. Switch to local-only — write the spec to `docs/specs/${FEATURE_SLUG}.md`, skip Linear
>   3. Cancel — exit cleanly, no changes made"

- **Configure now:** wait for the user to say "done" or similar. Re-run `bash "${PUBLISH_HOOK}" --check`. If still not configured, ask again. Loop until configured or the user picks option 2 or 3.
- **Switch to local-only:** set `PUBLISH_TARGET=local`, proceed to Step 1.
- **Cancel:** delete the empty journal (`rm -f "${JOURNAL}"`), exit. No work done.

Store the final `PUBLISH_TARGET` for Step 7.

---

## Step 1 — Explore project context

Ground your hypothesis before opening your mouth:

- Glob for manifests: `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `Gemfile`
- Read `README.md` and any top-level docs
- `git log --oneline -20` for recent direction
- Glob `docs/specs/` for existing specs — follow conventions if any exist
- For a GitHub-issue input, also fetch any comments on the issue

Do not dump findings to the user. Use them to sharpen the initial hypothesis in Step 2.

---

## Step 2 — Interview the user

The longest step. Use the **guess-attached question** technique throughout.

### Open with a calibrated hypothesis

Your first message in this step must take this exact form:

```
HYPOTHESIS: <one-sentence read of what the user wants>
CONFIDENCE: ~<N>%
```

The number forces honesty. If you wrote ~80% but can't actually predict the user's reaction to your next three questions, the number is wrong. Start at the confidence level you can defend.

### Then ask one question at a time, with a guess attached

Every subsequent message in this step uses this exact format:

```
Q:     <one focused question>
GUESS: <your hypothesis for the answer, with the reasoning that produced it>
```

Wait for the user to respond before sending the next question.

**Rules:**
- One question per message. Never batch.
- Always include a `GUESS`. Not "I wonder…", not a survey — a concrete hypothesis you can be visibly wrong about.
- Be visibly willing to be wrong. Occasionally guess in a direction you expect pushback on.
- Don't accept polite-sycophant answers. If the user says "whatever you think" or "sounds good," re-ask with two concrete options framed as a choice.

### After each user reply: journal the turn

Append to `${JOURNAL}` so the conversation is preserved for the spec appendix:

```bash
cat >> "${JOURNAL}" <<EOF

### Turn <N>
**Claude:** <your question, verbatim>
GUESS: <your guess, verbatim>

**User:** <user's reply, verbatim>
EOF
```

Do this every turn. Don't try to reconstruct the conversation at the end.

### The "want vs. should-want" probe

If the user gives a sophistication-signaling answer — words like *scalable, clean, modern, robust, best practice, the way most apps do it, the standard approach* — do NOT accept it. Ask:

> *"If you didn't have to justify this to anyone, what would you actually want?"*

That single question often does more work than the previous five.

### The 95% confidence stop (falsifiable)

You're done with Step 2 when you can answer **yes** to:

> *"Can I predict the user's reaction to the next three questions I would ask?"*

This is a checkable test, not a vibe. If yes, proceed to Step 3. If no, ask another question.

### Floor

If you've asked 6+ questions and confidence isn't rising, stop and tell the user:

> "I've asked X questions and still can't predict your reactions. Something foundational is missing. Want to step back?"

That's information about the ask, not a reason to keep grinding.

---

## Step 3 — Restate intent

Once you hit the stop condition, write back what you now think the user wants. Use this exact shape:

```
Here's what I now think you want:

- Outcome:      <one line>
- User:         <one line — who benefits>
- Why now:      <one line — what changed to make this matter>
- Success:      <one line — how we'd know it worked>
- Constraint:   <one line — the binding limit (time, budget, compatibility)>
- Out of scope: <one line — what we're explicitly NOT building>

Yes / no / refine?
```

**Mandatory:** the `Out of scope` line. Half of misalignment is silent disagreement about non-goals. Never omit it. If you can't think of one, ask: *"What's one thing you want me to explicitly NOT build here?"*

**The gate is an explicit yes.** Not "whatever you think." Not "sounds good." Not silence. If the user delegates, re-ask with two concrete options. If they correct you, fold the correction in and re-restate. Loop until you get an explicit yes.

Append the approved restate to the journal:

```bash
cat >> "${JOURNAL}" <<EOF

### Restate (approved)
- Outcome:      <...>
- User:         <...>
- Why now:      <...>
- Success:      <...>
- Constraint:   <...>
- Out of scope: <...>
EOF
```

---

## Step 4 — Propose 2–3 approaches

Lead with your recommendation:

> "I'd lean toward Approach A because <reason>. Here are the three I considered:
>
> **A. <name>** — <one-paragraph description>. Trade-off: <gain> vs <cost>.
> **B. <name>** — <description>. Trade-off: <gain> vs <cost>.
> **C. <name>** — <description>. Trade-off: <gain> vs <cost>.
>
> Which direction, or should I propose more?"

User picks. Append the chosen approach + rejection rationale for the others to the journal.

---

## Step 5 — Present design sections

Lay out the design in sections, scaled to complexity. Approve each before moving on.

Cover at minimum:
- **Architecture** — high-level shape, major components
- **Data flow** — what flows where, who owns what state
- **Boundaries** — interfaces between components, what's mockable
- **Error handling** — how failures surface
- **Testing** — what gets tested at which tier

A few sentences for straightforward sections; up to 200–300 words if nuanced. After each: *"Does that look right? Anything to adjust?"*

If the user says go back to a previous section, do it. Don't power through.

Append every approved section to the journal.

---

## Step 6 — Compose the spec

Build the full spec content. Write it to a temp file so the publish hook can read it:

```
COMPOSED_FILE=".brainstorm/composed-${FEATURE_SLUG}.md"
```

The composed file must use this exact frontmatter shape:

```yaml
---
type: codezen-spec
slug: <FEATURE_SLUG>
title: <FEATURE_TITLE>
status: draft
created: <YYYY-MM-DD>
authors:
  - <git config user.name>
version: 1
linear_doc_id: null
linear_doc_url: null
---
```

And this body structure (each `<...>` is content you generate from Steps 3–5 + the journal):

```markdown
# <FEATURE_TITLE>

## Overview
<2–3 sentences synthesizing Outcome + User + Why now from the restate>

## Goals & Non-Goals

**Goals:**
- <Success line, broken into measurable items>
- <Anything else surfaced as a goal during design>

**Out of Scope:**
- <Out-of-scope line from the restate — mandatory>
- <Any other non-goals surfaced during design>

## Approach
<Chosen approach from Step 4, plus why alternatives were rejected (1–2 paragraphs)>

## Design

### Architecture
<from Step 5>

### Data flow
<from Step 5>

### Boundaries
<from Step 5>

### Error handling
<from Step 5>

### Testing
<from Step 5>

## Open questions
<Anything you flagged during design that's deliberately deferred>

---

## Appendix: Brainstorm Conversation

*This spec was developed through the following dialogue on <YYYY-MM-DD>.*

<contents of $JOURNAL, verbatim>
```

Use the Write tool to put this exact content at `${COMPOSED_FILE}`.

---

## Step 7 — Publish

Single call to the hook. It handles write-to-disk, optional Linear upload, journal cleanup, and the git commit.

```bash
RESULT=$(bash "${PUBLISH_HOOK}" --publish \
    --target "${PUBLISH_TARGET}" \
    --slug "${FEATURE_SLUG}" \
    --title "${FEATURE_TITLE}" \
    --content-file "${COMPOSED_FILE}" \
    --journal "${JOURNAL}")
EXIT=$?
```

Parse the JSON in `$RESULT`. The shape is:

**Success (any target):**
```json
{
  "status": "success",
  "target": "linear" | "local",
  "spec_path": "docs/specs/<slug>.md",
  "commit_sha": "...",
  "linear_doc_id":  "<only if target=linear>",
  "linear_doc_url": "<only if target=linear>"
}
```

**Failure (Linear upload):**
```json
{
  "status": "error",
  "target": "linear",
  "reason": "<error message>",
  "stash_path": ".brainstorm/pending/<slug>.md"
}
```

Then clean up the temp composed file:

```bash
rm -f "${COMPOSED_FILE}"
```

(The hook deletes the journal; the skill deletes the composed file. Different ownership, same effect.)

---

## Step 8 — Wrap up

Tell the user concisely. Choose based on the JSON result.

### Success, `target=linear`:

> Spec published to Linear: `<linear_doc_url>`
> Pointer committed at `<spec_path>` (`<commit_sha>`).
>
> Next:
> - Edit the Linear Document directly for refinements.
> - When `/decompose-spec` is built, run it against this spec to create the Linear epics/stories/tasks.

### Success, `target=local`:

> Spec written to `<spec_path>` and committed (`<commit_sha>`).
>
> Next:
> - Use the spec as-is for implementation reference.
> - To later publish to Linear, set `CODEZEN_SERVER_URL` and re-run `/brainstorm` against the same input (or use `/publish-spec` once it exists).

### Failure (Linear upload failed):

> Linear upload failed: `<reason>`.
> Your composed spec is stashed at `<stash_path>`.
>
> Next:
> - Check that `CODEZEN_SERVER_URL` points at a reachable codezen-server with the `/specs` endpoint live.
> - Re-publish: `bash <hook> --publish --target linear --slug <slug> --title "<title>" --content-file <stash_path>`
> - Or switch to local: same command with `--target local`.

**Do NOT auto-invoke any other skill.** Brainstorm ends here — the user decides what's next.

---

## Rules

- **Out of scope is mandatory** in the restate. Never skip it. Half of misalignment is silent disagreement about non-goals.
- **One question at a time** during the interview. Never batch. Always include the `GUESS`.
- **Journal every turn** as it happens. Don't reconstruct from memory at the end.
- **Explicit yes only.** "Sounds good" / "whatever you think" / silence are NOT confirmation.
- **The 95% confidence stop is falsifiable.** If you can't predict the user's reactions to the next three questions you'd ask, you're not done.
- **No auto-handoff.** Brainstorm does not invoke `writing-plans`, `decompose-spec`, or any other skill at the end. The user decides.
- **No silent fallback from Linear to local.** If the user chose Linear and upload fails, the hook stashes the composed spec and exits non-zero. Report the stash path and retry options — don't write a local file unprompted.
- **Don't probe with the "what would you actually want" question more than twice per session.** It's a scalpel, not a hammer.
- **Non-interactive refusal.** If invoked in CI / autonomous-loop / non-TTY, refuse with: "this skill needs an interactive user — the current ask is too underspecified to proceed without one."
