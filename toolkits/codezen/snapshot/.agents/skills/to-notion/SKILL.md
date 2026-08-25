---
name: to-notion
description: Use when a local markdown document needs to exist as a Notion page — publishes any markdown file to Notion, converting to Notion-flavored markdown, and reports the page URL. Never modifies the file it publishes. Triggers on "publish to Notion", "mirror this to Notion", "put this doc in Notion". Works standalone, and can be called by any skill that produces a document worth mirroring — designs, specs, ADRs, review reports.
argument-hint: "FILEPATH [--to PARENT_PAGE_URL] [--update PAGE_URL] [--title TITLE] [--dry-run]"
compatibility: Requires a filesystem holding the markdown file, and a connected Notion MCP integration with permission to create pages. Git is optional, used only to rewrite relative links. AskUserQuestion and ToolSearch are preferred where available; prose fallbacks are specified so the skill runs on any harness.
allowed-tools: Read Bash Glob Grep ToolSearch AskUserQuestion mcp__*
metadata:
  mcp-server: notion
  version: "0.1.0"
  author: Korza
---

# CodeZen To Notion

```
/codezen:to-notion FILEPATH [--to PARENT_PAGE_URL] [--update PAGE_URL] [--title TITLE] [--dry-run]
```

Takes one markdown file on disk and makes it a Notion page, then prints the URL.
Knows nothing about what kind of document it is — HLD, LLD, spec, ADR, review
report all publish the same way. Keep it that way: document-specific logic belongs
in the calling skill.

**Read-only on your repository.** The output is a URL in the terminal. This skill
writes no frontmatter, edits no files, commits nothing, and stores the page
reference nowhere. `Edit` and `Write` are deliberately absent from
`allowed-tools`; `Bash` is present for read-only git queries only. Never reach
for `Bash` to write a file, stage, or commit — that is the one route by which
this promise can be broken, and the absent `Edit` does not close it.

**One direction only.** The repo is the source of truth; Notion holds a mirror.
Nothing is ever synced back down.

**Notation.** Backticked `CAPS` are placeholders to substitute — `PAGE_URL`, `N`.
Angle brackets are never placeholders in this file: they are literal Notion tags
(`<table>`, `<page>`, `<mention-page>`, `<br>`, `<ancestor-path>`) that appear verbatim
in Notion-flavored markdown or in `notion-fetch` output. Keep the two distinct; this
skill is the one place where confusing them changes what gets published.

## Portability

Two tools named below are Claude Code conveniences, not requirements. Where they are
unavailable, the requirement still holds and is met another way:

- **AskUserQuestion** → ask in prose, listing the same **named options**, and wait for
  a reply naming one. What matters is that the user sees the choices and picks; the
  widget is not the point.
- **ToolSearch** → skip it. Other harnesses expose MCP tools directly in context, so
  simply use the Notion tools already available. ToolSearch exists because Claude Code
  defers MCP tool schemas until asked.

**On the one non-spec field.** `argument-hint` is a Claude Code extension that drives
`/` autocomplete. Other agent runtimes parse frontmatter and ignore keys they don't
know, so it costs nothing there. It is only rejected by two Anthropic-side *validation*
paths — `skills-ref validate`, and packaging or uploading to claude.ai or the Skills
API, which fail with `Unexpected key(s) in SKILL.md frontmatter`. This skill ships as a
Claude Code plugin and takes neither path, so the hint is kept. Strip it if this is ever
uploaded as an API Skill; the usage line in the body above says the same thing.

`user-invocable` is deliberately absent for a different reason: its default is already
`true`, so setting it was a no-op.

The two things that genuinely are required: a filesystem with the file on it, and a
Notion MCP connection.

## Loading constraints

Publishing is outward-facing and hard to reverse — a page created in the wrong
teamspace has already been shared with everyone who can see that space. So:

- Never create or update a page without showing the resolved destination first
  and getting an explicit go.
- Do NOT run in `/loop`, autonomous, or non-TTY contexts unless `--to` was
  passed explicitly — a CREATE whose parent the caller already named is the only
  case where no confirmation is needed. `--update` does not qualify and is never
  exempt: it is the one flag that destroys content already on the page.
