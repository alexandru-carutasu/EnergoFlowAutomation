#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-energoflow}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_dependencies() {
    local missing=()

    if ! command -v kind &> /dev/null; then
        missing+=("kind")
    fi

    if ! command -v kubectl &> /dev/null; then
        missing+=("kubectl")
    fi

    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        echo ""
        echo "Install instructions:"
        echo "  kind:    brew install kind"
        echo "  kubectl: brew install kubectl"
        echo "  docker:  https://docs.docker.com/desktop/install/mac-install/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi

    log_info "All dependencies found"
}

create_kind_config() {
    cat <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 30080
        hostPort: 18000
        protocol: TCP
      - containerPort: 30081
        hostPort: 18001
        protocol: TCP
      - containerPort: 30030
        hostPort: 13000
        protocol: TCP
      - containerPort: 30090
        hostPort: 19090
        protocol: TCP
EOF
}

create_cluster() {
    if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        log_warn "Cluster '${CLUSTER_NAME}' already exists"
        read -p "Delete and recreate? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deleting existing cluster..."
            kind delete cluster --name "$CLUSTER_NAME"
        else
            log_info "Using existing cluster"
            return 0
        fi
    fi

    log_info "Creating Kind cluster '${CLUSTER_NAME}'..."
    create_kind_config | kind create cluster --config=-

    log_info "Waiting for cluster to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=120s

    log_info "Cluster '${CLUSTER_NAME}' is ready"
}

print_info() {
    echo ""
    echo "=============================================="
    echo "  Kind cluster '${CLUSTER_NAME}' is ready"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo "  1. Deploy the application:"
    echo "     ./scripts/deploy-kind.sh"
    echo ""
    echo "  2. Access services (after deployment):"
    echo "     - Web Dashboard: http://localhost:18000"
    echo "     - Kong Admin:    http://localhost:18001"
    echo "     - Grafana:       http://localhost:13000"
    echo "     - Prometheus:    http://localhost:19090"
    echo ""
    echo "Useful commands:"
    echo "  kubectl get pods -n energoflow"
    echo "  kubectl logs -n energoflow -l app=api-service"
    echo "  kind delete cluster --name ${CLUSTER_NAME}"
    echo ""
}

main() {
    echo ""
    log_info "Setting up Kind cluster for EnergoFlow"
    echo ""

    check_dependencies
    create_cluster
    print_info
}

main "$@"
