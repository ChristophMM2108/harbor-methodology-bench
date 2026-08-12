# Contributing

## Authoring conventions

- Every skill/kit gets its own directory with a `README.md` explaining what
  it does and why it exists.
- `SKILL.md` files should be mostly instructions; nontrivial logic belongs
  in `tools/` and gets called into, not inlined.
- Naming: prefix skills by domain, e.g. `sdd-*` for spec-driven-development
  skills, `ctx-*` for context/token-reduction skills. Keeps origin obvious
  once skills live side-by-side in `.claude/skills/`.
- Any PR that claims a performance win (fewer tokens, faster loop) must
  include a before/after number, ideally produced by `tools/benchmarks/`.

## Adding something new

1. Decide kit vs. skill (see README).
2. Scaffold with `scripts/new-kit.sh` or `scripts/new-skill.sh`.
3. Add a test under `tests/integration/` (for kits) or a usage example
   (for skills).
4. Open a PR — CI runs `validate-skills.yml` / `test-kits.yml`.

## Promoting to the company Claude skills repository

Suggested bar before promotion (adjust as your team settles on one):

- [ ] Used in at least one real project outside this repo's own tests
- [ ] Has a measured before/after (tokens, time, or error-rate)
- [ ] `SKILL.md` frontmatter validated (`tools/skill_validator`)
- [ ] No repo-local paths or dependencies on this repo's structure
- [ ] Reviewed by at least one other team member

Run `scripts/package-for-upstream.sh <path>` to produce a clean, portable
copy ready to become a PR against the company repo.