- **Nothing here can be undone.** The Notion integration exposes no delete or
  archive command — a page created in the wrong place has to be trashed by hand
  in the Notion UI by someone with access. That asymmetry is why Step 6 confirms
  instead of assuming, and why `--dry-run` exists.

## Quick reference

| Step | Purpose | Hard stop if… |
|---|---|---|
| 1 — Discover tools | Find the connected Notion MCP tools | no Notion tools present |
| 2 — Load spec | Read `notion://docs/enhanced-markdown-spec` | fetch fails |
| 3 — Read source | Derive the title and the mode | file missing or not `.md` |
| 4 — Resolve target | `--to`/ask on CREATE; fetch-verify the URL either way | URL fails to fetch, or user cancels |
| 5 — Convert | Notion-flavored markdown | — |
| 6 — Confirm | Show destination + flags, wait | user declines |
| 7 — Publish | create, or update `--update` | API error |
| 8 — Report | Print the URL | — |

---

## Step 1 — Discover the Notion tools

**Never hardcode Notion MCP tool names.** The prefix is connection-specific —
`mcp__claude_ai_Notion__notion-create-pages` on a claude.ai-authenticated
connection, something else for a directly-installed server.

If the Notion tools are already in context, use them. In Claude Code they are deferred,
so discover them first:

```
ToolSearch("notion create pages update page fetch search")
```

From the results, record the actual names for: **create-pages**, **update-page**,
**fetch**. This is also why `allowed-tools` ends in the `mcp__*` wildcard rather
than three literal names: the names are not knowable when the frontmatter is
written, and without the wildcard the Step 2 fetch is denied before the skill
reaches anything it could publish. If no Notion tools resolve, stop:

> "No Notion connection is available in this session. Connect the Notion
> integration, then re-run. I won't write the doc anywhere else as a fallback."

Do not fall back to a REST call with a raw token. Publishing goes through the official integration — a
custom client is permanent maintenance for no differentiated value.

## Step 2 — Load the Notion markdown spec

Call the Notion **fetch** tool with `id: "notion://docs/enhanced-markdown-spec"`.

Do this **every run**. Do not convert from memory of the format — Notion-flavored
markdown differs from CommonMark in ways that fail silently rather than loudly,
and the spec is the only authority. Do not pass that URI to WebFetch.

## Step 3 — Read the source document

Read the file. Reject anything that is not `.md`.

Derive:

- **TITLE** — `--title` > frontmatter `title` > first `#` heading > filename
  without extension.
- **MODE** — `--update PAGE_URL` given → `UPDATE` that page. Otherwise `CREATE`.

`--to` together with `--update` is a usage error, not a precedence question.
Stop and say so: `--to` names a parent for a page that does not exist yet,
`--update` names a page that already does. Silently honouring one and dropping
the other re-parents nothing while the user believes it did.

Frontmatter is read for `title` only, and never written. The mode comes from the
command line, not from the file: nothing about which Notion page a document maps
to is stored in the repository.

**A consequence to state plainly at Step 6, and again at Step 8:** publishing the
same file twice with no `--update` produces two separate pages, and nothing in
the repo remembers the first one — not for you a week later, and not for a
teammate on a fresh clone. That is the accepted trade for never touching the
user's files, and it is why the CREATE confirmation says so out loud instead of
letting the duplicate be discovered afterwards. Do not work around it by
searching Notion for a same-titled page and assuming it is the right one.

## Step 4 — Resolve the target

**CREATE** — in priority order:

1. `--to PARENT_URL` — use as parent page.
2. **Ask** (AskUserQuestion, or prose with the same named options):
   - **Private space (recommended default)** — omit the `parent` argument
     entirely and the page is created as a workspace-level private page owned by
     the authenticated user. They move it wherever they want afterwards.
   - **Under a specific page** — they paste a URL.

**UPDATE** — the target is the `--update` URL. There is nothing to choose, which
is precisely why this step is not CREATE-only: an unverified URL is how a
document lands on top of an unrelated page.

