---
description: Map a Python file's intra-repo dependencies before working on it
argument-hint: <path/to/file.py> [--max-hops N] [--repo-root PATH]
allowed-tools: Bash(python3 .claude/scripts/ccmap.py:*)
---

Run the dependency map for the target the user named:

```
python3 .claude/scripts/ccmap.py $ARGUMENTS
```

Then use the output to decide what to read, and say so briefly:

- Read the **hop 1** files first — those are direct call dependencies.
- Treat **hop 2** as context only; read them if hop 1 doesn't explain enough.
- If the output lists **0 dependencies**, don't conclude the file is standalone. The
  resolver is name-based and misses dynamic dispatch. Fall back to Grep.
- If **RELIABILITY WARNINGS** appear, say which ones and adjust: `getattr` dispatch or
  event decorators mean real dependencies may be absent from the list; ambiguous call
  names mean some listed files may be irrelevant.
- Do **not** read every listed file just because it's listed. The token figure is the
  cost of reading all of them, not a recommendation to.

This tool is Python-only and covers intra-repo call graphs, not imports from installed
packages. If the target isn't a `.py` file, the script exits with an error — just use
Grep and Read instead.
