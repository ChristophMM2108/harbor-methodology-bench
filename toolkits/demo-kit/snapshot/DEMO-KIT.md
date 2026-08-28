# demo-kit

A deliberately tiny methodology, vendored in `harbor-methodology-bench` so the
pipeline is runnable straight after cloning, with no access to any private
toolkit repository.

It is a fixture, not a serious methodology: three instructions and one skill,
chosen because their effect is easy to see in a trajectory (a `PLAN.md` appears;
tests run between edits). Use it to prove the plumbing — generate, validate,
preflight, one smoke trial — then declare your own toolkit in
`config/sources.yaml` and compare that instead.

Top-level names here avoid `README.md`, `docs/`, `tests/`, `src/` and `scripts/`
on purpose: a name that already exists in a benchmark image is diverted to the
collision archive, and every diverted file is one less piece of methodology in
front of the agent.
