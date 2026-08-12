# Skill authoring guide

## SKILL.md schema

```yaml
---
name: skill-name
description: One or two sentences. Trigger conditions belong here — be
  specific about when Claude should reach for this skill.
---
```

Followed by plain-language instructions. Point to `tools/` scripts for
anything nontrivial rather than inlining logic.

## Naming

Prefix by domain: `sdd-*`, `ctx-*`, etc. Keep names lowercase, hyphenated.

## Versioning

Track changes in a `CHANGELOG.md` inside the kit/skill directory once it
has external users (e.g. after promotion, or once used in >1 project).
