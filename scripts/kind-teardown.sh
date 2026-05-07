#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-energoflow}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    log_error "Cluster '${CLUSTER_NAME}' not found"
    exit 1
fi

log_warn "This will delete the Kind cluster '${CLUSTER_NAME}' and all its data"
read -p "Continue? [y/N] " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Deleting cluster..."
    kind delete cluster --name "$CLUSTER_NAME"
    log_info "Cluster deleted"
else
    log_info "Cancelled"
fi
