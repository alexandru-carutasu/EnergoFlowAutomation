#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="energoflow"

kubectl config set-context --current --namespace="$NAMESPACE"

echo "Default namespace set to: $NAMESPACE"
echo "You can now run kubectl commands without -n energoflow"
