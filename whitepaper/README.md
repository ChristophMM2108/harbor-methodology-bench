# Whitepaper: does a repository's agent configuration make a coding agent better?

A consolidated, fully recomputed reading of the `suite` and `ceiling` runs of
`harbor-methodology-bench`, integrating the primary per-run analyses, the cross-run
synthesis, and the independent critical review contributed by Antigravity (Google DeepMind).

**Two outputs, same recomputed data:**

| Document | Length | For |
|---|---|---|
| [`brief.pdf`](brief.pdf) — *The Cost of Process* | 19 pp, 12 figures, 6 tables | the significant results only: the cost finding, the clock, adherence, the length paradox, the retry question, and what to change. Starts with a one-page summary. |
| [`main.pdf`](main.pdf) | 48 pp, 20 figures, 7 diagrams, 18 tables | the complete record: every table, every censored trial, the full correlation matrix, the per-task tables, and all nine adjudicated divergences. |

Read `brief.pdf` first. `main.pdf` is what it cites.

## Layout

```
whitepaper/
  brief.tex                 the short report — significant results only
  main.tex                  the full paper
  references.bib            20-entry bibliography; `% VERIFY` comments mark unconfirmed details
  Makefile                  regenerate everything, then compile
  data/                     recomputed values, source memo, and the citation audit
    verified_numbers.json     every number the paper quotes, recomputed from the trial tables
    best_of_n.json            independence check and the three best-of-N estimators
    pooled_task_table.csv     26 tasks x 3 conditions, differenced against baseline
    schmierzettel.txt         the literature review memo both documents cite from
    citation-map.md           where every citation landed, and what still needs verifying
  figures/                  20 figures, PDF (for LaTeX) + PNG (for preview)
  diagrams/                 7 Mermaid diagrams: .mmd source + PDF + PNG
  tables/                   generated LaTeX table fragments (t* full paper, b* short report)
  scripts/
    verify_numbers.py       recomputation of every quoted quantity
    best_of_n.py            best-of-N estimators and the attempt-independence check
    figures_common.py       shared print style
    make_figures_perrun.py  the six per-run views, for both runs
    make_figures_cross.py   the eight cross-run figures
    make_tables.py          LaTeX table fragments for the full paper
    make_tables_brief.py    trimmed table fragments for the short report
    make_citation_map.py    harvests citation placements into data/citation-map.md
    render_diagrams.sh      Mermaid -> PDF/PNG via mermaid-cli and the system Chrome
```

Nothing in `data/`, `figures/`, `tables/` or the rendered diagrams is hand-written: all of it
is generated from `results/analysis-{suite,ceiling}/data/*.csv`, which are themselves the
exports of the two analysis notebooks.

## Build

Requirements: the repository's `.venv` (pandas, numpy, scipy, matplotlib), `tectonic`
(any recent single-binary release, on `PATH` or in `~/.local/bin`), and — for the diagrams
only — `npx` plus a system Chrome or Chromium.

```bash
cd whitepaper
make            # data -> figures -> diagrams -> tables -> both PDFs -> citation map
make brief      # compile the short report only
make paper      # compile the full paper only
make citations  # refresh data/citation-map.md after moving a citation
```

Tectonic runs BibTeX automatically, so no separate bibliography step is needed.

## Before circulating either PDF

`references.bib` follows the literature memo in `data/schmierzettel.txt`. Nine of its 20
entries — chiefly the 2026 works — carry a `% VERIFY <key>:` comment because their
bibliographic details could not be confirmed first-hand; three more carry a `% NOTE <key>:`
explaining a substitution for a source the memo named but did not identify. `data/citation-map.md` lists all of them, records
every placement in both documents, and flags three points where the memo's own attribution
appears to be wrong. Both PDFs state this in a provenance note above their reference list.
Nothing was invented to fill a gap: unknown identifiers were left out rather than guessed.

`render_diagrams.sh` points mermaid-cli at the system Chrome through a generated
`puppeteer.json`, because the bundled `chrome-headless-shell` is not installed here. Override
with `CHROME=/path/to/chrome ./scripts/render_diagrams.sh`.

## Source documents consolidated here

| Document | Role |
|---|---|
| `results/analysis-suite/suite_discussion.md` | primary reading of the 96-trial `suite` run |
| `results/analysis-suite/suite_discussion_antigravity.md` | independent review of the same |
| `results/analysis-ceiling/ceiling_discussion.md` | primary reading of the 60-trial `ceiling` run |
| `results/analysis-ceiling/ceiling_discussion_antigravity.md` | independent review of the same |
| `results/codezen-vs-sdd_discussion.md` | primary cross-run synthesis |
| `results/codezen-vs-sdd_discussion_antigravity.md` | independent cross-run synthesis |

Every finding in those six documents is carried into `main.pdf`. Where two readings disagree,
its Section 10 states the disagreement, gives the recomputed value, and says which reading
survives; `brief.pdf` carries the three divergences that change something a reader would act
on. See `data/verified_numbers.json` for the recomputation itself.
