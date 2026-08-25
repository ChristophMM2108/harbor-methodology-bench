---
name: setup
description: Credential manager for CodeZen — set up or update Anthropic key, GitHub auth, git identity, and any project-specific secrets (AWS, DB, Azure, custom tokens). Run any time to add new credentials.
argument-hint: "[add|update|status] or empty for interactive"
user-invocable: true
allowed-tools: Read Bash Glob Grep Write
---

# CodeZen Credential Manager

Use any time — first-time setup, adding new secrets, or updating existing ones.

**Credentials are stored in macOS Keychain. Claude never sees the actual values.**

---

## Resolve hook paths

At the start of every step in this skill, resolve script paths once and store them:

```bash
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]] && [[ -f "${CLAUDE_PLUGIN_ROOT}/hooks/setup-credentials.sh" ]]; then
    SETUP_SCRIPT="${CLAUDE_PLUGIN_ROOT}/hooks/setup-credentials.sh"
    LAUNCHER_SCRIPT="${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh"
elif [[ -f "plugin/hooks/setup-credentials.sh" ]]; then
    SETUP_SCRIPT="plugin/hooks/setup-credentials.sh"
    LAUNCHER_SCRIPT="plugin/hooks/launch-tdd-container.sh"
else
    echo "ERROR: setup-credentials.sh not found. Is codezen-lite installed as a Claude Code plugin?"
    exit 1
fi
```

Use `${SETUP_SCRIPT}` and `${LAUNCHER_SCRIPT}` for all subsequent calls.

---

## Step 1 — Show current status

Always start by showing what is and isn't configured:

```bash
bash "${SETUP_SCRIPT}" --check
```

```bash
bash "${LAUNCHER_SCRIPT}" --check-extra
```

Print a consolidated status table:

```
Standard credentials:
  ✓ Anthropic API key
  ✓ GitHub auth (logged in as <user>)
  ✓ Git identity (<name> <email>)

Project credentials (.codezen/extra-credentials.json):
  ✓ aws_access_key_id     → AWS_ACCESS_KEY_ID     (in Keychain)
  ✗ database_url          → DATABASE_URL           (missing — required)
  - stripe_api_key        → STRIPE_API_KEY         (missing — optional)

Plain env vars:
  • NODE_ENV = test
  • AZURITE_HOST = localhost
```

If `.codezen/extra-credentials.json` does not exist, show:
```
Project credentials: not configured
```

---

## Step 2 — Ask what the user wants to do

After showing status, ask:

> "What would you like to do?
>
> 1. Set up / fix standard credentials (Anthropic key, GitHub, git identity)
> 2. Add a new project credential (secret stored in Keychain)
> 3. Add a plain env var (non-sensitive value stored in config file)
> 4. Update an existing credential
> 5. Done — everything looks good"

Handle each choice as described below.

---

## Choice 1 — Standard credentials

Walk through each missing standard credential in order.
If all are present, say "All standard credentials are already configured."

### Anthropic API key (if missing or user wants to update)

Say:
> "Get your key from **https://console.anthropic.com/settings/keys**
>
> Run this in your terminal (the `!` prefix keeps the value hidden from me):
> ```
> ! bash "${SETUP_SCRIPT}" --anthropic
> ```"

Wait for confirmation. Then verify:
```bash
bash "${SETUP_SCRIPT}" --check
```

### GitHub auth (if missing or user wants to update)

Say:
> "Run this in your terminal:
> ```
> ! gh auth login
> ```
> Choose: GitHub.com → HTTPS → Login with a web browser."

Wait for confirmation. Then verify:
```bash
gh auth status
```

### Git identity (if missing)

Git name and email are not sensitive — ask directly:
> "What name and email should appear on your git commits?"

Set them:
```bash
git config --global user.name "<name they gave>"
git config --global user.email "<email they gave>"
```

---

## Choice 2 — Add a new project secret (Keychain)

Ask:
> "What secret do you need to add? Describe it and I'll help you configure it.
>
> Examples:
> - Database: PostgreSQL URL, MongoDB URI, Redis URL
> - AWS: Access Key ID, Secret Access Key, region
> - Azure: Storage connection string, client ID/secret
> - GCP: Project ID, service account key path
> - CI/tokens: NPM token, PyPI token, Stripe key, Twilio auth token
> - Custom: any env var your tests or app needs"

From the user's answer, derive:
- `account` — Keychain account name (lowercase, underscores, e.g. `database_url`)
- `env_var` — env var name inside container (uppercase, e.g. `DATABASE_URL`)
- `description` — human-readable label
- `required` — ask: "Is this required for tests to run, or optional?"

**Add to `.codezen/extra-credentials.json`** (create if absent):

```bash
# Read existing or start fresh
cat .codezen/extra-credentials.json 2>/dev/null || echo '{"credentials":[],"env_vars":[]}'
```

Update the `credentials` array with the new entry. Write the file:
```bash
mkdir -p .codezen
# Write updated JSON (preserving existing entries)
```

Then guide the user to store the value:
> "Run this in your terminal to store the value securely:
> ```
> ! bash "${SETUP_SCRIPT}" --store <account>
> ```"

Wait for confirmation. Verify:
```bash
bash "${LAUNCHER_SCRIPT}" --check-extra
```

**After adding**, ask: "Do you have any other credentials to add?"
Loop back to the choice menu if yes.

---

## Choice 3 — Add a plain env var (non-sensitive)

For values that are not secrets — local service hosts, feature flags, runtime modes.

Ask:
> "What env var name and value do you need?
> Example: NODE_ENV=test, AZURITE_HOST=localhost, LOG_LEVEL=debug"

Add to the `env_vars` array in `.codezen/extra-credentials.json`:

```json
{ "name": "NODE_ENV", "value": "test" }
```

Write the updated file. Confirm: "Added `NAME=value` to project env vars."

**Azurite note:** If the user mentions Azurite, suggest:
> "Azurite uses a fixed dev connection string — it's not a real secret. Use a plain env var:
> `AZURITE_CONNECTION_STRING=UseDevelopmentStorage=true`"

---

## Choice 4 — Update an existing credential

Ask which credential they want to update. Show the list from `.codezen/extra-credentials.json` plus standard credentials (names only, never values).

For a **Keychain secret**: guide them to re-run `--store`:
> ```
> ! bash "${SETUP_SCRIPT}" --store <account>
> ```

For a **plain env var**: update the value directly in `.codezen/extra-credentials.json`.

For **standard credentials**: follow the same flow as Choice 1.

---

## Choice 5 — Done

Run a final status check:
```bash
bash "${SETUP_SCRIPT}" --check
bash "${LAUNCHER_SCRIPT}" --check-extra
```

If all required credentials are present:
> "All set! You can now run `/tdd` to start a TDD session."

If required credentials are still missing, show which ones and offer to loop back.

---

## Rules

- **Never print or reference credential values.** Only account names, env var names, and descriptions.
- **Always show current status first** — the user may have come back to add one thing, not redo everything.
- **`--store` must run in the user's terminal** via the `!` prefix — this keeps the value hidden from Claude entirely.
- **`.codezen/extra-credentials.json` is safe to commit** — it contains no values, only names and descriptions.
- **Loop after each addition** — always ask if there's more to add before wrapping up.
- **`required: false` is the safe default** — only set `true` if the user says tests will fail without it.
