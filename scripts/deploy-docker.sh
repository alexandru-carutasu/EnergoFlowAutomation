#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*"; }

check_dependencies() {
    if ! command -v docker &>/dev/null; then
        log_error "Docker not found. Install: https://docs.docker.com/desktop/"
        exit 1
    fi

    if ! docker info &>/dev/null; then
        log_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi

    if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
        log_error "Docker Compose not found"
        exit 1
    fi

    log_info "Dependencies OK"
}

setup_env() {
    if [ ! -f "${PROJECT_ROOT}/.env" ]; then
        log_warn ".env file not found, creating from .env.example"
        cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
        log_warn "Please edit .env with your actual values"
    fi
}

compose_cmd() {
    if docker compose version &>/dev/null; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

start_services() {
    log_step "Starting services with Docker Compose..."

    cd "$PROJECT_ROOT"
    compose_cmd up -d --build

    log_info "Services started"
}

wait_for_healthy() {
    log_step "Waiting for services to be healthy..."

    local timeout=120
    local start_time=$(date +%s)

    while true; do
        local unhealthy=$(compose_cmd ps --format json 2>/dev/null | grep -c '"unhealthy"' || echo "0")
        local starting=$(compose_cmd ps --format json 2>/dev/null | grep -c '"starting"' || echo "0")

        if [ "$unhealthy" -eq 0 ] && [ "$starting" -eq 0 ]; then
            local running=$(compose_cmd ps --services --filter "status=running" 2>/dev/null | wc -l || echo "0")
            if [ "$running" -gt 0 ]; then
                break
            fi
        fi

        local elapsed=$(($(date +%s) - start_time))
        if [ "$elapsed" -gt "$timeout" ]; then
            log_warn "Timeout waiting for healthy status, checking manually..."
            break
        fi

        echo -n "."
        sleep 3
    done
    echo ""
}

print_status() {
    echo ""
    echo "=============================================="
    echo "  Docker Compose Deployment"
    echo "=============================================="
    echo ""

    cd "$PROJECT_ROOT"
    compose_cmd ps

    echo ""
    echo "Services:"
    echo "  - Main Service:  http://localhost:5000"
    echo "  - Auth Service:  http://localhost:5001"
    echo "  - Adminer (DB):  http://localhost:8080"
    echo ""
    echo "Database connection:"
    echo "  - Host: localhost"
    echo "  - Port: 3306"
    echo "  - User: Check .env (DB_USER)"
    echo "  - Pass: Check .env (DB_PASSWORD)"
    echo ""
    echo "Commands:"
    echo "  View logs:     docker compose logs -f"
    echo "  Stop:          docker compose down"
    echo "  Stop + clean:  docker compose down -v"
    echo ""
}

stop_services() {
    log_step "Stopping services..."
    cd "$PROJECT_ROOT"
    compose_cmd down
    log_info "Services stopped"
}

show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Deploy EnergoFlow with Docker Compose"
    echo ""
    echo "Commands:"
    echo "  start     Start all services (default)"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  logs      Follow logs"
    echo "  status    Show service status"
    echo "  clean     Stop and remove volumes"
    echo "  -h        Show this help"
}

main() {
    local command="${1:-start}"

    case "$command" in
        start)
            log_info "Starting EnergoFlow with Docker Compose"
            check_dependencies
            setup_env
            start_services
            wait_for_healthy
            print_status
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            start_services
            wait_for_healthy
            print_status
            ;;
        logs)
            cd "$PROJECT_ROOT"
            compose_cmd logs -f
            ;;
        status)
            cd "$PROJECT_ROOT"
            compose_cmd ps
            ;;
        clean)
            log_warn "This will remove all data volumes!"
            read -p "Continue? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                cd "$PROJECT_ROOT"
                compose_cmd down -v
                log_info "Cleaned up"
            fi
            ;;
        -h|--help|help)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
