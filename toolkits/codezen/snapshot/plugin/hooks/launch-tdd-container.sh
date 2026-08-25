#!/usr/bin/env bash
# =============================================================================
# CodeZen TDD Container Launcher — runs on the HOST machine
# =============================================================================
# Builds the TDD Docker image if needed, extracts credentials, launches
# Claude Code inside the container for TDD, then pulls the result branch.
#
# Called by the codezen-tdd skill, not directly by users.
#
# Usage:
#   plugin/hooks/launch-tdd-container.sh \
#     --feature-slug <slug> \
#     --feature-desc <description-or-filepath> \
#     [--base-branch main] \
#     [--timeout 1800] \
#     [--max-cycles 10] \
#     [--model <model-id>] \
#     [--rebuild]
#
# Exit codes:
#   0  — success, branch pulled to host
#   1  — pre-flight check failed
#   2  — Docker image build failed
#   3  — container execution failed
#   4  — branch pull failed
# =============================================================================

set -euo pipefail

# Ensure Docker and Homebrew binaries are on PATH (macOS Docker Desktop installs to /usr/local/bin)
export PATH="/usr/local/bin:/opt/homebrew/bin:${PATH}"

# Resolve codezen-lite plugin root from this script's location (hooks/ lives at <root>/hooks/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEZEN_LITE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[launcher]${NC} $*"; }
warn() { echo -e "${YELLOW}[launcher]${NC} $*" >&2; }
info() { echo -e "${CYAN}[launcher]${NC} $*"; }
die()  { echo -e "${RED}[launcher]${NC} $*" >&2; exit "${2:-1}"; }

# ---------------------------------------------------------------------------
# Keychain helper — reads credentials without ever printing them
# ---------------------------------------------------------------------------
KEYCHAIN_SERVICE="codezen"

keychain_get() {
    # Returns the stored value or empty string. Never echoes to stdout in logs.
    security find-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "$1" \
        -w 2>/dev/null || echo ""
}

keychain_exists() {
    security find-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "$1" \
        -w >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
FEATURE_SLUG=""
FEATURE_DESC=""
BASE_BRANCH="main"
TDD_TIMEOUT="1800"
TDD_MAX_CYCLES="10"
CLAUDE_MODEL=""
REBUILD=false
CHECK_SETUP=false
CHECK_EXTRA=false
FIX_BRANCH=""
EXTRA_ENV_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --feature-slug)  FEATURE_SLUG="$2";   shift 2 ;;
        --feature-desc)  FEATURE_DESC="$2";   shift 2 ;;
        --base-branch)   BASE_BRANCH="$2";    shift 2 ;;
        --timeout)       TDD_TIMEOUT="$2";    shift 2 ;;
        --max-cycles)    TDD_MAX_CYCLES="$2"; shift 2 ;;
        --model)         CLAUDE_MODEL="$2";   shift 2 ;;
        --rebuild)       REBUILD=true;        shift ;;
        --check-setup)   CHECK_SETUP=true;    shift ;;
        --check-extra)   CHECK_EXTRA=true;    shift ;;
        --env)           EXTRA_ENV_ARGS+=(-e "$2"); shift 2 ;;
        --fix-branch)    FIX_BRANCH="$2";           shift 2 ;;
        *) die "Unknown argument: $1" 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# CHECK-SETUP MODE — called by the skill to detect first-time setup needed
