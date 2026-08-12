---
description: Pre-PR checks — git status, lint, tests, ci, issue link. Refuses on any "no".
---

# /harness-pre-pr-checklist

You are running the pre-PR checklist. This slash command operationalises
the discipline already in `kit/METHODOLOGY/03-hardening-loop.md`: **no PR
opens before local CI is green and the issue is linked**.

Origin: post-W1 retrospective (issue #18) — two PRs merged in W1 with red
CI because the discipline existed only as text. This makes it
operational.

## Process — six checks

Each check returns ✓ or ✗. **Any ✗ aborts the push.**

| # | Check                       | Command                          | Pass condition |
|---|-----------------------------|----------------------------------|----------------|
| 1 | Worktree clean              | `git status --porcelain`         | Empty output   |
| 2 | Branch ahead of main        | `git log main..HEAD --oneline`   | Non-empty      |
| 3 | Lint passes                 | `make lint`                      | Exit 0         |
| 4 | Tests pass                  | `make test`                      | Exit 0         |
| 5 | Full CI green locally       | `make ci`                        | Exit 0         |
| 6 | Issue / spec linked in PR body | inspect prepared body         | see below      |

**Check 5 is the canonical gate** — `make ci` must reproduce remote CI.

**Check 6:** Inspect the prepared PR body (operator passes path, or
`.git/pr-body.md`). Required:
- `Closes #<n>` or `Fixes #<n>` (issue link)
- `## Wave / DFG` block referencing the wave / work unit
- `## Acceptance criteria (from #<issue>)` checklist

All three present → ✓. Any missing → ✗.

## Output format

```
Pre-PR checklist — <branch>
  [✓] worktree clean
  [✓] branch ahead of main
  [✓] lint passes
  [✓] tests pass
  [✓] make ci exit 0
  [✓] issue / spec linked

Verdict: READY TO PUSH | ABORT — <list of failures>
```

## Discipline

- **Refuse on any ✗.** Do not run `git push`. Surface the failures and
  exit. The author fixes locally; re-runs the checklist; pushes only after
  all six pass.
- **Do not "skip 5 because it's slow."** The whole point of issue #18 is
  that skipping `make ci` is what produced the red-CI-merge anti-pattern.
- **Do not rely on remote CI to catch what local CI catches.** Remote CI
  is the second line of defence; this checklist is the first.

## When to invoke

Author (or dispatch agent acting as author) runs this **immediately
before** `git push`. Pair with the PR-template requirement: the PR body
must reference the issue per check 6.

Closes #18.
