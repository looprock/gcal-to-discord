#!/bin/bash
# Cleanup script for Google Calendar to Discord Kubernetes resources
#
# Usage: ./cleanup.sh [--namespace NAME] [--all] [--secrets-only]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default configuration
NAMESPACE="gcal-to-discord"
DELETE_SECRETS=false
DELETE_ALL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --all)
            DELETE_ALL=true
            DELETE_SECRETS=true
            shift
            ;;
        --secrets-only)
            DELETE_SECRETS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--namespace NAME] [--all] [--secrets-only]"
            exit 1
            ;;
    esac
done

error() { echo -e "${RED}ERROR: $1${NC}" >&2; exit 1; }
success() { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

echo "================================================"
echo "  Google Calendar to Discord - Cleanup"
echo "================================================"
echo

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    error "Namespace '$NAMESPACE' does not exist"
fi

# Show what will be deleted
echo "The following resources will be deleted:"
echo

if [ "$DELETE_ALL" = true ]; then
    echo "  - Namespace: $NAMESPACE (and ALL resources within)"
else
    echo "  - CronJob: gcal-to-discord-sync"
    echo "  - Active Jobs and Pods"
    echo "  - ConfigMap: gcal-to-discord-config"

    if [ "$DELETE_SECRETS" = true ]; then
        echo "  - Secret: gcal2discord-discord-bot-token"
        echo "  - Secret: gcal2discord-google-credentials"
        echo "  - Secret: gcal2discord-google-token"
    fi
fi

echo
warn "This action cannot be undone!"
read -p "Are you sure you want to continue? (yes/NO): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo

# Delete entire namespace
if [ "$DELETE_ALL" = true ]; then
    echo "Deleting namespace '$NAMESPACE'..."
    kubectl delete namespace "$NAMESPACE" --wait=true
    success "Namespace deleted (all resources removed)"
    exit 0
fi

# Delete CronJob
echo "Deleting CronJob..."
if kubectl get cronjob gcal-to-discord-sync -n "$NAMESPACE" &> /dev/null; then
    kubectl delete cronjob gcal-to-discord-sync -n "$NAMESPACE"
    success "CronJob deleted"
else
    warn "CronJob not found"
fi

# Delete Jobs
echo "Deleting Jobs..."
JOBS=$(kubectl get jobs -n "$NAMESPACE" -l app=gcal-to-discord -o name)
if [ -n "$JOBS" ]; then
    echo "$JOBS" | xargs kubectl delete -n "$NAMESPACE"
    success "Jobs deleted"
else
    warn "No jobs found"
fi

# Delete Pods
echo "Deleting Pods..."
PODS=$(kubectl get pods -n "$NAMESPACE" -l app=gcal-to-discord -o name)
if [ -n "$PODS" ]; then
    echo "$PODS" | xargs kubectl delete -n "$NAMESPACE" --force --grace-period=0
    success "Pods deleted"
else
    warn "No pods found"
fi

# Delete ConfigMap
echo "Deleting ConfigMap..."
if kubectl get configmap gcal-to-discord-config -n "$NAMESPACE" &> /dev/null; then
    kubectl delete configmap gcal-to-discord-config -n "$NAMESPACE"
    success "ConfigMap deleted"
else
    warn "ConfigMap not found"
fi

# Delete Secrets
if [ "$DELETE_SECRETS" = true ]; then
    echo "Deleting Secrets..."

    for secret in gcal2discord-discord-bot-token gcal2discord-google-credentials gcal2discord-google-token; do
        if kubectl get secret "$secret" -n "$NAMESPACE" &> /dev/null; then
            kubectl delete secret "$secret" -n "$NAMESPACE"
            success "Secret '$secret' deleted"
        else
            warn "Secret '$secret' not found"
        fi
    done
fi

echo
success "Cleanup complete!"
echo

if [ "$DELETE_SECRETS" = false ]; then
    warn "Secrets were preserved. Use --secrets-only to delete them if needed."
fi
