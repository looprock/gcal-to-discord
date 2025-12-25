#!/bin/bash
# Helper script to create Kubernetes secrets for Google Calendar to Discord sync
#
# Usage: ./create-secrets.sh
#
# Prerequisites:
# - kubectl configured and connected to cluster
# - credentials.json downloaded from Google Cloud Console
# - Discord bot token ready
# - Discord channel ID ready

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="gcal-to-discord"
CREDENTIALS_FILE="${CREDENTIALS_FILE:-credentials.json}"
TOKEN_FILE="${TOKEN_FILE:-token.json}"

# Helper functions
error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

prompt() {
    local var_name=$1
    local prompt_text=$2
    local secret=${3:-false}

    if [ "$secret" = true ]; then
        read -sp "$prompt_text: " value
        echo
    else
        read -p "$prompt_text: " value
    fi

    eval "$var_name='$value'"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found. Please install kubectl first."
    fi

    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
    fi

    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        warn "Namespace '$NAMESPACE' does not exist. Creating it..."
        kubectl create namespace "$NAMESPACE"
        success "Namespace created"
    fi

    success "Prerequisites check passed"
}

# Create Discord bot token secret
create_discord_secret() {
    info "Creating Discord bot token secret..."

    if kubectl get secret gcal2discord-discord-bot-token -n "$NAMESPACE" &> /dev/null; then
        warn "Secret 'gcal2discord-discord-bot-token' already exists"
        read -p "Do you want to replace it? (y/N): " replace
        if [ "$replace" != "y" ] && [ "$replace" != "Y" ]; then
            info "Skipping Discord secret creation"
            return
        fi
        kubectl delete secret gcal2discord-discord-bot-token -n "$NAMESPACE"
    fi

    prompt DISCORD_TOKEN "Enter your Discord bot token" true

    if [ -z "$DISCORD_TOKEN" ]; then
        error "Discord bot token cannot be empty"
    fi

    kubectl create secret generic gcal2discord-discord-bot-token \
        --from-literal=token="$DISCORD_TOKEN" \
        -n "$NAMESPACE"

    success "Discord bot token secret created"
}

# Create Google credentials secret
create_google_credentials_secret() {
    info "Creating Google credentials secret..."

    if kubectl get secret gcal2discord-google-credentials -n "$NAMESPACE" &> /dev/null; then
        warn "Secret 'gcal2discord-google-credentials' already exists"
        read -p "Do you want to replace it? (y/N): " replace
        if [ "$replace" != "y" ] && [ "$replace" != "Y" ]; then
            info "Skipping Google credentials secret creation"
            return
        fi
        kubectl delete secret gcal2discord-google-credentials -n "$NAMESPACE"
    fi

    read -p "Path to credentials.json [$CREDENTIALS_FILE]: " creds_path
    creds_path=${creds_path:-$CREDENTIALS_FILE}

    if [ ! -f "$creds_path" ]; then
        error "Credentials file not found: $creds_path"
    fi

    kubectl create secret generic gcal2discord-google-credentials \
        --from-file=credentials.json="$creds_path" \
        -n "$NAMESPACE"

    success "Google credentials secret created"
}

# Create Google token secret (optional)
create_google_token_secret() {
    info "Creating Google OAuth token secret (optional)..."

    if kubectl get secret gcal2discord-google-token -n "$NAMESPACE" &> /dev/null; then
        warn "Secret 'gcal2discord-google-token' already exists"
        read -p "Do you want to replace it? (y/N): " replace
        if [ "$replace" != "y" ] && [ "$replace" != "Y" ]; then
            info "Skipping Google token secret creation"
            return
        fi
        kubectl delete secret gcal2discord-google-token -n "$NAMESPACE"
    fi

    read -p "Do you have a token.json file? (y/N): " has_token

    if [ "$has_token" = "y" ] || [ "$has_token" = "Y" ]; then
        read -p "Path to token.json [$TOKEN_FILE]: " token_path
        token_path=${token_path:-$TOKEN_FILE}

        if [ ! -f "$token_path" ]; then
            error "Token file not found: $token_path"
        fi

        kubectl create secret generic gcal2discord-google-token \
            --from-file=token.json="$token_path" \
            -n "$NAMESPACE"

        success "Google token secret created"
    else
        info "Skipping token secret. It will be generated on first run."
        warn "Note: First run will require manual OAuth authentication"
    fi
}

# Verify secrets
verify_secrets() {
    info "Verifying created secrets..."

    echo
    echo "Secrets in namespace '$NAMESPACE':"
    kubectl get secrets -n "$NAMESPACE" | grep -E "(NAME|gcal2discord-)" || true
    echo

    # Check secret details
    for secret in gcal2discord-discord-bot-token gcal2discord-google-credentials gcal2discord-google-token; do
        if kubectl get secret "$secret" -n "$NAMESPACE" &> /dev/null; then
            echo "Secret '$secret':"
            kubectl describe secret "$secret" -n "$NAMESPACE" | grep -E "(Name:|Namespace:|Type:|Data)"
            echo
        fi
    done

    success "Secret verification complete"
}

# Main execution
main() {
    echo "================================================"
    echo "  Google Calendar to Discord - Secrets Setup"
    echo "================================================"
    echo

    check_prerequisites
    echo

    create_discord_secret
    echo

    create_google_credentials_secret
    echo

    create_google_token_secret
    echo

    verify_secrets
    echo

    success "All secrets created successfully!"
    echo
    info "Next steps:"
    echo "  1. Edit configmap.yaml and set your Discord channel ID"
    echo "  2. Run: kubectl apply -f configmap.yaml"
    echo "  3. Run: kubectl apply -f cronjob.yaml"
    echo
}

# Run main function
main
