#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="energoflow"

echo "=== Pod Status ==="
kubectl get pods -n "$NAMESPACE"
echo ""

echo "=== Scheduler Service Logs (Ctrl+C to exit) ==="
kubectl logs -n "$NAMESPACE" -l app=scheduler-service -f --tail=50
