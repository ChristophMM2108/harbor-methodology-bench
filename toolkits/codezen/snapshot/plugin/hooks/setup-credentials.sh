#!/usr/bin/env bash
# =============================================================================
# CodeZen Credentials Setup
# =============================================================================
# Run this ONCE from your own terminal — NEVER through Claude Code.
# Credentials are stored in macOS Keychain. The Claude Code LLM never sees
# the actual values at any point.
#
# What this sets up:
#   1. Anthropic API key  → Keychain (service: codezen, account: anthropic_api_key)
#   2. GitHub auth        → via `gh auth login` (gh manages its own Keychain entry)
#   3. Git identity       → git config --global user.name / user.email
#   4. Extra credentials  → arbitrary secrets (AWS, Azure, DB URLs, etc.)
#
# Usage:
#   bash hooks/setup-credentials.sh
#
# To update a single credential:
#   bash hooks/setup-credentials.sh --anthropic
#   bash hooks/setup-credentials.sh --github
#   bash hooks/setup-credentials.sh --git
#
# To store an arbitrary secret (project extra credentials):
#   bash hooks/setup-credentials.sh --store <account>
#   e.g.: bash hooks/setup-credentials.sh --store aws_access_key_id
#
# To verify (prints OK/MISSING per credential, never prints values):
#   bash hooks/setup-credentials.sh --check
# =============================================================================

set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:${PATH}"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()    { echo -e "  ${GREEN}✓${NC} $*"; }
fail()  { echo -e "  ${RED}✗${NC} $*"; }
info()  { echo -e "  ${CYAN}→${NC} $*"; }
warn()  { echo -e "  ${YELLOW}!${NC} $*"; }
header(){ echo -e "\n${BOLD}$*${NC}"; }

# ---------------------------------------------------------------------------
# Keychain helpers — values never echoed to stdout
# ---------------------------------------------------------------------------
KEYCHAIN_SERVICE="codezen"

keychain_get() {
    # $1 = account name
    # Returns value or empty string. Never fails.
    security find-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "$1" \
        -w 2>/dev/null || echo ""
}

keychain_set() {
    # $1 = account name, $2 = value
    # Delete existing entry first (update pattern)
    security delete-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "$1" 2>/dev/null || true
    security add-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "$1" \
        -w "$2" 2>/dev/null
}

keychain_exists() {
    # $1 = account name
    # Returns 0 (true) if key exists, 1 (false) otherwise
    security find-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "$1" \
        -w >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Parse mode flag
# ---------------------------------------------------------------------------
MODE="all"
STORE_ACCOUNT=""
case "${1:-}" in
    --anthropic) MODE="anthropic" ;;
    --github)    MODE="github" ;;
    --git)       MODE="git" ;;
    --check)     MODE="check" ;;
    --store)
        MODE="store"
        STORE_ACCOUNT="${2:-}"
        ;;
    --help|-h)
        sed -n '/^# Usage:/,/^# ====/p' "$0" | grep -v '^# ====' | sed 's/^# //'
        exit 0
        ;;
    "") MODE="all" ;;
    *)  echo "Unknown flag: $1. Use --help for usage." >&2; exit 1 ;;
esac