Whenever a URL is involved — either CREATE route, or `--update` — **fetch it
first**. Verify it is a page, not a database or data source, and capture its
`<ancestor-path>` so Step 6 can show the user the full path involved. A target
that fails to fetch is a stop, not a guess; on UPDATE, never fall through to
creating a new page instead.

Never resolve a destination by searching the workspace for a plausible-looking
parent. Guessing where a client-visible document goes is the failure mode this
step exists to prevent.

## Step 5 — Convert to Notion-flavored markdown

Follow the spec from Step 2. The conversions that actually bite:

- **Strip the frontmatter, then put back what a reader needs.** Render `status`,
  `approvers`, `authors` and `date` as a `<table>` at the top whenever they are
  present — never judge those four "not worth showing". The mirror is what
  stakeholders actually read, and one that drops `status: draft` or a
  half-finished approver list tells them an unapproved document is settled.
  Purely mechanical keys (`depth`, `related`, ids) can go.
- **Strip the leading `#` heading** if it duplicates TITLE. The title lives in
  `properties`, and Notion renders it above the content already.
- **Pipe tables must become `<table>` XML.** GFM pipe tables are not in the
  spec — they render as literal text with visible pipes. Use
  `header-row="true"` where the first row is a header. Table cells hold rich
  text only: no headings, lists, or images inside a cell.
- **Code fences pass through with a language set.** Content inside a fence is
  literal — do NOT apply escaping there.
