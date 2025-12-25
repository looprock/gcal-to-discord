#!/bin/bash
# Complete deployment script for Google Calendar to Discord sync on Kubernetes
#
# Usage: ./deploy.sh [options]
#
# Options:
#   --namespace NAME    Kubernetes namespace (default: gcal-to-discord)
#   --image IMAGE       Docker image to use
#   --schedule CRON     Cron schedule (default: "*/30 * * * *")
#   --skip-secrets      Skip secret creation
#   --skip-build        Skip Docker build
#   --dry-run           Show what would be done without executing

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default configuration
NAMESPACE="gcal-to-discord"
IMAGE=""
SCHEDULE="*/30 * * * *"
SKIP_SECRETS=false
SKIP_BUILD=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --image)
            IMAGE="$2"
            shift 2
            ;;
        --schedule)
            SCHEDULE="$2"
            shift 2
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--namespace NAME] [--image IMAGE] [--schedule CRON] [--skip-secrets] [--skip-build] [--dry-run]"
            exit 1
            ;;
    esac
done

# Helper functions
error() { echo -e "${RED}ERROR: $1${NC}" >&2; exit 1; }
success() { echo -e "${GREEN}✓ $1${NC}"; }
info() { echo -e "${BLUE}ℹ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

execute() {
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] $*"
    else
        "$@"
    fi
}

# Step 1: Validate prerequisites
validate_prerequisites() {
    info "Validating prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found"
    fi

    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster"
    fi

    # Check Docker if not skipping build
    if [ "$SKIP_BUILD" = false ] && ! command -v docker &> /dev/null; then
        error "Docker not found. Use --skip-build if image is already built."
    fi

    success "Prerequisites validated"
}

# Step 2: Build and push Docker image
build_and_push_image() {
    if [ "$SKIP_BUILD" = true ]; then
        info "Skipping Docker build (--skip-build flag set)"
        return
    fi

    info "Building Docker image..."

    if [ -z "$IMAGE" ]; then
        error "Image name required. Use --image <registry/name:tag>"
    fi

    # Navigate to project root (2 levels up from scripts/)
    cd "$(dirname "$0")/../../../"

    info "Building image: $IMAGE"
    execute docker build -t "$IMAGE" .

    info "Pushing image: $IMAGE"
    execute docker push "$IMAGE"

    success "Docker image built and pushed"
}

# Step 3: Create namespace
create_namespace() {
    info "Creating namespace '$NAMESPACE'..."

    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        info "Namespace already exists"
    else
        execute kubectl create namespace "$NAMESPACE"
        success "Namespace created"
    fi
}

# Step 4: Create secrets
create_secrets() {
    if [ "$SKIP_SECRETS" = true ]; then
        info "Skipping secrets creation (--skip-secrets flag set)"
        return
    fi

    info "Creating secrets..."

    # Check if secret creation script exists
    SCRIPT_DIR="$(dirname "$0")"
    if [ -f "$SCRIPT_DIR/create-secrets.sh" ]; then
        execute "$SCRIPT_DIR/create-secrets.sh"
    else
        warn "Secret creation script not found. Please create secrets manually:"
        echo "  kubectl create secret generic gcal2discord-discord-bot-token --from-literal=token=YOUR_TOKEN -n $NAMESPACE"
        echo "  kubectl create secret generic gcal2discord-google-credentials --from-file=credentials.json -n $NAMESPACE"
        read -p "Press Enter when secrets are ready..."
    fi

    success "Secrets configured"
}

# Step 5: Create ConfigMap
create_configmap() {
    info "Creating ConfigMap..."

    MANIFEST_DIR="$(dirname "$0")/.."

    # Check if user has edited configmap.yaml
    if grep -q "YOUR_DISCORD_CHANNEL_ID" "$MANIFEST_DIR/configmap.yaml" 2>/dev/null; then
        warn "ConfigMap still has placeholder values!"
        echo "Please edit $MANIFEST_DIR/configmap.yaml and set your Discord channel ID"
        read -p "Press Enter when ready..."
    fi

    execute kubectl apply -f "$MANIFEST_DIR/configmap.yaml"
    success "ConfigMap created"
}

# Step 6: Deploy CronJob
deploy_cronjob() {
    info "Deploying CronJob..."

    MANIFEST_DIR="$(dirname "$0")/.."
    TEMP_CRONJOB="/tmp/cronjob-${NAMESPACE}.yaml"

    # Copy and modify CronJob manifest
    cp "$MANIFEST_DIR/cronjob.yaml" "$TEMP_CRONJOB"

    # Update namespace
    sed -i "s/namespace: gcal-to-discord/namespace: $NAMESPACE/g" "$TEMP_CRONJOB"

    # Update image if provided
    if [ -n "$IMAGE" ]; then
        sed -i "s|image: gcal-to-discord:latest|image: $IMAGE|g" "$TEMP_CRONJOB"
    fi

    # Update schedule
    sed -i "s|schedule: \".*\"|schedule: \"$SCHEDULE\"|g" "$TEMP_CRONJOB"

    execute kubectl apply -f "$TEMP_CRONJOB"

    rm -f "$TEMP_CRONJOB"

    success "CronJob deployed"
}

# Step 8: Verify deployment
verify_deployment() {
    info "Verifying deployment..."

    echo
    echo "CronJob status:"
    kubectl get cronjob -n "$NAMESPACE"
    echo

    echo "Recent jobs:"
    kubectl get jobs -n "$NAMESPACE" --sort-by=.metadata.creationTimestamp | tail -5 || echo "No jobs yet"
    echo

    echo "Secrets:"
    kubectl get secrets -n "$NAMESPACE" | grep -E "(NAME|gcal2discord-)" || true
    echo

    success "Deployment verification complete"
}

# Step 9: Show next steps
show_next_steps() {
    echo
    echo "================================================"
    echo "  Deployment Complete!"
    echo "================================================"
    echo
    info "Next Steps:"
    echo
    echo "1. Monitor CronJob:"
    echo "   kubectl get cronjob -n $NAMESPACE -w"
    echo
    echo "2. View logs:"
    echo "   kubectl logs -l app=gcal-to-discord -n $NAMESPACE -f"
    echo
    echo "3. Trigger manual run:"
    echo "   kubectl create job --from=cronjob/gcal-to-discord-sync manual-test -n $NAMESPACE"
    echo
    echo "4. Check job status:"
    echo "   kubectl get jobs -n $NAMESPACE"
    echo
    echo "5. View recent events:"
    echo "   kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'"
    echo
    info "Schedule: $SCHEDULE"
    if [ -n "$IMAGE" ]; then
        info "Image: $IMAGE"
    fi
    echo
}

# Main execution
main() {
    echo "================================================"
    echo "  Google Calendar to Discord - K8s Deployment"
    echo "================================================"
    echo

    if [ "$DRY_RUN" = true ]; then
        warn "DRY RUN MODE - No changes will be made"
        echo
    fi

    validate_prerequisites
    build_and_push_image
    create_namespace
    create_secrets
    create_configmap
    deploy_cronjob
    verify_deployment
    show_next_steps

    success "Deployment complete!"
}

# Run main
main