# ---------------------------------------------------------------------------
# CHECK MODE — print status without revealing values
# ---------------------------------------------------------------------------
if [[ "${MODE}" == "check" ]]; then
    echo ""
    echo -e "${BOLD}CodeZen Credentials Status${NC}"
    echo "────────────────────────────────"

    # Anthropic API key
    if keychain_exists "anthropic_api_key"; then
        VALUE=$(keychain_get "anthropic_api_key")
        PREFIX="${VALUE:0:10}"
        ok "Anthropic API key   (${PREFIX}...)"
    else
        fail "Anthropic API key   MISSING"
    fi

    # GitHub auth
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        GH_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
        ok "GitHub auth         (logged in as ${GH_USER})"
    else
        fail "GitHub auth         MISSING — run: gh auth login"
    fi

    # Git identity
    GIT_NAME=$(git config --global --get user.name 2>/dev/null || echo "")
    GIT_EMAIL=$(git config --global --get user.email 2>/dev/null || echo "")
    if [[ -n "${GIT_NAME}" ]] && [[ -n "${GIT_EMAIL}" ]]; then
        ok "Git identity        (${GIT_NAME} <${GIT_EMAIL}>)"
    else
        fail "Git identity        MISSING — run this script to configure"
    fi

    echo ""

    # Exit 0 only if all present
    if keychain_exists "anthropic_api_key" \
        && (command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1) \
        && [[ -n "${GIT_NAME}" ]] && [[ -n "${GIT_EMAIL}" ]]; then
        echo -e "${GREEN}All credentials configured.${NC}"
        exit 0
    else
        echo -e "${RED}Some credentials are missing. Run: bash hooks/setup-credentials.sh${NC}"
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# STORE MODE — save an arbitrary project secret to Keychain
# ---------------------------------------------------------------------------
if [[ "${MODE}" == "store" ]]; then
    echo ""
    echo -e "${BOLD}Store Project Secret in Keychain${NC}"
    echo "────────────────────────────────"
    echo "The value will be stored securely. Claude Code never sees it."
    echo ""

    if [[ -z "${STORE_ACCOUNT}" ]]; then
        echo -n "  Keychain account name (e.g. aws_access_key_id): "
        read -r STORE_ACCOUNT
        if [[ -z "${STORE_ACCOUNT}" ]]; then
            fail "Account name cannot be empty"
            exit 1
        fi
    fi

    # Show whether existing entry will be overwritten
    if keychain_exists "${STORE_ACCOUNT}"; then
        warn "Existing entry found for '${STORE_ACCOUNT}'"
        echo -n "  Overwrite? [y/N]: "
        read -r OVERWRITE
        if [[ "${OVERWRITE}" != "y" ]] && [[ "${OVERWRITE}" != "Y" ]]; then
            ok "Keeping existing value for '${STORE_ACCOUNT}'"
            exit 0
        fi
    fi

    echo -n "  Value for '${STORE_ACCOUNT}' (hidden): "
    read -rs STORE_VALUE
    echo ""

    if [[ -z "${STORE_VALUE}" ]]; then
        fail "No value entered — nothing saved"
        exit 1
    fi

    keychain_set "${STORE_ACCOUNT}" "${STORE_VALUE}"
    unset STORE_VALUE
    ok "'${STORE_ACCOUNT}' saved to Keychain (service: ${KEYCHAIN_SERVICE})"
    exit 0
fi

# ---------------------------------------------------------------------------
# SETUP MODE
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   CodeZen Credentials Setup               ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "Credentials are stored in macOS Keychain."
echo "The Claude Code LLM never sees these values."
echo ""

# ---------------------------------------------------------------------------
# 1. Anthropic API key
# ---------------------------------------------------------------------------
if [[ "${MODE}" == "all" ]] || [[ "${MODE}" == "anthropic" ]]; then
    header "1. Anthropic API Key"

    EXISTING=""
    if keychain_exists "anthropic_api_key"; then
        EXISTING=$(keychain_get "anthropic_api_key")
        EXISTING_PREFIX="${EXISTING:0:10}"
        warn "Existing key found: ${EXISTING_PREFIX}..."
        echo -n "  Overwrite? [y/N]: "
        read -r OVERWRITE
        if [[ "${OVERWRITE}" != "y" ]] && [[ "${OVERWRITE}" != "Y" ]]; then
            ok "Keeping existing Anthropic key"
        else
            EXISTING=""
        fi
    fi

    if [[ -z "${EXISTING}" ]]; then
        echo ""
        info "Get your key from: https://console.anthropic.com/settings/keys"
        echo ""
        echo -n "  Anthropic API key (hidden): "
        read -rs ANTHROPIC_KEY
        echo ""

        if [[ -z "${ANTHROPIC_KEY}" ]]; then
            fail "No key entered — skipping"
        elif [[ ! "${ANTHROPIC_KEY}" =~ ^sk- ]]; then
            fail "Key must start with 'sk-' — not saved"
        else
            keychain_set "anthropic_api_key" "${ANTHROPIC_KEY}"
            unset ANTHROPIC_KEY
            ok "Anthropic API key saved to Keychain"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 2. GitHub auth