- **Mermaid renders natively** with a ```mermaid fence. Wrap any node label
  containing special characters in double quotes (`A["Gateway (OAuth)"]`), use
  `<br>` for line breaks in labels, never `\n`, and never `\(`.
- **Escape outside code blocks** where these characters are meant literally —
  the spec's escape set:

  ```text
  \ * ~ ` $ [ ] < > { } | ^
  ```

- **Nested list children indent with tabs.**
- **`#####`/`######` become `####`** — Notion has no H5/H6.
- **Never emit a `<page>` tag.** Pointing one at an existing URL *moves* that
  page into this one, and dropping the tag later *deletes* the child. Use
  `<mention-page>` for references.

Flag, don't silently break:

- **Relative repo links** (`./lld.md`, `../standards/x.md`) resolve to nothing in
  Notion. Rewrite one to a web URL only when it will actually resolve there —
  `git remote get-url origin` returns a remote, `git ls-files --error-unmatch
  TARGET` succeeds, and `git branch -r --contains HEAD` is non-empty — and pin
  the result to the commit SHA rather than a branch name. If any check fails,
  which is the normal case when the caller deliberately left the document
  uncommitted, leave the path as inline code and list it in Step 6. A rewritten
  link that 404s for every reader is worse than a visible relative path.
- **Local image paths** produce broken image blocks. Do not emit them — list
  them as needing manual upload.

## Step 6 — Confirm

Show, compactly:

- **Mode** — creating a new page, or updating `--update PAGE_URL`. On CREATE,
  say plainly that this makes a *new* page, and that re-running later without
  `--update PAGE_URL` makes another one because the repo keeps no record of this
  page. On UPDATE, say that the page's current content is being replaced.
- **Destination** — the ancestor path from Step 4, or "your private space"
- **Title**
- **Flags** — unresolvable links, local images, anything dropped

Then ask with **AskUserQuestion** where available, offering these options. Do not improvise the
prompt as prose:

- **Publish** — create or update the page now
- **Dry run first** — show the converted markdown, publish nothing
- **Cancel** — stop; nothing is created

**Name the action and spell out the choices.** "Say the word", "let me know", and
"shall I proceed?" leave the user guessing what to type and what happens after
they do. State what will be created, where it lands, and what each option does.
The user should never have to infer that "yes" is the magic word.

**Offer exactly these three options, and no others.** Do not invent extra
questions about what to do with the URL, the file, or git — there is only one
decision here, and it is whether to publish.

`--dry-run` skips straight to the converted output and never reaches Step 7.

**"Dry run first" is not an exit.** Show the converted markdown, then ask the
same question again with the two options that remain — **Publish** and
**Cancel**. That is the same single decision, now informed, so it does not
conflict with "one decision per run". Do not improvise a prose "looks good?",
and do not make the user re-invoke from scratch: a second invocation re-resolves
the destination they just reviewed and can land on a different one.

## Step 7 — Publish

**CREATE** — call create-pages with `properties: {title: TITLE}`, the converted
content, and the parent. Omit `parent` entirely for the private-space case;
do not pass a null or empty value.

**UPDATE** — call update-page against the `--update` URL. Choose the command
deliberately, because the obvious one is not the safe one:

- **`update_content`** — search-and-replace over just the regions that changed.
  This is the right choice whenever only some sections differ, which is every
  `--delta` regeneration. Untouched blocks, comments anchored to them, and any
  child pages all survive.
- **`replace_content`** — only when the entire document was regenerated. Pass the
  full body as `new_str`. It **fails** if the page has child pages or databases
  absent from the new content, listing what would be lost.
- **Never set `allow_deleting_content: true` on your own initiative.** That flag
  turns the failure above into a silent deletion of someone's child pages. If the
  error fires, show the user exactly what would be destroyed and let them decide.

Prefer `update_content` when in doubt. A too-narrow edit is a visible diff someone
can correct; a too-broad one destroys work that was never yours.

If update-page returns not-found or no-access, do NOT create a new page as a
fallback — report it. The likely cause is a wrong URL, or a page that was moved or
trashed, and a silent re-create leaves two divergent copies with no signal which
is current.

Capture the returned page URL.

## Step 8 — Report

The URL is the deliverable. Lead with it, keep the rest to one line each, and
say nothing about frontmatter, git, or link storage — none of that happened.

> Published to Notion: `URL`
>
> Flagged: `N` local images need manual upload; `N` relative links rewritten.

On a CREATE, add the one operational fact the user needs to publish again:

> To update this page later, re-run with `--update PAGE_URL`.

---

## Examples

**Publish a design doc for the first time**

> `/codezen:to-notion docs/design/rate-limiting/design.md`

Resolves no `--to`, so it asks where the page goes and defaults to the user's private
space. Converts pipe tables to `<table>`, keeps the mermaid block, shows the
destination and the flagged items, waits for **Publish**, then prints the URL and the
reminder that re-running without `--update` makes a second page.

**Update the page that doc already has**

> `/codezen:to-notion docs/design/rate-limiting/design.md --update https://notion.so/Rate-Limiting-abc123`

Fetches the URL first to confirm it is a page and to show its ancestor path. Uses
`update_content` over the changed regions rather than `replace_content`, and still
confirms — `--update` overwrites what is already there, so it is never exempt.

**See the conversion without publishing anything**

> `/codezen:to-notion docs/specs/auth.md --dry-run`

Prints the Notion-flavored markdown and stops. Then asks again with the two options
that remain, **Publish** and **Cancel**, so the dry run informs the decision instead of
ending the run.

---

## Rules

- **Discover Notion tool names; never hardcode them.** The prefix varies by how
  the integration is connected.
- **Read the markdown spec every run.** Converting from memory produces pages
  that look fine to the writer and wrong to every reader.
- **Never write to the repository.** No frontmatter, no files, no commits, no
  stored page references. The URL goes to the terminal and nowhere else.
- **UPDATE only when given a URL.** Never infer which existing page a document
  belongs to by searching titles.
- **Confirm the destination before writing.** Every time, unless `--to` was
  explicit. `--update` is never exempt: a page in the wrong space is already
  disclosed, and an overwritten page has already lost what it held.
- **Every confirmation offers named options.** Use AskUserQuestion where available,
  otherwise list the same options in prose. Never "say the word" or "shall I
  proceed?" — the user should always be able to see what they're approving and what
  the alternatives are.
- **One decision per run.** Whether to publish. Don't manufacture others.
- **Describe consequences, not mechanisms.** "Publishing again will create a
  second page" beats any sentence containing the word "frontmatter".
- **No custom Notion client.** Official integration only.