# Outputs only "OK" or "SETUP_REQUIRED:<what>" — never credential values
# ---------------------------------------------------------------------------
if [[ "${CHECK_SETUP}" == "true" ]]; then
    MISSING=()

    keychain_exists "anthropic_api_key" || MISSING+=("anthropic_api_key")

    if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
        MISSING+=("github_auth")
    fi

    GIT_NAME=$(git config --global --get user.name 2>/dev/null || echo "")
    GIT_EMAIL=$(git config --global --get user.email 2>/dev/null || echo "")
    if [[ -z "${GIT_NAME}" ]] || [[ -z "${GIT_EMAIL}" ]]; then
        MISSING+=("git_identity")
    fi

    if [[ ${#MISSING[@]} -eq 0 ]]; then
        echo "OK"
    else
        echo "SETUP_REQUIRED:$(IFS=,; echo "${MISSING[*]}")"
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# CHECK-EXTRA MODE — check project extra credentials from .codezen/extra-credentials.json
# Outputs: "OK", "NOT_CONFIGURED", or "EXTRA_REQUIRED:<account>:<desc>,..."
# ---------------------------------------------------------------------------
if [[ "${CHECK_EXTRA}" == "true" ]]; then
    EXTRA_FILE=".codezen/extra-credentials.json"
    if [[ ! -f "${EXTRA_FILE}" ]]; then
        echo "NOT_CONFIGURED"
        exit 0
    fi

    if ! command -v jq >/dev/null 2>&1; then
        echo "OK"  # can't check without jq, proceed
        exit 0
    fi

    EXTRA_MISSING=()
    while IFS=$'\t' read -r account _env_var description required; do
        if [[ "${required}" == "true" ]] && ! keychain_exists "${account}"; then
            EXTRA_MISSING+=("${account}:${description}")
        fi
    done < <(jq -r '.credentials[]? | [.account, .env_var, .description, (.required // false | tostring)] | @tsv' "${EXTRA_FILE}" 2>/dev/null || true)

    if [[ ${#EXTRA_MISSING[@]} -eq 0 ]]; then
        echo "OK"
    else
        echo "EXTRA_REQUIRED:$(IFS=,; echo "${EXTRA_MISSING[*]}")"
    fi
    exit 0
fi

[[ -z "${FEATURE_SLUG}" ]] && die "Missing required argument: --feature-slug" 1
[[ -z "${FEATURE_DESC}" ]] && die "Missing required argument: --feature-desc" 1

PROJECT_DIR="$(pwd)"
PROJECT_NAME="$(basename "${PROJECT_DIR}")"
CONTAINER_NAME="tdd-${PROJECT_NAME}-${FEATURE_SLUG}"
ORIGINAL_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
IMAGE_NAME="codezen-tdd"
IMAGE_TAG="latest"

# Locate the Dockerfile relative to the project or codezen install
DOCKERFILE_PATH=""
if [[ -f "${PROJECT_DIR}/docker/Dockerfile.tdd" ]]; then
    DOCKERFILE_PATH="${PROJECT_DIR}/docker/Dockerfile.tdd"
else
    # Fall back to codezen package install location
    CODEZEN_DIR="$(python -c 'import codezen, os; print(os.path.dirname(codezen.__file__))' 2>/dev/null || echo "")"
    if [[ -n "${CODEZEN_DIR}" ]] && [[ -f "${CODEZEN_DIR}/../../docker/Dockerfile.tdd" ]]; then
        DOCKERFILE_PATH="${CODEZEN_DIR}/../../docker/Dockerfile.tdd"
    fi
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "Running pre-flight checks..."

# 1. Docker daemon running?
if ! docker info >/dev/null 2>&1; then
    die "Docker is not running. Start Docker Desktop or the Docker daemon first." 1
fi
log "  Docker running"

# 2. Docker disk space (informational only)
DOCKER_AVAIL=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1 || echo "unknown")
log "  Docker storage available: ${DOCKER_AVAIL}"

# 3. Anthropic API key — read from Keychain (never from env var)
# Single call avoids TOCTOU: exists-then-get race window
ANTHROPIC_API_KEY=$(keychain_get "anthropic_api_key")
if [[ -z "${ANTHROPIC_API_KEY}" ]]; then
    die "Anthropic API key not found in Keychain.\n  Run setup first:\n  bash plugin/hooks/setup-credentials.sh" 1
fi
log "  Anthropic API key loaded from Keychain"

# 4. GitHub CLI installed?
if ! command -v gh >/dev/null 2>&1; then
    die "GitHub CLI (gh) not installed.\n  Install: brew install gh" 1
fi

# 5. GitHub authenticated?
if ! gh auth status >/dev/null 2>&1; then
    die "Not logged in to GitHub.\n  Run: bash plugin/hooks/setup-credentials.sh --github" 1
fi

# 6. Extract GH_TOKEN from gh's Keychain entry (gh manages its own secure storage)
GH_TOKEN_ERR=$(mktemp /tmp/gh-token-err-XXXXXX)
GH_TOKEN=$(gh auth token 2>"${GH_TOKEN_ERR}" || echo "")
if [[ -z "${GH_TOKEN}" ]]; then
    GH_ERR_MSG=$(cat "${GH_TOKEN_ERR}" 2>/dev/null || echo "")
    rm -f "${GH_TOKEN_ERR}"
    if [[ -n "${GH_ERR_MSG}" ]]; then
        die "Could not extract GitHub token: ${GH_ERR_MSG}\n  Run: bash plugin/hooks/setup-credentials.sh --github" 1
    else
        die "Could not extract GitHub token.\n  Run: bash plugin/hooks/setup-credentials.sh --github" 1
    fi
fi
rm -f "${GH_TOKEN_ERR}"
log "  GitHub auth OK (token extracted from Keychain)"

# 7. Git identity configured? (check local then global)
GIT_USER_NAME=$(git config --get user.name 2>/dev/null || git config --global --get user.name 2>/dev/null || echo "")
GIT_USER_EMAIL=$(git config --get user.email 2>/dev/null || git config --global --get user.email 2>/dev/null || echo "")
if [[ -z "${GIT_USER_NAME}" ]] || [[ -z "${GIT_USER_EMAIL}" ]]; then
    die "Git identity not configured.\n  git config --global user.name 'Your Name'\n  git config --global user.email 'you@example.com'" 1
fi
log "  Git identity: ${GIT_USER_NAME} <${GIT_USER_EMAIL}>"

# 8. Working tree clean? (only check tracked changes — untracked files are OK)
if [[ -n "$(git status --porcelain 2>/dev/null | grep -v '^??')" ]]; then
    die "Working tree has uncommitted changes. Commit or stash first:\n  git stash" 1
fi
log "  Working tree clean"

# 9. Remote origin exists?
if ! git remote get-url origin >/dev/null 2>&1; then
    die "No 'origin' remote configured.\n  git remote add origin https://github.com/owner/repo.git" 1
fi
REMOTE_URL=$(git remote get-url origin)
log "  Remote: ${REMOTE_URL}"

# 10. Detect project type from CodeZen config (optional — entrypoint falls back to stack detection)
PROJECT_TYPE=""
CODEZEN_CONFIG="${PROJECT_DIR}/korza-docs/config.yaml"
if [[ -f "${CODEZEN_CONFIG}" ]]; then
    PROJECT_TYPE=$(grep '^project_type:' "${CODEZEN_CONFIG}" | sed 's/project_type:[[:space:]]*//' | tr -d '"' | tr -d "'" | xargs || echo "")
    if [[ -n "${PROJECT_TYPE}" ]]; then
        log "  Project type: ${PROJECT_TYPE} (from korza-docs/config.yaml)"
    fi
fi

# 11. Kill stale container with same name if it exists
if docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
    warn "Removing stale container: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1
fi

# ---------------------------------------------------------------------------
# Load extra project credentials from .codezen/extra-credentials.json
# Supports two sections:
#   credentials — secrets loaded from Keychain (AWS keys, tokens, DB URLs, etc.)
#   env_vars    — plain non-sensitive values inlined in the config (NODE_ENV, etc.)
# ---------------------------------------------------------------------------
EXTRA_CREDENTIAL_ARGS=()
EXTRA_CREDS_FILE="${PROJECT_DIR}/.codezen/extra-credentials.json"

if [[ -f "${EXTRA_CREDS_FILE}" ]]; then
    if ! command -v jq >/dev/null 2>&1; then
        warn "jq not found — skipping extra credentials from ${EXTRA_CREDS_FILE}"
    else
        log "Loading extra credentials from .codezen/extra-credentials.json..."

        # Secret credentials — fetched from Keychain
        while IFS=$'\t' read -r account env_var description required; do
            [[ -z "${account}" ]] && continue
            VALUE=$(keychain_get "${account}")
            if [[ -z "${VALUE}" ]]; then
                if [[ "${required}" == "true" ]]; then
                    die "Required credential '${account}' (${description}) not in Keychain.\n  Store it first:\n  ! bash plugin/hooks/setup-credentials.sh --store ${account}" 1
                else
                    warn "  Optional '${account}' not in Keychain — skipping ${env_var}"
                fi
            else
                EXTRA_CREDENTIAL_ARGS+=(-e "${env_var}=${VALUE}")
                unset VALUE
                log "  ${env_var} loaded (Keychain: ${account})"
            fi
        done < <(jq -r '.credentials[]? | [.account, .env_var, (.description // ""), (.required // false | tostring)] | @tsv' "${EXTRA_CREDS_FILE}" 2>/dev/null || true)

        # Plain env vars — inlined values (non-sensitive: NODE_ENV, host names, flags)
        while IFS=$'\t' read -r name value; do
            [[ -z "${name}" ]] && continue
            EXTRA_CREDENTIAL_ARGS+=(-e "${name}=${value}")
            log "  ${name} set (plain env var)"
        done < <(jq -r '.env_vars[]? | [.name, .value] | @tsv' "${EXTRA_CREDS_FILE}" 2>/dev/null || true)
    fi
fi

# ---------------------------------------------------------------------------
# Build Docker image if needed
# ---------------------------------------------------------------------------
IMAGE_EXISTS=$(docker images -q "${IMAGE_NAME}:${IMAGE_TAG}" 2>/dev/null || echo "")

if [[ -z "${IMAGE_EXISTS}" ]] || [[ "${REBUILD}" == "true" ]]; then
    if [[ -z "${DOCKERFILE_PATH}" ]]; then
        die "Cannot find docker/Dockerfile.tdd in project or codezen install directory." 2
    fi

    DOCKER_CONTEXT="$(dirname "${DOCKERFILE_PATH}")"
    log "Building ${IMAGE_NAME}:${IMAGE_TAG} from ${DOCKERFILE_PATH}..."
    log "  (first build takes ~5 minutes — cached afterwards)"

    if ! docker build \
        -f "${DOCKERFILE_PATH}" \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        "${DOCKER_CONTEXT}" 2>&1 | tail -5; then
        die "Docker build failed.\n  Debug with:\n  docker build -f ${DOCKERFILE_PATH} -t ${IMAGE_NAME}:${IMAGE_TAG} ${DOCKER_CONTEXT}" 2
    fi
    log "  Image built: ${IMAGE_NAME}:${IMAGE_TAG}"
else
    log "  Using cached image ${IMAGE_NAME}:${IMAGE_TAG} (pass --rebuild to force)"
fi

# ---------------------------------------------------------------------------
# Assemble docker run arguments
# ---------------------------------------------------------------------------
DOCKER_ARGS=(
    --name "${CONTAINER_NAME}"
    --rm

    # Mount project source (read-write — Claude Code writes test + impl files)
    -v "${PROJECT_DIR}:/app"
    -w /app

    # Mount codezen-lite itself (read-only) so projects using the
    # <codezen-lite.path> placeholder in pyproject.toml can resolve it.
    -v "${CODEZEN_LITE_ROOT}:/opt/codezen-lite:ro"
    -e "CODEZEN_LITE_MOUNT=/opt/codezen-lite"

    # Credentials via env vars — never persisted in the image
    -e "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
    -e "GH_TOKEN=${GH_TOKEN}"
    -e "GIT_USER_NAME=${GIT_USER_NAME}"
    -e "GIT_USER_EMAIL=${GIT_USER_EMAIL}"

    # Feature configuration
    -e "FEATURE_SLUG=${FEATURE_SLUG}"
    -e "FEATURE_DESC=${FEATURE_DESC}"
    -e "BASE_BRANCH=${BASE_BRANCH}"
    -e "TDD_TIMEOUT=${TDD_TIMEOUT}"
    -e "TDD_MAX_CYCLES=${TDD_MAX_CYCLES}"
    -e "PROJECT_TYPE=${PROJECT_TYPE}"

    # Resource limits
    --memory 4g
    --cpus 2.0

    # Network access required for git push and Anthropic API calls
    --network host
)

# Optional: Claude model override
if [[ -n "${CLAUDE_MODEL}" ]]; then
    DOCKER_ARGS+=(-e "CLAUDE_MODEL=${CLAUDE_MODEL}")
fi

# Pass fix-branch mode to container when set
if [[ -n "${FIX_BRANCH}" ]]; then
    DOCKER_ARGS+=(-e "FIX_BRANCH=${FIX_BRANCH}")
fi

# Extra project credentials (from .codezen/extra-credentials.json)
if [[ ${#EXTRA_CREDENTIAL_ARGS[@]} -gt 0 ]]; then
    DOCKER_ARGS+=("${EXTRA_CREDENTIAL_ARGS[@]}")
fi

# Non-sensitive config env vars passed via --env flag (e.g. USE_REAL_INFRA, INFRA_TYPE)
# Never pass credential values through this path — use extra-credentials.json instead.
if [[ ${#EXTRA_ENV_ARGS[@]} -gt 0 ]]; then
    DOCKER_ARGS+=("${EXTRA_ENV_ARGS[@]}")
fi

# Mount host Claude plugins so container can use superpowers:test-driven-development
if [[ -d "${HOME}/.claude/plugins" ]]; then
    log "  Mounting host plugins (superpowers skills available)"
    DOCKER_ARGS+=(-v "${HOME}/.claude/plugins:/home/codezen/.claude/plugins:ro")
else
    warn "  ~/.claude/plugins not found — container will run without superpowers skills"
fi

# Optional: SSH keys for projects using SSH git protocol
# Container user is 'codezen' (uid 1000), home is /home/codezen — NOT /root
GIT_PROTOCOL=$(gh config get git_protocol 2>/dev/null || echo "https")
if [[ "${GIT_PROTOCOL}" == "ssh" ]] && [[ -d "${HOME}/.ssh" ]]; then
    log "  Mounting SSH keys (read-only)"
    DOCKER_ARGS+=(-v "${HOME}/.ssh:/home/codezen/.ssh:ro")
    if [[ -n "${SSH_AUTH_SOCK:-}" ]]; then
        DOCKER_ARGS+=(
            -v "${SSH_AUTH_SOCK}:/ssh-agent:ro"
            -e "SSH_AUTH_SOCK=/ssh-agent"
        )
    fi
fi

# Optional: pip config for private package registries
if [[ -f "${HOME}/.pip/pip.conf" ]]; then
    DOCKER_ARGS+=(-v "${HOME}/.pip/pip.conf:/home/codezen/.pip/pip.conf:ro")
fi
if [[ -f "${HOME}/.config/pip/pip.conf" ]]; then
    DOCKER_ARGS+=(-v "${HOME}/.config/pip/pip.conf:/home/codezen/.config/pip/pip.conf:ro")
fi

# Optional: npmrc for private npm registries
if [[ -f "${HOME}/.npmrc" ]]; then
    DOCKER_ARGS+=(-v "${HOME}/.npmrc:/home/codezen/.npmrc:ro")
fi

# ---------------------------------------------------------------------------
# Launch container
# ---------------------------------------------------------------------------
log "Launching TDD container: ${CONTAINER_NAME}"
info "  Feature:    ${FEATURE_SLUG}"
info "  Base:       ${BASE_BRANCH}"
info "  Timeout:    ${TDD_TIMEOUT}s"
info "  Max cycles: ${TDD_MAX_CYCLES}"
echo ""

# Capture output to temp file for result parsing while streaming to terminal
OUTPUT_FILE=$(mktemp /tmp/codezen-tdd-XXXXXX)

# Cleanup container + temp file on Ctrl+C or SIGTERM
cleanup() {
    warn "Interrupted — cleaning up container..."
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
    rm -f "${OUTPUT_FILE}"
    exit 130
}
trap cleanup SIGINT SIGTERM

# Run container — stream to terminal and capture simultaneously
set +e
docker run "${DOCKER_ARGS[@]}" "${IMAGE_NAME}:${IMAGE_TAG}" 2>&1 | tee "${OUTPUT_FILE}"
CONTAINER_EXIT="${PIPESTATUS[0]}"
set -e

# ---------------------------------------------------------------------------
# Parse container exit code
# ---------------------------------------------------------------------------
if [[ "${CONTAINER_EXIT}" -ne 0 ]]; then
    warn "Container exited with code ${CONTAINER_EXIT}"
    case "${CONTAINER_EXIT}" in
        1)   die "Credential validation failed inside container." 3 ;;
        2)   die "Project dependency installation failed inside container." 3 ;;
        3)   die "Claude Code TDD failed — no commits produced." 3 ;;
        4)   die "Git push failed from inside container." 3 ;;
        10)  die "TDD timed out after ${TDD_TIMEOUT}s." 3 ;;
        137) die "Container was killed (OOM?). Increase memory: --memory flag in this script." 3 ;;
        *)   die "Container failed (exit ${CONTAINER_EXIT})." 3 ;;
    esac
fi

# ---------------------------------------------------------------------------
# Parse structured result from container output
# ---------------------------------------------------------------------------
# Use awk — sed -n with q is not portable across macOS/Linux
RESULT_JSON=$(awk '/---CODEZEN-TDD-RESULT---/{found++; next} found==1{print}' "${OUTPUT_FILE}" \
    | tr -d '\n' || echo "")

if [[ -z "${RESULT_JSON}" ]]; then
    warn "Could not parse structured result — inferring branch name"
    BRANCH_NAME="feat/${FEATURE_SLUG}"
    TESTS_PASSED="unknown"
    COMMIT_COUNT="?"
else
    BRANCH_NAME=$(echo "${RESULT_JSON}" | jq -r '.branch // "feat/'"${FEATURE_SLUG}"'"' 2>/dev/null || echo "feat/${FEATURE_SLUG}")
    TESTS_PASSED=$(echo "${RESULT_JSON}" | jq -r '.tests_passed // "unknown"' 2>/dev/null || echo "unknown")
    COMMIT_COUNT=$(echo "${RESULT_JSON}" | jq -r '.commits // "?"' 2>/dev/null || echo "?")
fi

rm -f "${OUTPUT_FILE}"

log "TDD Result:"
info "  Branch:  ${BRANCH_NAME}"
info "  Commits: ${COMMIT_COUNT}"
info "  Tests:   ${TESTS_PASSED}"

# ---------------------------------------------------------------------------
# Pull branch to host
# ---------------------------------------------------------------------------
log "Pulling branch to host..."

if ! git fetch origin "${BRANCH_NAME}" --quiet 2>/dev/null; then
    die "Failed to fetch '${BRANCH_NAME}' from origin." 4
fi
if ! git checkout "${BRANCH_NAME}" --quiet 2>/dev/null; then
    die "Failed to checkout '${BRANCH_NAME}'." 4
fi

log "Now on branch: ${BRANCH_NAME}"

# Return to the original branch so the caller's working directory is unchanged
if [[ -n "${ORIGINAL_BRANCH}" ]] && [[ "${ORIGINAL_BRANCH}" != "${BRANCH_NAME}" ]]; then
    git checkout "${ORIGINAL_BRANCH}" --quiet 2>/dev/null || true
    log "Restored to: ${ORIGINAL_BRANCH}"
fi

echo ""
log "========================================="
log "  TDD complete. Branch ready for review."
log "========================================="
echo ""

# Output final JSON for the skill to consume
echo "${RESULT_JSON:-{\"status\":\"success\",\"branch\":\"${BRANCH_NAME}\",\"tests_passed\":\"unknown\"}}"