# ---------------------------------------------------------------------------
if [[ "${MODE}" == "all" ]] || [[ "${MODE}" == "github" ]]; then
    header "2. GitHub Authentication"

    if ! command -v gh >/dev/null 2>&1; then
        fail "GitHub CLI not installed."
        info "Install with: brew install gh"
    elif gh auth status >/dev/null 2>&1; then
        GH_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
        ok "Already logged in as: ${GH_USER}"
    else
        info "Opening GitHub login..."
        echo ""
        gh auth login
        echo ""
        if gh auth status >/dev/null 2>&1; then
            GH_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
            ok "Logged in as: ${GH_USER}"
        else
            fail "GitHub login failed — retry with: gh auth login"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 3. Git identity
# ---------------------------------------------------------------------------
if [[ "${MODE}" == "all" ]] || [[ "${MODE}" == "git" ]]; then
    header "3. Git Identity"

    CURRENT_NAME=$(git config --global --get user.name 2>/dev/null || echo "")
    CURRENT_EMAIL=$(git config --global --get user.email 2>/dev/null || echo "")

    if [[ -n "${CURRENT_NAME}" ]] && [[ -n "${CURRENT_EMAIL}" ]]; then
        warn "Existing identity: ${CURRENT_NAME} <${CURRENT_EMAIL}>"
        echo -n "  Keep this? [Y/n]: "
        read -r KEEP_GIT
        if [[ "${KEEP_GIT}" == "n" ]] || [[ "${KEEP_GIT}" == "N" ]]; then
            CURRENT_NAME=""
            CURRENT_EMAIL=""
        else
            ok "Keeping existing git identity"
        fi
    fi

    if [[ -z "${CURRENT_NAME}" ]]; then
        echo -n "  Your full name: "
        read -r GIT_NAME
        if [[ -n "${GIT_NAME}" ]]; then
            git config --global user.name "${GIT_NAME}"
            ok "Git name set"
        fi
    fi

    if [[ -z "${CURRENT_EMAIL}" ]]; then
        echo -n "  Your email: "
        read -r GIT_EMAIL
        if [[ -n "${GIT_EMAIL}" ]]; then
            git config --global user.email "${GIT_EMAIL}"
            ok "Git email set"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Final status check
# ---------------------------------------------------------------------------
echo ""
echo "────────────────────────────────"
echo -e "${BOLD}Setup complete. Verifying...${NC}"
echo ""

SETUP_OK=true

if keychain_exists "anthropic_api_key"; then
    VALUE=$(keychain_get "anthropic_api_key")
    ok "Anthropic API key   (${VALUE:0:10}...)"
else
    fail "Anthropic API key   MISSING"
    SETUP_OK=false
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GH_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
    ok "GitHub auth         (${GH_USER})"
else
    fail "GitHub auth         MISSING"
    SETUP_OK=false
fi

GIT_NAME=$(git config --global --get user.name 2>/dev/null || echo "")
GIT_EMAIL=$(git config --global --get user.email 2>/dev/null || echo "")
if [[ -n "${GIT_NAME}" ]] && [[ -n "${GIT_EMAIL}" ]]; then
    ok "Git identity        (${GIT_NAME} <${GIT_EMAIL}>)"
else
    fail "Git identity        incomplete"
    SETUP_OK=false
fi

echo ""
if [[ "${SETUP_OK}" == "true" ]]; then
    echo -e "${GREEN}${BOLD}All credentials configured. You can now run /tdd${NC}"
else
    echo -e "${YELLOW}Some credentials still missing. Re-run this script to complete setup.${NC}"
    exit 1
fi
