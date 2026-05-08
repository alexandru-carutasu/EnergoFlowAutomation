#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-energoflow}"
NAMESPACE="energoflow"
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

check_cluster() {
    if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        log_error "Kind cluster '${CLUSTER_NAME}' not found"
        echo "Run: ./scripts/kind-setup.sh"
        exit 1
    fi

    kubectl config use-context "kind-${CLUSTER_NAME}" &>/dev/null || {
        log_error "Failed to switch kubectl context"
        exit 1
    }

    log_info "Using Kind cluster '${CLUSTER_NAME}'"
}

build_images() {
    log_step "Building Docker images..."

    local services=(
        "api-service:microservices/api-service/Dockerfile"
        "auth-service:microservices/auth-service/Dockerfile"
        "db-service:microservices/db-service/Dockerfile"
        "scheduler-service:microservices/scheduler-service/Dockerfile"
    )

    for service_info in "${services[@]}"; do
        local name="${service_info%%:*}"
        local dockerfile="${service_info##*:}"

        log_info "Building ${name}..."
        docker build \
            -t "energoflow/${name}:local" \
            -f "${PROJECT_ROOT}/${dockerfile}" \
            "${PROJECT_ROOT}"
    done

    log_info "All images built successfully"
}

load_images() {
    log_step "Loading images into Kind cluster..."

    local images=(
        "energoflow/api-service:local"
        "energoflow/auth-service:local"
        "energoflow/db-service:local"
        "energoflow/scheduler-service:local"
    )

    for image in "${images[@]}"; do
        log_info "Loading ${image}..."
        kind load docker-image "$image" --name "$CLUSTER_NAME"
    done

    log_info "All images loaded into cluster"
}

create_secrets() {
    log_step "Creating secrets from secrets.env..."

    local secrets_file="${PROJECT_ROOT}/secrets.env"

    if [ ! -f "$secrets_file" ]; then
        log_warn "secrets.env not found. Copy secrets.env.example to secrets.env and fill in your values."
        log_warn "Skipping secrets creation - pods may fail to start!"
        return
    fi

    # Source the secrets file
    set -a
    source "$secrets_file"
    set +a

    # Create email-secrets
    if ! kubectl get secret email-secrets -n "$NAMESPACE" &>/dev/null; then
        log_info "Creating email-secrets..."
        kubectl create secret generic email-secrets -n "$NAMESPACE" \
            --from-literal=IMAP_SERVER="${IMAP_SERVER}" \
            --from-literal=IMAP_ADDRESS="${IMAP_ADDRESS}" \
            --from-literal=IMAP_PASSWORD="${IMAP_PASSWORD}" \
            --from-literal=FORECAST_ADDRESS="${FORECAST_ADDRESS}" \
            --from-literal=IBD_ADDRESS="${IBD_ADDRESS}"
    else
        log_info "email-secrets already exists (not overwriting)"
    fi

    # Create dropbox-secrets
    if ! kubectl get secret dropbox-secrets -n "$NAMESPACE" &>/dev/null; then
        log_info "Creating dropbox-secrets..."
        kubectl create secret generic dropbox-secrets -n "$NAMESPACE" \
            --from-literal=DROPBOX_APP_KEY="${DROPBOX_APP_KEY}" \
            --from-literal=DROPBOX_APP_SECRET="${DROPBOX_APP_SECRET}"
    else
        log_info "dropbox-secrets already exists (not overwriting)"
    fi

    # Create dropbox-token from file
    if ! kubectl get secret dropbox-token -n "$NAMESPACE" &>/dev/null; then
        local token_file="${PROJECT_ROOT}/${DROPBOX_TOKEN_FILE:-dropbox_token.json}"
        if [ -f "$token_file" ]; then
            log_info "Creating dropbox-token from ${token_file}..."
            kubectl create secret generic dropbox-token -n "$NAMESPACE" \
                --from-file=dropbox_token.json="$token_file"
        else
            log_warn "Dropbox token file not found at ${token_file}"
            log_warn "Create it manually or run Dropbox authorization"
        fi
    else
        log_info "dropbox-token already exists (not overwriting)"
    fi
}

apply_manifests() {
    log_step "Applying Kubernetes manifests..."

    if command -v kustomize &>/dev/null; then
        kustomize build "${PROJECT_ROOT}/k8s/local" | kubectl apply -f -
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/local"
    fi

    log_info "Manifests applied"

    log_step "Restarting deployments to pick up new images..."
    kubectl rollout restart deployment -n "$NAMESPACE"
}

wait_for_pods() {
    log_step "Waiting for pods to be ready..."

    local timeout=300
    local start_time=$(date +%s)

    while true; do
        local pending=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v "Running\|Completed" | wc -l | tr -d ' ')

        if [ "$pending" -eq 0 ]; then
            local running=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep "Running" | wc -l | tr -d ' ')
            if [ "$running" -gt 0 ]; then
                break
            fi
        fi

        local elapsed=$(($(date +%s) - start_time))
        if [ "$elapsed" -gt "$timeout" ]; then
            log_error "Timeout waiting for pods"
            kubectl get pods -n "$NAMESPACE"
            exit 1
        fi

        echo -n "."
        sleep 5
    done

    echo ""
    log_info "All pods are ready"
}

print_status() {
    echo ""
    echo "=============================================="
    echo "  Deployment Complete"
    echo "=============================================="
    echo ""

    kubectl get pods -n "$NAMESPACE"

    echo ""
    echo "Services:"
    echo "  - Web Dashboard: http://localhost:18000"
    echo "  - Kong Admin:    http://localhost:18001"
    echo "  - Grafana:       http://localhost:13000 (admin/admin)"
    echo "  - Prometheus:    http://localhost:19090"
    echo ""
    echo "Useful commands:"
    echo "  kubectl logs -n energoflow -l app=api-service -f"
    echo "  kubectl exec -it -n energoflow deploy/mysql -- mysql -uenergoflow -pchangeme energoflow"
    echo ""
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy EnergoFlow to Kind cluster"
    echo ""
    echo "Options:"
    echo "  --skip-build    Skip building Docker images"
    echo "  --skip-load     Skip loading images to Kind"
    echo "  --manifests     Only apply manifests (no build/load)"
    echo "  -h, --help      Show this help"
}

main() {
    local skip_build=false
    local skip_load=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-build)
                skip_build=true
                shift
                ;;
            --skip-load)
                skip_load=true
                shift
                ;;
            --manifests)
                skip_build=true
                skip_load=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo ""
    log_info "Deploying EnergoFlow to Kind"
    echo ""

    check_cluster

    if [ "$skip_build" = false ]; then
        build_images
    fi

    if [ "$skip_load" = false ]; then
        load_images
    fi

    apply_manifests
    create_secrets
    wait_for_pods
    print_status
}

main "$@"
