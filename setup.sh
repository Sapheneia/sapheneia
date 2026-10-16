#!/bin/bash
# =============================================================================
# Sapheneia v2 — single-command setup
# =============================================================================
# Usage:
#   ./setup.sh up              start full stack + run migrations + create symlinks
#   ./setup.sh down            stop containers (preserve data)
#   ./setup.sh reset           down + drop the database volume + remove symlinks
#   ./setup.sh test            run pytest
#   ./setup.sh logs [SERVICE]  follow logs
#   ./setup.sh status          docker compose ps
#   ./setup.sh -h | --help     show this help
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
ENV_TEMPLATE="${REPO_ROOT}/.env.template"
# Compose prefixes named volumes with the project name, which defaults to the
# directory basename. Hardcoding the prefix means `reset` silently removes
# nothing when the repo is cloned elsewhere or COMPOSE_PROJECT_NAME is set.
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]_-')}"
DB_VOLUME="${COMPOSE_PROJECT}_timescaledb_data"
SKILLS_SRC="${REPO_ROOT}/skills"
CLAUDE_SKILLS_DIR="${REPO_ROOT}/.claude/skills"
AGENT_SKILLS_DIR="${REPO_ROOT}/.agent/skills"

if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

log()  { printf "${BLUE}[setup]${NC} %s\n" "$*"; }
ok()   { printf "${GREEN}[ok]${NC}   %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
err()  { printf "${RED}[err]${NC}  %s\n" "$*" >&2; }

compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        err "docker compose not found"
        exit 1
    fi
}

ensure_env() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_TEMPLATE" ]; then
            log "Copying .env.template to .env"
            cp "$ENV_TEMPLATE" "$ENV_FILE"
            warn "Edit .env and set API_SECRET_KEY, TRADING_API_KEY, ORCHESTRATOR_API_KEY before running anything sensitive"
        else
            err "no .env or .env.template found"
            exit 1
        fi
    fi
}

# Database storage is a Docker named volume; compose creates it on demand.
# The bind-mounted directories do need to exist and be writable by the
# containers, which run as uid 1000 — on Linux a host-owned directory is not.
ensure_data_dir() {
    for dir in "${REPO_ROOT}/logs" "${MODELS_CACHE_PATH:-${REPO_ROOT}/.models_cache}"; do
        mkdir -p "$dir"
        chmod a+rwX "$dir" 2>/dev/null || warn "could not relax permissions on $dir"
    done
}

create_skill_symlinks() {
    log "Linking skills/ into .claude/skills and .agent/skills"
    mkdir -p "$CLAUDE_SKILLS_DIR" "$AGENT_SKILLS_DIR"
    for dir in "$SKILLS_SRC"/*/ ; do
        [ -d "$dir" ] || continue
        name="$(basename "$dir")"
        for parent in "$CLAUDE_SKILLS_DIR" "$AGENT_SKILLS_DIR"; do
            target="$parent/$name"
            if [ -L "$target" ]; then rm "$target"; fi
            if [ -e "$target" ]; then
                warn "$target exists and is not a symlink; leaving in place"
                continue
            fi
            ln -s "$dir" "$target"
        done
    done
}

remove_skill_symlinks() {
    for parent in "$CLAUDE_SKILLS_DIR" "$AGENT_SKILLS_DIR"; do
        [ -d "$parent" ] || continue
        for link in "$parent"/*; do
            [ -L "$link" ] || continue
            rm "$link"
        done
    done
}

wait_healthy() {
    local container="$1"
    local timeout="${2:-90}"
    local start
    start=$(date +%s)
    while true; do
        local status
        status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "absent")
        if [ "$status" = "healthy" ]; then
            return 0
        fi
        if [ $(( $(date +%s) - start )) -gt "$timeout" ]; then
            err "$container did not become healthy in ${timeout}s (last status: $status)"
            return 1
        fi
        sleep 2
    done
}

run_migrations() {
    log "Applying alembic migrations"
    # Honour TIMESCALEDB_HOST so migrations can also run from inside a
    # container or against a remote database, matching every service's config.
    local dsn="postgresql+psycopg://${TIMESCALEDB_USER:-sapheneia}:${TIMESCALEDB_PASSWORD:-sapheneia}@${TIMESCALEDB_HOST:-localhost}:${TIMESCALEDB_PORT:-5432}/${TIMESCALEDB_DB:-sapheneia}"
    DATABASE_URL="$dsn" uv run alembic -c "$REPO_ROOT/migrations/alembic.ini" upgrade head
}

cmd_up() {
    ensure_env
    ensure_data_dir

    # shellcheck disable=SC1090
    set -a; source "$ENV_FILE"; set +a

    log "Bringing up the docker stack"
    compose --profile cpu up -d --build

    log "Waiting for TimescaleDB to be healthy"
    wait_healthy sapheneia-timescaledb 60 || exit 1

    run_migrations

    log "Waiting for a forecast model container to be healthy"
    wait_healthy forecast-chronos-t5-tiny 180 \
        || warn "no forecast model container is healthy; runs will fail to reach a model"

    log "Waiting for orchestrator to be healthy"
    wait_healthy sapheneia-orchestrator 90 || warn "orchestrator did not pass /health in time"

    create_skill_symlinks

    ok "Stack up. Service URLs:"
    cat <<EOF
    forecast (gateway)        http://localhost:${FORECAST_PORT:-12700}
    data                       http://localhost:${DATA_API_PORT:-12701}
    metrics                    http://localhost:${METRICS_PORT:-12702}
    sapheneia-mcp              http://localhost:${SAPHENEIA_MCP_PORT:-12703}
    orchestrator               http://localhost:${ORCHESTRATOR_PORT:-12704}
    trading                    http://localhost:${TRADING_API_PORT:-12132}
    timescaledb (postgres)     localhost:${TIMESCALEDB_PORT:-5432}
EOF
}

cmd_down() {
    log "Stopping the docker stack (data preserved)"
    compose --profile cpu down
    ok "Stopped"
}

cmd_reset() {
    cmd_down
    log "Removing database volume $DB_VOLUME"
    docker volume rm -f "$DB_VOLUME" >/dev/null 2>&1 || true
    remove_skill_symlinks
    ok "Reset complete"
}

cmd_test() {
    uv run pytest "$@"
}

cmd_logs() {
    if [ $# -ge 1 ]; then
        compose logs -f "$@"
    else
        compose logs -f
    fi
}

cmd_status() {
    compose ps
}

usage() {
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
}

main() {
    local cmd="${1:-}"
    case "$cmd" in
        up)     shift; cmd_up "$@" ;;
        down)   shift; cmd_down "$@" ;;
        reset)  shift; cmd_reset "$@" ;;
        test)   shift; cmd_test "$@" ;;
        logs)   shift; cmd_logs "$@" ;;
        status) shift; cmd_status "$@" ;;
        -h|--help|help|"") usage ;;
        *) err "unknown command: $cmd"; usage; exit 1 ;;
    esac
}

main "$@"
